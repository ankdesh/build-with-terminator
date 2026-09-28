#!/usr/bin/env python3
"""GDS File Extractor and Size Statistics Analyzer.

This script extracts all 13,921 binary GDS layout files from the Rule2DRC
testcases Parquet dataset into a local folder structure and computes detailed
size statistics, percentiles, and distribution histograms.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pyarrow.parquet as pq
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

# ==============================================================================
# Centralized Hoisted Constants
# ==============================================================================
DEFAULT_INPUT_PARQUET: Path = Path("data/testcases.parquet")
DEFAULT_OUTPUT_DIR: Path = Path("data/extracted_gds")
GDSII_MAGIC_HEADER: bytes = b"\x00\x06\x00\x02"

SIZE_BINS: tuple[tuple[str, int, int], ...] = (
    ("< 200 B", 0, 200),
    ("200 B - 300 B", 200, 300),
    ("300 B - 500 B", 300, 500),
    ("500 B - 1 KB", 500, 1024),
    ("1 KB - 5 KB", 1024, 5 * 1024),
    (">= 5 KB", 5 * 1024, sys.maxsize),
)

console = Console()
error_console = Console(stderr=True)


# ==============================================================================
# Domain Exceptions
# ==============================================================================
class Rule2DRCError(Exception):
    """Base exception for Rule2DRC tooling."""


class DatasetNotFoundError(Rule2DRCError):
    """Raised when the input testcases parquet file does not exist."""


class ExtractionError(Rule2DRCError):
    """Raised when an error occurs during binary GDS extraction."""


# ==============================================================================
# Data Models
# ==============================================================================
@dataclass(frozen=True)
class FileRecord:
    """Metadata and size information for an extracted GDS file."""

    problem_id: str
    testcase_id: str
    relative_path: str
    split_hint: str
    size_bytes: int


@dataclass(frozen=True)
class GroupStats:
    """Aggregate statistics for a group of files."""

    count: int
    total_bytes: int
    min_bytes: int
    max_bytes: int
    mean_bytes: float
    median_bytes: float
    stdev_bytes: float


@dataclass(frozen=True)
class ExtractionReport:
    """Comprehensive extraction and statistical report."""

    total_files: int
    output_directory: Path
    overall: GroupStats
    by_split: dict[str, GroupStats]
    percentiles: dict[str, float]
    bin_counts: dict[str, int]
    smallest_files: list[FileRecord]
    largest_files: list[FileRecord]


# ==============================================================================
# Extractor Class (One Primary Class)
# ==============================================================================
class GDSExtractor:
    """Extracts binary GDS files from Parquet and tabulates size statistics."""

    def __init__(
        self,
        input_parquet: Path = DEFAULT_INPUT_PARQUET,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        by_problem: bool = False,
        overwrite: bool = False,
    ) -> None:
        """Initialize extractor configuration."""
        self.input_parquet = input_parquet
        self.output_dir = output_dir
        self.by_problem = by_problem
        self.overwrite = overwrite

    def _compute_group_stats(self, sizes: Sequence[int]) -> GroupStats:
        """Calculate summary statistics for a given sequence of byte sizes."""
        if not sizes:
            return GroupStats(0, 0, 0, 0, 0.0, 0.0, 0.0)

        count = len(sizes)
        total_bytes = sum(sizes)
        min_bytes = min(sizes)
        max_bytes = max(sizes)
        mean_bytes = statistics.fmean(sizes)
        median_bytes = statistics.median(sizes)
        stdev_bytes = statistics.stdev(sizes) if count > 1 else 0.0

        return GroupStats(
            count=count,
            total_bytes=total_bytes,
            min_bytes=min_bytes,
            max_bytes=max_bytes,
            mean_bytes=mean_bytes,
            median_bytes=median_bytes,
            stdev_bytes=stdev_bytes,
        )

    def run(self) -> ExtractionReport:
        """Execute extraction and generate the statistical report."""
        if not self.input_parquet.exists():
            raise DatasetNotFoundError(
                f"Input parquet file '{self.input_parquet}' does not exist. "
                "Run 'uv run python scripts/download_dataset.py' first."
            )

        console.log(f"Reading dataset: [bold cyan]{self.input_parquet}[/bold cyan]")
        try:
            table = pq.read_table(
                self.input_parquet,
                columns=["problem_id", "testcase_id", "split_hint", "gds_path", "gds"],
            )
        except Exception as exc:
            raise ExtractionError(f"Failed to read parquet table: {exc}") from exc

        total_rows = table.num_rows
        console.log(f"Found [bold green]{total_rows:,}[/bold green] testcases to extract.")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        records: list[FileRecord] = []
        pass_sizes: list[int] = []
        fail_sizes: list[int] = []

        # Batch iteration for high performance
        problem_ids = table["problem_id"].to_pylist()
        testcase_ids = table["testcase_id"].to_pylist()
        split_hints = table["split_hint"].to_pylist()
        gds_paths = table["gds_path"].to_pylist()
        gds_blobs = table["gds"].to_pylist()

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Extracting GDS layouts...", total=total_rows)

            for i in range(total_rows):
                pid = problem_ids[i]
                tcid = testcase_ids[i]
                split = split_hints[i]
                raw_path = gds_paths[i]
                blob = gds_blobs[i]

                if not isinstance(blob, (bytes, bytearray)):
                    raise ExtractionError(
                        f"Row {i} ({pid}/{tcid}) contains non-binary GDS blob: {type(blob)}"
                    )

                size = len(blob)
                if self.by_problem:
                    dest_file = self.output_dir / "problems" / pid / raw_path
                else:
                    dest_file = self.output_dir / raw_path

                if self.overwrite or not dest_file.exists():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(blob)

                record = FileRecord(
                    problem_id=pid,
                    testcase_id=tcid,
                    relative_path=str(dest_file.relative_to(self.output_dir)),
                    split_hint=split,
                    size_bytes=size,
                )
                records.append(record)

                if split == "pass":
                    pass_sizes.append(size)
                else:
                    fail_sizes.append(size)

                progress.advance(task_id)

        all_sizes = [r.size_bytes for r in records]
        sorted_sizes = sorted(all_sizes)

        # Percentile calculations
        def percentile(data: list[int], pct: float) -> float:
            k = (len(data) - 1) * (pct / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return float(data[int(k)])
            d0 = data[int(f)] * (c - k)
            d1 = data[int(c)] * (k - f)
            return float(d0 + d1)

        percentiles = {
            "p10": percentile(sorted_sizes, 10),
            "p25": percentile(sorted_sizes, 25),
            "p50 (median)": percentile(sorted_sizes, 50),
            "p75": percentile(sorted_sizes, 75),
            "p90": percentile(sorted_sizes, 90),
            "p95": percentile(sorted_sizes, 95),
            "p99": percentile(sorted_sizes, 99),
        }

        # Histogram Bins
        bin_counts: dict[str, int] = {name: 0 for name, _, _ in SIZE_BINS}
        for s in all_sizes:
            for name, low, high in SIZE_BINS:
                if low <= s < high:
                    bin_counts[name] += 1
                    break

        sorted_records = sorted(records, key=lambda r: r.size_bytes)
        smallest_files = sorted_records[:5]
        largest_files = sorted_records[-5:][::-1]

        return ExtractionReport(
            total_files=len(records),
            output_directory=self.output_dir,
            overall=self._compute_group_stats(all_sizes),
            by_split={
                "pass": self._compute_group_stats(pass_sizes),
                "fail": self._compute_group_stats(fail_sizes),
            },
            percentiles=percentiles,
            bin_counts=bin_counts,
            smallest_files=smallest_files,
            largest_files=largest_files,
        )


# ==============================================================================
# Presentation Helper
# ==============================================================================
def display_report(report: ExtractionReport) -> None:
    """Format and print detailed statistical tables using Rich."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]GDS Extraction Completed Successfully![/bold green]\n"
            f"Destination Directory: [cyan]{report.output_directory.resolve()}[/cyan]\n"
            f"Total Layouts Extracted: [bold]{report.total_files:,}[/bold]",
            title="Extraction Summary",
        )
    )

    # 1. Summary by Group Table
    table_group = Table(
        title="1. Overall & Subset File Size Statistics",
        header_style="bold magenta",
        show_lines=True,
    )
    table_group.add_column("Category", style="bold")
    table_group.add_column("Files", justify="right")
    table_group.add_column("Total Size", justify="right")
    table_group.add_column("Min Size", justify="right")
    table_group.add_column("Max Size", justify="right")
    table_group.add_column("Mean ± StdDev", justify="right")
    table_group.add_column("Median", justify="right")

    def format_row(name: str, s: GroupStats) -> list[str]:
        total_str = f"{s.total_bytes / (1024 * 1024):.2f} MB"
        mean_std = f"{s.mean_bytes:.1f} ± {s.stdev_bytes:.1f} B"
        return [
            name,
            f"{s.count:,}",
            total_str,
            f"{s.min_bytes:,} B",
            f"{s.max_bytes:,} B",
            mean_std,
            f"{s.median_bytes:.1f} B",
        ]

    table_group.add_row(*format_row("Overall (All Files)", report.overall))
    if "pass" in report.by_split:
        table_group.add_row(*format_row("pass/ (clean)", report.by_split["pass"]))
    if "fail" in report.by_split:
        table_group.add_row(*format_row("fail/ (violation)", report.by_split["fail"]))

    console.print(table_group)
    console.print()

    # 2. Size Percentiles Table
    table_pct = Table(
        title="2. File Size Percentile Distribution",
        header_style="bold cyan",
        show_lines=True,
    )
    table_pct.add_column("Percentile", style="bold")
    table_pct.add_column("Size (Bytes)", justify="right")
    table_pct.add_column("Size (KB)", justify="right")

    for pct_name, val in report.percentiles.items():
        table_pct.add_row(pct_name, f"{val:.1f} B", f"{val / 1024:.2f} KB")

    # 3. Size Bins / Histogram Table
    table_bins = Table(
        title="3. Size Bin Histogram",
        header_style="bold yellow",
        show_lines=True,
    )
    table_bins.add_column("Size Range", style="bold")
    table_bins.add_column("File Count", justify="right")
    table_bins.add_column("Percentage", justify="right")
    table_bins.add_column("Visual Bar", style="green")

    max_bin_count = max(report.bin_counts.values()) if report.bin_counts else 1
    for bin_name, count in report.bin_counts.items():
        pct = (count / report.total_files) * 100
        bar_len = int((count / max_bin_count) * 25)
        bar = "█" * bar_len
        table_bins.add_row(bin_name, f"{count:,}", f"{pct:.2f}%", bar)

    # 4. Extremes Table
    table_extremes = Table(
        title="4. Top 5 Smallest & Largest GDS Files",
        header_style="bold blue",
        show_lines=True,
    )
    table_extremes.add_column("Type", style="bold")
    table_extremes.add_column("Size", justify="right")
    table_extremes.add_column("Problem ID")
    table_extremes.add_column("Testcase ID")
    table_extremes.add_column("Relative Path")

    for rec in report.smallest_files:
        table_extremes.add_row(
            "[green]Smallest[/green]",
            f"{rec.size_bytes} B",
            rec.problem_id,
            rec.testcase_id,
            rec.relative_path,
        )
    for rec in report.largest_files:
        table_extremes.add_row(
            "[red]Largest[/red]",
            f"{rec.size_bytes:,} B ({rec.size_bytes / 1024:.2f} KB)",
            rec.problem_id,
            rec.testcase_id,
            rec.relative_path,
        )

    console.print(table_pct)
    console.print()
    console.print(table_bins)
    console.print()
    console.print(table_extremes)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for extractor script."""
    parser = argparse.ArgumentParser(
        description="Extract binary GDS files and tabulate size statistics."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PARQUET,
        help=f"Path to testcases Parquet file (default: {DEFAULT_INPUT_PARQUET})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output folder to extract GDS files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--by-problem",
        action="store_true",
        help="Organize into problems/{problem_id}/{split}/{testcase}.gds subfolders",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files on disk.",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_args()
    extractor = GDSExtractor(
        input_parquet=args.input,
        output_dir=args.output_dir,
        by_problem=args.by_problem,
        overwrite=args.overwrite,
    )

    console.print(
        Panel.fit(
            f"[bold blue]Rule2DRC GDS Extractor & Statistical Analyzer[/bold blue]\n"
            f"Input Parquet: [green]{args.input}[/green]\n"
            f"Output Directory: [cyan]{args.output_dir}[/cyan]",
            title="Rule2DRC GDS Tool",
        )
    )

    try:
        report = extractor.run()
        display_report(report)
    except Rule2DRCError as err:
        error_console.print(f"\n[bold red]Error:[/bold red] {err}")
        sys.exit(1)
    except Exception as err:
        error_console.print(f"\n[bold red]Unexpected Error:[/bold red] {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
