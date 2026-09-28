#!/usr/bin/env python3
"""Top-Level Master Pipeline Runner for Rule2DRC & Sky130 Assets.

This script orchestrates and executes all download, extraction, and statistical
analysis scripts generated in this project:
1. 'download_dataset.py' - Downloads Rule2DRC tasks (DRC decks) & testcases
2. 'extract_gds.py'      - Extracts 13,921 binary GDS layouts from Parquet
3. 'sky130_gds_stats.py' - Queries & tabulates SkyWater 130nm HD standard cell GDS stats
4. 'download_large_gds.py' (Optional) - Downloads large Sky130 production GDS layouts
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ==============================================================================
# Centralized Hoisted Constants
# ==============================================================================
SCRIPTS_DIR: Path = Path("scripts")

SCRIPT_DOWNLOAD_DATASET: Path = SCRIPTS_DIR / "download_dataset.py"
SCRIPT_EXTRACT_GDS: Path = SCRIPTS_DIR / "extract_gds.py"
SCRIPT_SKY130_STATS: Path = SCRIPTS_DIR / "sky130_gds_stats.py"
SCRIPT_DOWNLOAD_LARGE_GDS: Path = SCRIPTS_DIR / "download_large_gds.py"

console = Console()
error_console = Console(stderr=True)


# ==============================================================================
# Domain Exceptions
# ==============================================================================
class PipelineError(Exception):
    """Base exception for pipeline execution failures."""


class StepExecutionError(PipelineError):
    """Raised when an individual pipeline step exits with non-zero status."""


# ==============================================================================
# Data Models
# ==============================================================================
@dataclass
class StepResult:
    """Outcome and execution metadata for a single pipeline step."""

    name: str
    script_path: Path
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    duration_seconds: float
    output_artifacts: str


# ==============================================================================
# Pipeline Runner Implementation (One Primary Class)
# ==============================================================================
class MasterPipelineRunner:
    """Coordinates and executes all Rule2DRC and Sky130 tooling scripts."""

    def __init__(
        self,
        include_large_gds: bool = False,
        large_target: str = "user_proj_example",
        skip_download: bool = False,
        skip_extract: bool = False,
        skip_stats: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Initialize runner options."""
        self.include_large_gds = include_large_gds
        self.large_target = large_target
        self.skip_download = skip_download
        self.skip_extract = skip_extract
        self.skip_stats = skip_stats
        self.dry_run = dry_run
        self.python_executable = sys.executable

    def _execute_step(
        self,
        name: str,
        script: Path,
        args: list[str],
        artifact_desc: str,
        skip: bool = False,
    ) -> StepResult:
        """Execute a single script step with timing and error handling."""
        if skip:
            console.log(f"[dim]Skipping step: {name}[/dim]")
            return StepResult(name, script, "SKIPPED", 0.0, artifact_desc)

        console.print(f"\n[bold cyan]━━━ Running Step: {name} ━━━[/bold cyan]")
        console.log(f"Script: [green]{script}[/green] Args: [yellow]{args}[/yellow]")

        if self.dry_run:
            console.log("[yellow]Dry run active: step simulated successfully.[/yellow]")
            return StepResult(name, script, "SUCCESS (Dry-Run)", 0.0, artifact_desc)

        if not script.exists():
            raise StepExecutionError(f"Script not found at: {script.resolve()}")

        start_time = time.perf_counter()
        cmd = [self.python_executable, str(script), *args]

        try:
            # Run directly with inherited terminal stdio for rich output
            proc = subprocess.run(cmd, check=False)
            elapsed = time.perf_counter() - start_time

            if proc.returncode != 0:
                console.print(
                    f"[bold red]Step '{name}' failed with exit code {proc.returncode}[/bold red]"
                )
                return StepResult(name, script, "FAILED", elapsed, artifact_desc)

            return StepResult(name, script, "SUCCESS", elapsed, artifact_desc)
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            raise StepExecutionError(f"Step '{name}' encountered an exception: {exc}") from exc

    def run(self) -> list[StepResult]:
        """Execute all configured steps in deterministic order."""
        results: list[StepResult] = []

        # Step 1: Download Benchmark Dataset (Tasks & Testcases Parquet)
        res_dl = self._execute_step(
            name="1. Download Rule2DRC Dataset & DRC Decks",
            script=SCRIPT_DOWNLOAD_DATASET,
            args=[],
            artifact_desc="data/tasks.parquet (DRC Decks), data/testcases.parquet",
            skip=self.skip_download,
        )
        results.append(res_dl)

        # Step 2: Extract Binary GDS Layouts
        res_ext = self._execute_step(
            name="2. Extract Binary GDS Layouts & Size Stats",
            script=SCRIPT_EXTRACT_GDS,
            args=[],
            artifact_desc="data/extracted_gds/ (13,921 layout files)",
            skip=self.skip_extract,
        )
        results.append(res_ext)

        # Step 3: SkyWater 130nm HD Standard Cell Stats
        res_stats = self._execute_step(
            name="3. Collect SkyWater 130nm HD Library Stats",
            script=SCRIPT_SKY130_STATS,
            args=[],
            artifact_desc="docs/sky130_fd_sc_hd_gds_stats.md",
            skip=self.skip_stats,
        )
        results.append(res_stats)

        # Step 4: (Optional) Large Sky130 Production GDS Download
        large_args = ["--targets", self.large_target]
        res_large = self._execute_step(
            name="4. Download Production Large Sky130 GDS",
            script=SCRIPT_DOWNLOAD_LARGE_GDS,
            args=large_args,
            artifact_desc=f"data/large_gds/ ({self.large_target}.gds)",
            skip=not self.include_large_gds,
        )
        results.append(res_large)

        return results


# ==============================================================================
# Presentation Helper
# ==============================================================================
def display_pipeline_summary(results: list[StepResult]) -> None:
    """Print consolidated pipeline summary table."""
    table = Table(
        title="Rule2DRC & Sky130 Pipeline Execution Summary",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Step Name", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Artifacts Generated")

    total_time = 0.0
    all_succeeded = True

    for r in results:
        total_time += r.duration_seconds
        if "FAILED" in r.status:
            all_succeeded = False
            status_text = f"[bold red]{r.status}[/bold red]"
        elif "SKIPPED" in r.status:
            status_text = f"[dim]{r.status}[/dim]"
        else:
            status_text = f"[bold green]{r.status}[/bold green]"

        dur_text = f"{r.duration_seconds:.2f} s" if r.duration_seconds > 0 else "-"
        table.add_row(r.name, status_text, dur_text, r.output_artifacts)

    console.print()
    console.print(table)
    console.print(f"\n[bold]Total Pipeline Duration:[/bold] {total_time:.2f} s\n")

    if all_succeeded:
        console.print(
            Panel("[bold green]✓ All pipeline steps completed successfully![/bold green]")
        )
    else:
        console.print(
            Panel("[bold red]✗ One or more pipeline steps encountered errors.[/bold red]")
        )


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def parse_args() -> argparse.Namespace:
    """Parse CLI options for the master pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Run all Rule2DRC and Sky130 layout/DRC download and analysis scripts."
    )
    parser.add_argument(
        "--include-large-gds",
        action="store_true",
        help="Download production-scale Sky130 GDS layouts (e.g. user_proj_example or caravel).",
    )
    parser.add_argument(
        "--large-target",
        choices=["user_proj_example", "caravel", "all"],
        default="user_proj_example",
        help=(
            "Target large GDS layout to download if --include-large-gds is active "
            "(default: user_proj_example)."
        ),
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading the Rule2DRC benchmark dataset.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip extracting the 13,921 GDS testcase files.",
    )
    parser.add_argument(
        "--skip-stats",
        action="store_true",
        help="Skip querying SkyWater 130nm HD library statistics.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the pipeline execution without running underlying commands.",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_args()
    runner = MasterPipelineRunner(
        include_large_gds=args.include_large_gds,
        large_target=args.large_target,
        skip_download=args.skip_download,
        skip_extract=args.skip_extract,
        skip_stats=args.skip_stats,
        dry_run=args.dry_run,
    )

    console.print(
        Panel.fit(
            f"[bold blue]Rule2DRC & SkyWater 130nm Master Pipeline[/bold blue]\n"
            f"Include Large GDS: [cyan]{args.include_large_gds}[/cyan] "
            f"(Target: [green]{args.large_target}[/green])\n"
            f"Dry Run Mode: [yellow]{args.dry_run}[/yellow]",
            title="Master Orchestrator",
        )
    )

    try:
        results = runner.run()
        display_pipeline_summary(results)
    except PipelineError as err:
        error_console.print(f"\n[bold red]Pipeline Error:[/bold red] {err}")
        sys.exit(1)
    except Exception as err:
        error_console.print(f"\n[bold red]Unexpected Error:[/bold red] {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
