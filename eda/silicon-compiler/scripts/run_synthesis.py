#!/usr/bin/env python3
"""Run a SiliconCompiler/Yosys logic-synthesis-only flow for sample RTL."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from siliconcompiler import ASIC, Design, Flowgraph
from siliconcompiler.tools.yosys import syn_asic

from lambdapdk.asap7.libs.asap7sc7p5t import ASAP7SC7p5LVT, ASAP7SC7p5RVT, ASAP7SC7p5SLVT
from lambdapdk.freepdk45.libs.nangate45 import Nangate45
from lambdapdk.sky130.libs.sky130sc import Sky130_SCHDLibrary

import siliconcompiler.utils.multiprocessing as sc_multiprocessing


REPO_ROOT = Path(__file__).resolve().parents[1]
RTL = REPO_ROOT / "rtl" / "mac_unit.v"
RESULTS_DIR = REPO_ROOT / "results"
DIRECT_BUILD_DIR = REPO_ROOT / "build" / "direct"


def _ensure_local_yosys_on_path() -> None:
    os.environ["PATH"] = f"{REPO_ROOT / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"


def _force_tcp_manager() -> None:
    """Use TCP for SiliconCompiler's manager when Unix sockets are unavailable."""

    base_manager = sc_multiprocessing.SyncManager

    class TCPSyncManager(base_manager):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("address", ("127.0.0.1", 0))
            super().__init__(*args, **kwargs)

    if sc_multiprocessing.SyncManager is not TCPSyncManager:
        sc_multiprocessing.SyncManager = TCPSyncManager


def _make_design() -> Design:
    design = Design("mac_unit")
    design.set_dataroot("local", str(REPO_ROOT))
    with design.active_dataroot("local"), design.active_fileset("rtl"):
        design.set_topmodule("mac_unit")
        design.add_file("rtl/mac_unit.v")
    return design


def _add_synthesis_scenario(project: ASIC, corner: str = "typical") -> None:
    scenario = project.constraint.timing.make_scenario("synthesis")
    scenario.add_libcorner([corner, "generic"])
    scenario.add_check("setup")
    project.set_asic_delaymodel("nldm")


def _configure_freepdk45(project: ASIC) -> None:
    project.set_mainlib(Nangate45())
    project.set_pdk("freepdk45")
    _add_synthesis_scenario(project, "typical")


def _configure_sky130(project: ASIC) -> None:
    project.set_mainlib(Sky130_SCHDLibrary())
    project.set_pdk("skywater130")
    _add_synthesis_scenario(project, "slow")


def _configure_asap7(project: ASIC) -> None:
    project.set_mainlib(ASAP7SC7p5RVT())
    project.add_asiclib(ASAP7SC7p5LVT())
    project.add_asiclib(ASAP7SC7p5SLVT())
    project.set_pdk("asap7")
    _add_synthesis_scenario(project, "slow")


TARGETS: dict[str, Callable[[ASIC], None]] = {
    "freepdk45": _configure_freepdk45,
    "sky130": _configure_sky130,
    "asap7": _configure_asap7,
}


def build_project(target: str, clock_period_ns: float, jobname: str | None = None) -> ASIC:
    if target not in TARGETS:
        raise ValueError(f"Unsupported target '{target}'. Choose one of: {', '.join(TARGETS)}")

    _force_tcp_manager()
    design = _make_design()
    project = ASIC(design)
    project.add_fileset("rtl")
    TARGETS[target](project)

    flow = Flowgraph("yosys_logic_synthesis")
    synthesis = syn_asic.ASICSynthesis()
    synthesis.set_yosys_abcclockperiod(clock_period_ns * 1000.0)
    flow.node("synthesis", synthesis)
    project.set_flow(flow)

    project.set("option", "jobname", jobname or target)
    project.set("option", "builddir", str(REPO_ROOT / "build"))
    project.set("option", "quiet", True)
    return project



def _target_liberty_files(project: ASIC, corner: str | None = None) -> list[Path]:
    libname = project.get("asic", "mainlib")
    library = project.get_library(libname)
    delaymodel = project.get("asic", "delaymodel")
    available_corners = list(library.getkeys("asic", "libcornerfileset"))
    if not available_corners:
        raise RuntimeError(f"No Liberty corners found for library {libname}")
    selected_corner = corner if corner in available_corners else available_corners[0]
    filesets = library.get("asic", "libcornerfileset", selected_corner, delaymodel)
    liberty_files: list[Path] = []
    for fileset in filesets:
        liberty_files.extend(Path(path) for path in library.find_files("fileset", fileset, "file", "liberty"))
    if not liberty_files:
        raise RuntimeError(f"No Liberty files resolved for {libname}/{selected_corner}/{delaymodel}")
    return liberty_files



def _materialize_liberty(liberty: Path, workdir: Path) -> Path:
    inputs = workdir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    if liberty.suffix == ".gz":
        out = inputs / liberty.with_suffix("").name
        with gzip.open(liberty, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return out
    return liberty


def _parse_yosys_stat(stat_path: Path) -> dict[str, float | int | None]:
    raw = json.loads(stat_path.read_text(encoding="utf-8"))
    design = raw.get("design", raw)
    modules = design.get("modules", {}) if isinstance(design, dict) else {}
    top = modules.get("\\mac_unit") or modules.get("mac_unit") or design
    return {
        "cellarea": top.get("area") if isinstance(top, dict) else None,
        "cells": top.get("num_cells") if isinstance(top, dict) else None,
        "nets": top.get("num_wire_bits") if isinstance(top, dict) else None,
        "pins": top.get("num_port_bits") if isinstance(top, dict) else None,
        "registers": None,
    }


def run_direct_yosys(project: ASIC, target: str, clock_period_ns: float) -> Path:
    _ensure_local_yosys_on_path()
    workdir = DIRECT_BUILD_DIR / target
    reports = workdir / "reports"
    outputs = workdir / "outputs"
    reports.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    liberty_files = [_materialize_liberty(path, workdir) for path in _target_liberty_files(project)]
    liberty_args = " ".join(f"-liberty {path}" for path in liberty_files)
    script = workdir / "synth.ys"
    stat_json = reports / "stat.json"
    netlist_v = outputs / "mac_unit.vg"
    netlist_json = outputs / "mac_unit.netlist.json"
    script.write_text("\n".join([
        *(f"read_liberty -lib {liberty}" for liberty in liberty_files),
        f"read_verilog -sv {RTL}",
        "synth -flatten -top mac_unit",
        f"dfflibmap {liberty_args}",
        f"abc -D {clock_period_ns * 1000.0:.3f} {liberty_args}",
        "clean -purge",
        f"tee -o {stat_json} stat -json {liberty_args} -top mac_unit",
        f"write_verilog -noattr -noexpr -nohex -nodec {netlist_v}",
        f"write_json {netlist_json}",
        "",
    ]), encoding="utf-8")

    log_path = workdir / "yosys.log"
    yosys = REPO_ROOT / "bin" / "yosys"
    result = subprocess.run(
        [str(yosys), "-s", str(script)],
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Yosys failed for {target}; see {log_path}")

    metrics = _parse_yosys_stat(stat_json)
    report = {
        "design": "mac_unit",
        "target": target,
        "flow": "direct_yowasp_yosys_logic_synthesis",
        "topmodule": "mac_unit",
        "clock_period_ns": clock_period_ns,
        "liberty": [str(path) for path in liberty_files],
        "artifacts": {
            "workdir": str(workdir),
            "yosys_script": str(script),
            "yosys_log": str(log_path),
            "netlist_verilog": str(netlist_v),
            "netlist_json": str(netlist_json),
            "stat_json": str(stat_json),
        },
        "metrics": {"errors": 0, "warnings": None, **metrics},
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{target}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def summarize(project: ASIC, target: str) -> Path:
    metrics = {}
    for metric in ("errors", "warnings", "cells", "cellarea", "registers", "nets", "pins"):
        try:
            value = project.get("metric", metric, step="synthesis", index=0)
        except Exception:
            value = None
        metrics[metric] = value

    report = {
        "design": "mac_unit",
        "target": target,
        "flow": "yosys_logic_synthesis",
        "topmodule": "mac_unit",
        "metrics": metrics,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{target}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS),
        default="freepdk45",
        help="PDK/library target to use for synthesis.",
    )
    parser.add_argument(
        "--clock-period-ns",
        type=float,
        default=10.0,
        help="Clock period passed to Yosys ABC in nanoseconds.",
    )
    parser.add_argument(
        "--runner",
        choices=("direct", "sc"),
        default="direct",
        help="Use direct yowasp-yosys script or SiliconCompiler stock scheduler task.",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip SiliconCompiler's text summary after the run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ensure_local_yosys_on_path()
    project = build_project(args.target, args.clock_period_ns)
    if args.runner == "sc":
        project.run()
        result_path = summarize(project, args.target)
        if not args.no_summary:
            project.summary()
    else:
        result_path = run_direct_yosys(project, args.target, args.clock_period_ns)
    print(f"Wrote {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

