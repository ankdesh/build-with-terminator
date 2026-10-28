#!/usr/bin/env python3
"""Run the pinned PicoRV32 ASAP7 RTL-to-GDS flow. Requires Python 3.12+."""
import argparse
import collections
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
DEFAULT_OUTPUT = PROJECT / "output/picorv32_asap7"
ORFS_URL = "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git"
ORFS_COMMIT = "64939f3717ad7c694199ba04cb98924b98022868"
RTL_COMMIT = "ef203c2b0a3fb793280f5114941416c425c5b461"
IMAGE = "openroad/orfs@sha256:6810dbf0e03dddbc89ed8c0a1e13cad09ce4c98d40c4ac0ab99fdc04b0676347"
OPENROAD = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"
YOSYS = "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys"
REQUIRED = ("gds", "def", "odb", "v", "sdc", "spef")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def capture(command):
    return subprocess.check_output(command, text=True).strip()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def file_hashes(root):
    return {str(p.relative_to(root)): sha256(p)
            for p in sorted(root.rglob("*")) if p.is_file()}


def source_hashes():
    lock = json.loads((HERE / "sources.lock.json").read_text())
    actual = {name: sha256(HERE / name) for name in lock["rtl"]["files"]}
    if actual != lock["rtl"]["files"]:
        raise ValueError("Vendored PicoRV32 files differ from sources.lock.json")
    return actual


@contextlib.contextmanager
def exclusive(path):
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another flow command holds " + str(path)) from None
        yield


def prepare(args):
    source_hashes()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    with exclusive(root / ".prepare.lock"):
        repo = root / "orfs"
        if not (repo / ".git").is_dir():
            if args.orfs_source:
                source = args.orfs_source.resolve()
                if not (source / ".git").is_dir() or (source / ".git/objects/info/alternates").exists():
                    raise ValueError("Local ORFS source must have an independent .git directory")
                if capture(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"]):
                    raise ValueError("Local ORFS source has local changes")
                # Copy the partial clone and its objects. A Git local clone tries
                # to serve missing historical blobs from the promisor remote.
                shutil.copytree(source, repo, symlinks=True)
            else:
                subprocess.run(["git", "clone", "--no-checkout", "--filter=blob:none",
                                ORFS_URL, str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", ORFS_URL], check=True)
            subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set",
                            "flow/scripts", "flow/util", "flow/platforms/asap7",
                            "flow/platforms/common"], check=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "--detach", ORFS_COMMIT], check=True)
        if capture(["git", "-C", str(repo), "rev-parse", "HEAD"]) != ORFS_COMMIT:
            raise ValueError("ORFS revision differs from the pin; use a new output directory")
        if capture(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"]):
            raise ValueError("ORFS checkout has local changes")
        if subprocess.run(["docker", "image", "inspect", IMAGE], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode:
            subprocess.run(["docker", "pull", IMAGE], check=True)
        image = json.loads(capture(["docker", "image", "inspect", IMAGE]))[0]
        probe = capture(["docker", "run", "--rm", "--network=none", "--entrypoint", "bash", IMAGE,
                         "-lc", "source /OpenROAD-flow-scripts/env.sh; openroad -version; "
                         "yosys -V; klayout -v; sha256sum " + OPENROAD + " " + YOSYS])
        collateral = repo / "flow/platforms/asap7"
        toolchain = {"prepared_at": utc_now(), "orfs_url": ORFS_URL,
                     "orfs_commit": ORFS_COMMIT, "image": IMAGE, "image_id": image["Id"],
                     "tool_versions_and_binary_hashes": probe,
                     "orfs_files": file_hashes(repo / "flow"),
                     "asap7_files": file_hashes(collateral), "rtl_commit": RTL_COMMIT,
                     "rtl_files": source_hashes(),
                     "submodules": capture(["git", "-C", str(repo), "ls-tree", "HEAD", "tools/"])}
        manifest = root / "toolchain.json"
        if manifest.exists():
            previous = json.loads(manifest.read_text())
            for key in toolchain.keys() - {"prepared_at"}:
                if previous.get(key) != toolchain[key]:
                    raise ValueError("Prepared toolchain changed. Use a new output directory")
        else:
            write_json(manifest, toolchain)
        print("Prepared pinned ORFS, ASAP7, and container:", root, flush=True)


def verified_toolchain(root):
    toolchain = json.loads((root / "toolchain.json").read_text())
    if toolchain["orfs_commit"] != ORFS_COMMIT or toolchain["image"] != IMAGE:
        raise ValueError("Toolchain pin differs; run prepare with a new output directory")
    actual = file_hashes(root / "orfs/flow")
    if actual != toolchain["orfs_files"]:
        raise ValueError("ORFS files differ from the prepared hashes")
    return toolchain


def docker_command(args, work, target):
    name = f"picorv32-asap7-{args.attempt}-{os.getpid()}"
    command = ["docker", "run", "--rm", "--name", name, "--network=none",
               f"--cpus={args.threads}", f"--memory={args.memory_gib}g",
               f"--memory-swap={args.memory_gib}g", "--user", f"{os.getuid()}:{os.getgid()}",
               "--mount", f"type=bind,src={args.output / 'orfs'},dst=/orfs,readonly",
               "--mount", f"type=bind,src={work / 'inputs'},dst=/inputs,readonly",
               "--mount", f"type=bind,src={work},dst=/work", "--entrypoint", "bash", IMAGE,
               "-lc", "source /OpenROAD-flow-scripts/env.sh; cd /orfs/flow; exec make "
               "FLOW_HOME=/orfs/flow DESIGN_CONFIG=/inputs/config.mk WORK_HOME=/work "
               f"NUM_CORES={args.threads} FLOW_VARIANT={args.attempt} "
               f"OPENROAD_EXE={OPENROAD} YOSYS_EXE={YOSYS} {target}"]
    return name, command


def execute(args, work, target, logfile):
    name, command = docker_command(args, work, target)
    print("Running", target, "with", args.threads, "threads; log:", logfile, flush=True)
    with logfile.open("w") as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=args.timeout_minutes * 60)
            return result.returncode
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            subprocess.run(["docker", "stop", "--time", "10", name], check=False)
            raise


def summarize(work, attempt):
    results = work / f"results/asap7/picorv32_autofix/{attempt}"
    reports = work / f"reports/asap7/picorv32_autofix/{attempt}"
    logs = work / f"logs/asap7/picorv32_autofix/{attempt}"
    final = {ext: str((results / f"6_final.{ext}").relative_to(work))
             for ext in REQUIRED if (results / f"6_final.{ext}").is_file()
             and (results / f"6_final.{ext}").stat().st_size > 0}
    summary = {"final": final, "missing_artifacts": sorted(set(REQUIRED) - final.keys()),
               "lvs": "not_run", "functional_verification": "not_run"}
    metrics = logs / "6_report.json"
    if metrics.exists():
        summary["final_metrics"] = json.loads(metrics.read_text())
    drc = reports / "6_drc.lyrdb"
    if drc.exists():
        tree = ET.parse(drc)
        counts = collections.Counter(item.findtext("category") for item in tree.findall(".//items/item"))
        summary["public_drc"] = {"status": "complete", "items": sum(counts.values()),
                                 "categories": dict(sorted(counts.items())),
                                 "report": str(drc.relative_to(work)),
                                 "scope": "Pinned public ASAP7 deck; research audit, not foundry signoff"}
    else:
        summary["public_drc"] = {"status": "not_run"}
    return summary


def report_counts(path):
    counts = collections.Counter()
    for _, element in ET.iterparse(path, events=("end",)):
        if element.tag == "item":
            counts[element.findtext("category")] += 1
            element.clear()
    return {"items": sum(counts.values()), "categories": dict(sorted(counts.items()))}


def audit(args):
    """Audit a frozen GDS independently of the RTL-to-GDS resource settings."""
    verified_toolchain(args.output)
    work = args.output / "runs" / args.attempt
    receipt_path = work / "run.json"
    with exclusive(args.output / ".run.lock"):
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("flow_exit_code") != 0 or receipt.get("missing_artifacts"):
            raise ValueError("The RTL-to-GDS flow must complete before an independent audit")
        gds = work / receipt["final"]["gds"]
        if sha256(gds) != receipt["artifacts"][receipt["final"]["gds"]]:
            raise ValueError("Baseline GDS changed")
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        available = int(mem["MemAvailable"].split()[0]) / 1024**2
        if available < args.memory_gib + 0.5:
            raise ValueError(f"Need {args.memory_gib + 0.5:.1f} GiB available RAM; have {available:.1f}")
        deck = (args.output / "orfs/flow/platforms/asap7/drc/asap7.lydrc" if args.profile == "public"
                else PROJECT / "test_data/rules/asap7_c2c3_v1.lydrc")
        previous = [int(p.name.rsplit("_", 1)[-1]) for p in (work / "audits").glob("*_[0-9][0-9][0-9]")
                    if p.is_dir()]
        directory = work / "audits" / f"{args.profile}_{max(previous, default=0) + 1:03d}"
        directory.mkdir(parents=True)
        shutil.copy2(deck, directory / "deck.lydrc")
        name = f"picorv32-audit-{args.attempt}-{os.getpid()}"
        command = ["docker", "run", "--rm", "--name", name, "--network=none",
                   f"--cpus={args.threads}", f"--memory={args.memory_gib}g",
                   f"--memory-swap={args.memory_gib}g", "--user", f"{os.getuid()}:{os.getgid()}",
                   "--mount", f"type=bind,src={work},dst=/work,readonly",
                   "--mount", f"type=bind,src={directory},dst=/audit",
                   "--entrypoint", "bash", IMAGE, "-lc",
                   "source /OpenROAD-flow-scripts/env.sh; exec /usr/bin/time -v klayout -b -r /audit/deck.lydrc "
                   f"-rd in_gds=/work/{receipt['final']['gds']} -rd report_file=/audit/report.lyrdb"]
        result = {"profile": args.profile, "status": "running", "started_at": utc_now(),
                  "directory": str(directory.relative_to(work)), "image": IMAGE,
                  "deck_sha256": sha256(deck), "gds_sha256": sha256(gds),
                  "memory_gib": args.memory_gib, "threads": args.threads, "command": command}
        write_json(directory / "audit.json", result)
        print("Running independent", args.profile, "audit:", directory, flush=True)
        started = time.monotonic()
        try:
            with (directory / "audit.log").open("w") as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                         timeout=args.timeout_minutes * 60)
            result["exit_code"] = process.returncode
            report = directory / "report.lyrdb"
            if process.returncode == 0 and report.is_file():
                result.update(report_counts(report), status="complete",
                              report=str(report.relative_to(work)), report_sha256=sha256(report))
            else:
                result["status"] = "failed"
                if process.returncode in (137, -9):
                    result["reason"] = "KLayout was killed at the container memory limit"
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            subprocess.run(["docker", "stop", "--time", "10", name], check=False)
            result["status"] = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "interrupted"
        except (OSError, ET.ParseError) as exc:
            result.update(status="failed", reason=str(exc))
        result.update(finished_at=utc_now(), wall_seconds=round(time.monotonic() - started, 3))
        write_json(directory / "audit.json", result)
        receipt.setdefault("audits", []).append(result)
        receipt["flow_status"] = "complete"
        if receipt.get("drc_exit_code") and receipt["public_drc"]["status"] == "not_run":
            receipt["public_drc"] = {"status": "failed", "exit_code": receipt["drc_exit_code"],
                                      "log": "drc.log", "reason": "See retained original audit log"}
        key = "public_drc" if args.profile == "public" else "beol_drc"
        receipt[key] = {k: v for k, v in result.items() if k != "command"}
        if args.profile == "public" and result["status"] == "complete":
            receipt["status"] = "complete"
        receipt["artifacts"].update(file_hashes_relative(directory, work))
        write_json(receipt_path, receipt)
        print(json.dumps({k: result.get(k) for k in ("status", "profile", "items", "directory", "reason")}, indent=2))
        if result["status"] != "complete":
            raise SystemExit(1)


def file_hashes_relative(directory, root):
    return {str(p.relative_to(root)): sha256(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def run(args):
    verified_toolchain(args.output)
    source_hashes()
    work = args.output / "runs" / args.attempt
    work.mkdir(parents=True, exist_ok=True)
    with exclusive(args.output / ".run.lock"):
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        available = int(mem["MemAvailable"].split()[0]) / 1024**2
        if available < args.memory_gib + 0.5:
            raise ValueError(f"Need {args.memory_gib + 0.5:.1f} GiB available RAM; have {available:.1f}")
        receipt_path = work / "run.json"
        if receipt_path.exists() and not args.resume:
            raise ValueError("Attempt already exists. Use --resume or a new --attempt name")
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt["input_hashes"] != file_hashes(work / "inputs"):
                raise ValueError("Saved input snapshot changed")
            current = {name: sha256(HERE / name) for name in receipt["input_hashes"]}
            if current != receipt["input_hashes"]:
                raise ValueError("Flow inputs changed. Use a new --attempt to retain the old run")
            if receipt["resources"] != {"threads": args.threads, "memory_gib": args.memory_gib}:
                raise ValueError("Resume with the original resource settings")
            if receipt["toolchain_sha256"] != sha256(args.output / "toolchain.json"):
                raise ValueError("Prepared toolchain receipt changed")
            if receipt.get("flow_exit_code") == 0 and not receipt.get("missing_artifacts"):
                for name, digest in receipt["artifacts"].items():
                    path = work / name
                    if not path.is_file() or sha256(path) != digest:
                        raise ValueError("Completed run artifact changed: " + name)
                print("Completed RTL-to-GDS run verified:", receipt_path)
                return
        else:
            inputs = work / "inputs"
            inputs.mkdir()
            for name in ("config.mk", "constraint.sdc", "sources.lock.json"):
                shutil.copy2(HERE / name, inputs / name)
            shutil.copytree(HERE / "rtl", inputs / "rtl")
            receipt = {"schema_version": 1, "attempt": args.attempt, "started_at": utc_now(),
                       "image": IMAGE, "orfs_commit": ORFS_COMMIT, "rtl_commit": RTL_COMMIT,
                       "toolchain_sha256": sha256(args.output / "toolchain.json"),
                       "input_hashes": file_hashes(inputs),
                       "resources": {"threads": args.threads, "memory_gib": args.memory_gib},
                       "history": []}
        receipt["status"] = "running"
        write_json(receipt_path, receipt)
        started = time.monotonic()
        try:
            code = execute(args, work, "all", work / "flow.log")
            receipt["flow_exit_code"] = code
            receipt.update(summarize(work, args.attempt))
            receipt["flow_status"] = "failed" if code or receipt["missing_artifacts"] else "complete"
            if code or receipt["missing_artifacts"]:
                receipt["status"] = "flow_failed"
            else:
                receipt["status"] = "gds_generated"
        except subprocess.TimeoutExpired:
            receipt["status"] = "timeout"
        except KeyboardInterrupt:
            receipt["status"] = "interrupted"
        except Exception as exc:
            receipt.update(status="error", error=str(exc))
        receipt["history"].append({"finished_at": utc_now(), "status": receipt["status"],
                                   "wall_seconds": round(time.monotonic() - started, 3)})
        receipt["artifacts"] = {str(p.relative_to(work)): sha256(p)
                                for p in sorted(work.rglob("*")) if p.is_file()
                                and p != receipt_path and p.suffix != ".tmp"}
        write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path),
                          "final": receipt.get("final"), "public_drc": receipt.get("public_drc")}, indent=2))
        if receipt["status"] not in ("complete", "gds_generated"):
            raise SystemExit(1)


def status(args):
    work = args.output / "runs" / args.attempt
    receipt = json.loads((work / "run.json").read_text())
    print(json.dumps({key: receipt.get(key) for key in
                     ("status", "flow_status", "attempt", "history", "final", "missing_artifacts", "public_drc", "beol_drc")}, indent=2))


def verify(args):
    verified_toolchain(args.output)
    source_hashes()
    work = args.output / "runs" / args.attempt
    receipt = json.loads((work / "run.json").read_text())
    for name, digest in receipt["artifacts"].items():
        path = work / name
        if not path.is_file() or sha256(path) != digest:
            raise ValueError("Run artifact changed: " + name)
    if file_hashes(work / "inputs") != receipt["input_hashes"]:
        raise ValueError("Input snapshot changed")
    if sha256(args.output / "toolchain.json") != receipt["toolchain_sha256"]:
        raise ValueError("Toolchain receipt changed")
    print(json.dumps({"status": "verified", "artifacts": len(receipt["artifacts"]),
                      "flow_exit_code": receipt.get("flow_exit_code"),
                      "gds_sha256": sha256(work / receipt["final"]["gds"])}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Fetch pinned ORFS and check the container")
    prep.add_argument("--orfs-source", type=Path, help="Copy an existing independent ORFS checkout")
    build = sub.add_parser("run", help="Run RTL through final GDS; use audit for DRC")
    build.add_argument("--attempt", default="baseline")
    build.add_argument("--resume", action="store_true")
    build.add_argument("--threads", type=int, default=2)
    build.add_argument("--memory-gib", type=int, default=4)
    build.add_argument("--timeout-minutes", type=int, default=60)
    build.add_argument("--skip-drc", action="store_true", help=argparse.SUPPRESS)
    report = sub.add_parser("status")
    report.add_argument("--attempt", default="baseline")
    validate = sub.add_parser("verify", help="Verify saved toolchain, input, and output hashes")
    validate.add_argument("--attempt", default="baseline")
    check = sub.add_parser("audit", help="Check an existing GDS with a separate memory and time limit")
    check.add_argument("--attempt", default="baseline")
    check.add_argument("--profile", choices=("public", "beol"), default="public")
    check.add_argument("--threads", type=int, default=2)
    check.add_argument("--memory-gib", type=int, default=4)
    check.add_argument("--timeout-minutes", type=int, default=30)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if hasattr(args, "attempt") and not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", args.attempt):
        parser.error("Attempt must start with a lowercase letter and contain letters, digits, or underscores")
    if args.command in ("run", "audit") and min(args.threads, args.memory_gib, args.timeout_minutes) < 1:
        parser.error("Resources and timeout must be positive")
    try:
        {"prepare": prepare, "run": run, "status": status, "audit": audit, "verify": verify}[args.command](args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Flow error: {exc}\n")


if __name__ == "__main__":
    main()
