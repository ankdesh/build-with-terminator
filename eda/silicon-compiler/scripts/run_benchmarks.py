#!/usr/bin/env python3
"""Generate and run synthesis flows for lsils/benchmarks arithmetic tests."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_synthesis import (  # noqa: E402
    REPO_ROOT,
    TARGETS,
    _ensure_local_yosys_on_path,
    _materialize_liberty,
    _target_liberty_files,
    build_project,
)

CONFIG = REPO_ROOT / "config" / "benchmark_synthesis.json"
BUILD_DIR = REPO_ROOT / "build" / "benchmarks"
RESULTS_DIR = REPO_ROOT / "results" / "benchmarks"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        config = json.load(f)
    for key in ("benchmark_root", "topmodule", "benchmarks", "dc"):
        if key not in config:
            raise ValueError(f"Missing required benchmark config key: {key}")
    return config


def _repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def benchmark_names(config: dict[str, Any], requested: str) -> list[str]:
    names = list(config["benchmarks"].keys())
    if requested == "all":
        return names
    if requested not in config["benchmarks"]:
        raise ValueError(f"Unknown benchmark '{requested}'. Choose one of: all, {', '.join(names)}")
    return [requested]


def target_names(requested: str) -> list[str]:
    if requested == "all":
        return list(TARGETS.keys())
    if requested not in TARGETS:
        raise ValueError(f"Unknown target '{requested}'. Choose one of: all, {', '.join(TARGETS)}")
    return [requested]


def benchmark_rtl(config: dict[str, Any], benchmark: str) -> Path:
    root = _repo_path(config["benchmark_root"])
    rtl = root / config["benchmarks"][benchmark]["rtl"]
    if not rtl.exists():
        raise FileNotFoundError(f"Benchmark RTL not found: {rtl}")
    return rtl


def _liberty_files(target: str, workdir: Path, clock_period_ns: float) -> list[Path]:
    project = build_project(target, clock_period_ns, jobname=f"bench_{target}")
    return [_materialize_liberty(path, workdir) for path in _target_liberty_files(project)]


def _parse_yosys_stat(stat_path: Path, topmodule: str) -> dict[str, float | int | None]:
    raw = json.loads(stat_path.read_text(encoding="utf-8"))
    design = raw.get("design", raw)
    modules = design.get("modules", {}) if isinstance(design, dict) else {}
    top = modules.get(f"\\{topmodule}") or modules.get(topmodule) or design
    return {
        "cellarea": top.get("area") if isinstance(top, dict) else None,
        "cells": top.get("num_cells") if isinstance(top, dict) else None,
        "nets": top.get("num_wire_bits") if isinstance(top, dict) else None,
        "pins": top.get("num_port_bits") if isinstance(top, dict) else None,
    }


def run_yosys(config: dict[str, Any], benchmark: str, target: str) -> dict[str, Any]:
    _ensure_local_yosys_on_path()
    topmodule = config["topmodule"]
    clock_period_ns = float(config.get("clock_period_ns", 10.0))
    rtl = benchmark_rtl(config, benchmark)
    workdir = BUILD_DIR / "yosys" / target / benchmark
    reports = workdir / "reports"
    outputs = workdir / "outputs"
    for folder in (reports, outputs):
        folder.mkdir(parents=True, exist_ok=True)

    liberty_files = _liberty_files(target, workdir, clock_period_ns)
    liberty_args = " ".join(f"-liberty {path}" for path in liberty_files)
    script = workdir / "synth.ys"
    stat_json = reports / "stat.json"
    netlist_v = outputs / f"{benchmark}_{target}.vg"
    netlist_json = outputs / f"{benchmark}_{target}.netlist.json"
    script.write_text("\n".join([
        *(f"read_liberty -lib {liberty}" for liberty in liberty_files),
        f"read_verilog -sv {rtl}",
        f"hierarchy -check -top {topmodule}",
        f"synth -flatten -top {topmodule}",
        f"abc {liberty_args}",
        "clean -purge",
        f"tee -o {stat_json} stat -json {liberty_args} -top {topmodule}",
        f"write_verilog -noattr -noexpr -nohex -nodec {netlist_v}",
        f"write_json {netlist_json}",
        "",
    ]), encoding="utf-8")

    log_path = workdir / "yosys.log"
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "yosys"), "-s", str(script)],
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Yosys failed for {benchmark}/{target}; see {log_path}")

    metrics = _parse_yosys_stat(stat_json, topmodule)
    report = {
        "benchmark": benchmark,
        "description": config["benchmarks"][benchmark].get("description"),
        "category": config.get("category"),
        "tool": "yosys",
        "target": target,
        "status": "pass",
        "topmodule": topmodule,
        "rtl": str(rtl),
        "liberty": [str(path) for path in liberty_files],
        "artifacts": {
            "workdir": str(workdir),
            "yosys_script": str(script),
            "yosys_log": str(log_path),
            "stat_json": str(stat_json),
            "netlist_verilog": str(netlist_v),
            "netlist_json": str(netlist_json),
        },
        "metrics": {"errors": 0, **metrics},
    }
    outdir = RESULTS_DIR / "yosys" / target
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{benchmark}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _quote_tcl(value: str | Path) -> str:
    return "{" + str(value).replace("}", "\\}") + "}"


def _write_dc_tcl(config: dict[str, Any], benchmark: str, target: str, rtl: Path, liberty_files: list[Path], workdir: Path) -> Path:
    topmodule = config["topmodule"]
    dc_cfg = config["dc"]
    compile_cfg = dc_cfg.get("compile", {})
    constraints = dc_cfg.get("constraints", {})
    reports = workdir / "reports"
    outputs = workdir / "outputs"
    scripts = workdir / "scripts"
    for folder in (reports, outputs, scripts):
        folder.mkdir(parents=True, exist_ok=True)

    search_dirs = sorted({str(rtl.parent)} | {str(path.parent) for path in liberty_files})
    link_libs = ["*"] + [str(path) for path in liberty_files]
    compile_command = compile_cfg.get("command", "compile_ultra")
    compile_args = []
    if compile_command == "compile_ultra" and not compile_cfg.get("ungroup", False):
        compile_args.append("-no_autoungroup")
    if compile_cfg.get("incremental", False):
        compile_args.append("-incremental")

    lines = [
        "# Auto-generated by scripts/run_benchmarks.py. Edit config/benchmark_synthesis.json, not this file.",
        f"set DESIGN_NAME {_quote_tcl(benchmark)}",
        f"set TOP_MODULE {_quote_tcl(topmodule)}",
        f"set TARGET_NAME {_quote_tcl(target)}",
        f"set REPORT_DIR {_quote_tcl(reports)}",
        f"set OUTPUT_DIR {_quote_tcl(outputs)}",
        "file mkdir $REPORT_DIR",
        "file mkdir $OUTPUT_DIR",
        "",
        "set_app_var search_path [concat $search_path [list \\",
        *[f"    {_quote_tcl(path)} \\" for path in search_dirs],
        "] ]",
        f"set_app_var target_library [list {' '.join(_quote_tcl(path) for path in liberty_files)}]",
        f"set_app_var link_library [list {' '.join(_quote_tcl(path) for path in link_libs)}]",
        "",
        f"analyze -format verilog [list {_quote_tcl(rtl)}]",
        "elaborate $TOP_MODULE",
        "current_design $TOP_MODULE",
        "link",
        "uniquify",
        f"create_clock -name virtual_clock -period {float(constraints.get('combinational_max_delay_ns', 10.0))}",
        f"set_max_delay {float(constraints.get('combinational_max_delay_ns', 10.0))} -from [all_inputs] -to [all_outputs]",
        f"set_input_delay {float(constraints.get('input_delay_ns', 0.0))} -clock virtual_clock [all_inputs]",
        f"set_output_delay {float(constraints.get('output_delay_ns', 0.0))} -clock virtual_clock [all_outputs]",
        "check_design > $REPORT_DIR/check_design.rpt",
        f"{compile_command} {' '.join(compile_args)}".rstrip(),
        "report_qor > $REPORT_DIR/qor.rpt",
        "report_area -hierarchy > $REPORT_DIR/area.rpt",
        "report_timing -max_paths 20 > $REPORT_DIR/timing.rpt",
        "report_power > $REPORT_DIR/power.rpt",
        "write -format verilog -hierarchy -output $OUTPUT_DIR/${DESIGN_NAME}_${TARGET_NAME}.vg",
        "write -format ddc -hierarchy -output $OUTPUT_DIR/${DESIGN_NAME}_${TARGET_NAME}.ddc",
        "write_sdc $OUTPUT_DIR/${DESIGN_NAME}_${TARGET_NAME}.sdc",
        "exit",
        "",
    ]
    out = scripts / "dc_synth.tcl"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def preflight_dc(config: dict[str, Any], benchmark: str, target: str) -> dict[str, Any]:
    clock_period_ns = float(config.get("clock_period_ns", 10.0))
    rtl = benchmark_rtl(config, benchmark)
    workdir = BUILD_DIR / "dc" / target / benchmark
    workdir.mkdir(parents=True, exist_ok=True)
    liberty_files = _liberty_files(target, workdir, clock_period_ns)
    tcl = _write_dc_tcl(config, benchmark, target, rtl, liberty_files, workdir)

    dc_cfg = config["dc"]
    dc_shell_bin = dc_cfg.get("dc_shell_bin", "dc_shell")
    dc_shell_path = shutil.which(dc_shell_bin) if dc_shell_bin else None
    license_env = dc_cfg.get("license_env", {})
    license_status = {key: bool(value or os.environ.get(key)) for key, value in license_env.items()}
    checks = {
        "rtl_files_exist": rtl.exists(),
        "liberty_files_exist": all(path.exists() for path in liberty_files),
        "dc_shell_found": bool(dc_shell_path),
        "license_env_present": any(license_status.values()) if license_status else False,
        "tcl_generated": tcl.exists(),
    }
    runnable = checks["rtl_files_exist"] and checks["liberty_files_exist"] and checks["dc_shell_found"] and checks["license_env_present"]
    report = {
        "benchmark": benchmark,
        "description": config["benchmarks"][benchmark].get("description"),
        "category": config.get("category"),
        "tool": "dc",
        "target": target,
        "status": "ready_to_run" if runnable else "preflight_only",
        "topmodule": config["topmodule"],
        "checks": checks,
        "dc_shell_bin": dc_shell_bin,
        "dc_shell_path": dc_shell_path,
        "license_env": license_status,
        "rtl": str(rtl),
        "liberty": [str(path) for path in liberty_files],
        "artifacts": {
            "workdir": str(workdir),
            "dc_tcl": str(tcl),
            "reports_dir": str(workdir / "reports"),
            "outputs_dir": str(workdir / "outputs"),
        },
        "metrics": {},
    }
    outdir = RESULTS_DIR / "dc" / target
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{benchmark}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def compare_results(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for tool_dir in (RESULTS_DIR / "yosys", RESULTS_DIR / "dc"):
        if not tool_dir.exists():
            continue
        for result_file in sorted(tool_dir.glob("*/*.json")):
            data = json.loads(result_file.read_text(encoding="utf-8"))
            metrics = data.get("metrics", {})
            rows.append({
                "benchmark": data.get("benchmark"),
                "description": data.get("description"),
                "tool": data.get("tool"),
                "target": data.get("target"),
                "status": data.get("status"),
                "cells": metrics.get("cells"),
                "cellarea": metrics.get("cellarea"),
                "nets": metrics.get("nets"),
                "pins": metrics.get("pins"),
                "result_file": str(result_file),
            })
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "comparison.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (RESULTS_DIR / "comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["benchmark", "description", "tool", "target", "status", "cells", "cellarea", "nets", "pins", "result_file"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--benchmark", default="all", help="Benchmark name or all.")
    parser.add_argument("--target", default="freepdk45", help="Target PDK/library or all.")
    parser.add_argument("--tool", choices=("yosys", "dc", "both", "compare"), default="both")
    parser.add_argument("--run-dc", action="store_true", help="Reserved for future DC execution; currently preflight only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.tool == "compare":
        rows = compare_results(config)
        print(f"Wrote comparison with {len(rows)} rows to {RESULTS_DIR}")
        return 0

    reports = []
    for target in target_names(args.target):
        for benchmark in benchmark_names(config, args.benchmark):
            if args.tool in ("yosys", "both"):
                reports.append(run_yosys(config, benchmark, target))
            if args.tool in ("dc", "both"):
                reports.append(preflight_dc(config, benchmark, target))
                if args.run_dc:
                    raise RuntimeError("DC execution is not implemented until dc_shell/license are available; use generated Tcl.")
    compare_results(config)
    print(f"Processed {len(reports)} benchmark/tool result(s). Results: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
