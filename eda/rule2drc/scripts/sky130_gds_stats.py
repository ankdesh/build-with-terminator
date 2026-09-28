#!/usr/bin/env python3
"""SkyWater 130nm HD Standard Cell Library GDS Statistics Collector.

This script queries the official SkyWater PDK repository (google/skywater-pdk)
for the sky130_fd_sc_hd standard cell library, extracts metadata and file sizes
for all GDSII layout files, computes comprehensive statistics, and outputs both
formatted terminal tables and a markdown report.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ==============================================================================
# Centralized Hoisted Constants
# ==============================================================================
PDK_REPO_URL: str = "https://github.com/google/skywater-pdk/tree/main/libraries/sky130_fd_sc_hd"
SUBMODULE_TREE_API_URL: str = (
    "https://api.github.com/repos/google/skywater-pdk-libs-sky130_fd_sc_hd/git/trees/"
    "ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1?recursive=1"
)
DEFAULT_OUTPUT_MD: Path = Path("docs/sky130_fd_sc_hd_gds_stats.md")

SIZE_BINS: tuple[tuple[str, int, int], ...] = (
    ("< 2 KB", 0, 2048),
    ("2 KB – 5 KB", 2048, 5120),
    ("5 KB – 8 KB", 5120, 8192),
    ("8 KB – 12 KB", 8192, 12288),
    ("12 KB – 16 KB", 12288, 16384),
    ("16 KB – 20 KB", 16384, 20480),
    (">= 20 KB", 20480, sys.maxsize),
)

console = Console()
error_console = Console(stderr=True)


# ==============================================================================
# Domain Exceptions
# ==============================================================================
class Sky130StatsError(Exception):
    """Base exception for SkyWater PDK statistics extraction."""


class GitHubAPIError(Sky130StatsError):
    """Raised when GitHub API request fails or returns an error response."""


# ==============================================================================
# Data Models
# ==============================================================================
@dataclass(frozen=True)
class GDSBlobInfo:
    """Metadata record for a single GDS file in the repository."""

    path: str
    sha: str
    size_bytes: int
    cell_name: str
    cell_category: str


@dataclass(frozen=True)
class CategorySummary:
    """Summary statistics for a functional cell category."""

    category: str
    count: int
    total_bytes: int
    min_bytes: int
    max_bytes: int
    mean_bytes: float
    median_bytes: float


@dataclass(frozen=True)
class Sky130GDSReport:
    """Overall report containing computed metrics and tables."""

    total_files: int
    total_bytes: int
    min_bytes: int
    max_bytes: int
    mean_bytes: float
    median_bytes: float
    stdev_bytes: float
    percentiles: dict[str, float]
    bin_counts: dict[str, int]
    categories: list[CategorySummary]
    smallest_files: list[GDSBlobInfo]
    largest_files: list[GDSBlobInfo]


# ==============================================================================
# Statistics Collector Class
# ==============================================================================
class Sky130GDSStatsCollector:
    """Queries and computes layout statistics for sky130_fd_sc_hd GDS files."""

    def __init__(self, api_url: str = SUBMODULE_TREE_API_URL) -> None:
        """Initialize collector with API endpoint."""
        self.api_url = api_url

    @staticmethod
    def classify_cell(path: str) -> tuple[str, str]:
        """Extract cell name and functional group classification from path."""
        # e.g., cells/a2111o/sky130_fd_sc_hd__a2111o_1.gds
        filename = path.split("/")[-1].replace(".gds", "")
        cell_name = filename.replace("sky130_fd_sc_hd__", "")

        fn = cell_name.lower()
        if any(k in fn for k in ["df", "dl", "sd"]):
            cat = "Sequential (Flip-Flops / Latches)"
        elif any(k in fn for k in ["buf", "inv", "clk"]):
            cat = "Buffers & Inverters"
        elif any(
            k in fn for k in ["nand", "nor", "and", "or", "xor", "xnor", "a2", "a3", "o2", "o3"]
        ):
            cat = "Combinational Logic Gates"
        elif any(k in fn for k in ["mux"]):
            cat = "Multiplexers"
        elif any(k in fn for k in ["fill", "tap", "decap", "diode"]):
            cat = "Physical & Decap Cells"
        elif any(k in fn for k in ["lpflow", "dlswitch", "conb"]):
            cat = "Power Management & Special"
        elif any(k in fn for k in ["fa", "ha", "add"]):
            cat = "Adders & Arithmetic"
        else:
            cat = "Other Specialized Cells"

        return cell_name, cat

    def fetch_gds_entries(self) -> list[GDSBlobInfo]:
        """Fetch file tree from GitHub API and filter GDS entries."""
        console.log(f"Fetching git tree from GitHub API: [cyan]{self.api_url}[/cyan]")
        req = urllib.request.Request(self.api_url, headers={"User-Agent": "Rule2DRC-Stats/1.0"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise GitHubAPIError(f"Failed to fetch tree from GitHub API: {exc}") from exc

        tree = data.get("tree", [])
        if not tree:
            raise GitHubAPIError("Empty tree received from GitHub API.")

        entries: list[GDSBlobInfo] = []
        for item in tree:
            path = item.get("path", "")
            if path.endswith(".gds"):
                cell_name, cat = self.classify_cell(path)
                entries.append(
                    GDSBlobInfo(
                        path=path,
                        sha=item.get("sha", ""),
                        size_bytes=int(item.get("size", 0)),
                        cell_name=cell_name,
                        cell_category=cat,
                    )
                )

        console.log(f"Discovered [bold green]{len(entries)}[/bold green] GDS files.")
        return entries

    def compute_report(self, entries: Sequence[GDSBlobInfo]) -> Sky130GDSReport:
        """Compute statistical distributions and category summaries."""
        if not entries:
            raise Sky130StatsError("No GDS entries provided for statistical computation.")

        sizes = [e.size_bytes for e in entries]
        sorted_entries = sorted(entries, key=lambda e: e.size_bytes)
        sorted_sizes = [e.size_bytes for e in sorted_entries]

        def percentile(data: list[int], pct: float) -> float:
            k = (len(data) - 1) * (pct / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return float(data[int(k)])
            return float(data[int(f)] * (c - k) + data[int(c)] * (k - f))

        percentiles = {
            "p10": percentile(sorted_sizes, 10),
            "p25": percentile(sorted_sizes, 25),
            "p50 (median)": percentile(sorted_sizes, 50),
            "p75": percentile(sorted_sizes, 75),
            "p90": percentile(sorted_sizes, 90),
            "p95": percentile(sorted_sizes, 95),
            "p99": percentile(sorted_sizes, 99),
        }

        bin_counts: dict[str, int] = {name: 0 for name, _, _ in SIZE_BINS}
        for s in sizes:
            for name, low, high in SIZE_BINS:
                if low <= s < high:
                    bin_counts[name] += 1
                    break

        # Group by functional category
        groups: dict[str, list[int]] = defaultdict(list)
        for e in entries:
            groups[e.cell_category].append(e.size_bytes)

        category_summaries: list[CategorySummary] = []
        for cat, cat_sizes in groups.items():
            category_summaries.append(
                CategorySummary(
                    category=cat,
                    count=len(cat_sizes),
                    total_bytes=sum(cat_sizes),
                    min_bytes=min(cat_sizes),
                    max_bytes=max(cat_sizes),
                    mean_bytes=statistics.mean(cat_sizes),
                    median_bytes=statistics.median(cat_sizes),
                )
            )
        category_summaries.sort(key=lambda c: -c.count)

        return Sky130GDSReport(
            total_files=len(entries),
            total_bytes=sum(sizes),
            min_bytes=min(sizes),
            max_bytes=max(sizes),
            mean_bytes=statistics.mean(sizes),
            median_bytes=statistics.median(sizes),
            stdev_bytes=statistics.stdev(sizes),
            percentiles=percentiles,
            bin_counts=bin_counts,
            categories=category_summaries,
            smallest_files=sorted_entries[:5],
            largest_files=sorted_entries[-5:][::-1],
        )


# ==============================================================================
# Presentation & Markdown Generation
# ==============================================================================
def display_console(report: Sky130GDSReport) -> None:
    """Print clean formatted tables to terminal using Rich."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]SkyWater 130nm HD Standard Cell Library GDS Statistics[/bold blue]\n"
            f"Repository: [link={PDK_REPO_URL}]{PDK_REPO_URL}[/link]\n"
            f"Total GDS Files: [bold]{report.total_files}[/bold] | "
            f"Total Size: [bold]{report.total_bytes / (1024 * 1024):.2f} MB[/bold]",
            title="Sky130 HD PDK Analysis",
        )
    )

    # 1. Category Table
    tbl_cat = Table(
        title="1. Functional Cell Categories",
        header_style="bold magenta",
        show_lines=True,
    )
    tbl_cat.add_column("Category", style="bold")
    tbl_cat.add_column("Cell Count", justify="right")
    tbl_cat.add_column("Total Size", justify="right")
    tbl_cat.add_column("Min Size", justify="right")
    tbl_cat.add_column("Max Size", justify="right")
    tbl_cat.add_column("Mean Size", justify="right")
    tbl_cat.add_column("Median Size", justify="right")

    for c in report.categories:
        tbl_cat.add_row(
            c.category,
            str(c.count),
            f"{c.total_bytes / 1024:.1f} KB",
            f"{c.min_bytes:,} B",
            f"{c.max_bytes:,} B",
            f"{c.mean_bytes:.0f} B",
            f"{c.median_bytes:.0f} B",
        )
    console.print(tbl_cat)
    console.print()

    # 2. Percentiles & Bins Table
    tbl_bins = Table(title="2. Size Histogram Bins", header_style="bold yellow", show_lines=True)
    tbl_bins.add_column("Size Range", style="bold")
    tbl_bins.add_column("File Count", justify="right")
    tbl_bins.add_column("Percentage", justify="right")
    tbl_bins.add_column("Distribution", style="green")

    max_bin = max(report.bin_counts.values()) if report.bin_counts else 1
    for name, cnt in report.bin_counts.items():
        pct = (cnt / report.total_files) * 100
        bar = "█" * int((cnt / max_bin) * 25)
        tbl_bins.add_row(name, str(cnt), f"{pct:.2f}%", bar)
    console.print(tbl_bins)


def generate_markdown(report: Sky130GDSReport, output_file: Path) -> None:
    """Generate comprehensive markdown document."""
    lines: list[str] = [
        "# SkyWater 130nm HD Standard Cell Library (`sky130_fd_sc_hd`) GDS Statistics",
        "",
        "Comprehensive layout and file size statistics for all GDSII layout files in the "
        "**SkyWater SKY130 High-Density Standard Cell Library** (`sky130_fd_sc_hd`).",
        "",
        "## 1. Source & Repository Context",
        "",
        f"- **PDK Repository**: [`google/skywater-pdk`]({PDK_REPO_URL})",
        "- **Target Submodule**: `libraries/sky130_fd_sc_hd` ("
        "[`google/skywater-pdk-libs-sky130_fd_sc_hd`]"
        "(https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd))",
        "- **Target Commit**: `ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1` (`latest`)",
        "- **Technology**: SkyWater 130nm CMOS (`sky130`)",
        "- **Cell Library**: High Density (`fd_sc_hd`), 7-track standard cell architecture.",
        "",
        "---",
        "",
        "## 2. Overall GDS Metrics Summary",
        "",
        f"- **Total GDS Layout Files**: **{report.total_files}**",
        f"- **Total Uncompressed Size**: **{report.total_bytes:,} Bytes** "
        f"({report.total_bytes / (1024 * 1024):.2f} MB)",
        f"- **Minimum File Size**: **{report.min_bytes:,} Bytes** "
        f"({report.min_bytes / 1024:.2f} KB)",
        f"- **Maximum File Size**: **{report.max_bytes:,} Bytes** "
        f"({report.max_bytes / 1024:.2f} KB)",
        f"- **Mean File Size**: **{report.mean_bytes:.1f} ± {report.stdev_bytes:.1f} Bytes** "
        f"({report.mean_bytes / 1024:.2f} KB)",
        f"- **Median File Size**: **{report.median_bytes:.1f} Bytes** "
        f"({report.median_bytes / 1024:.2f} KB)",
        "",
        "---",
        "",
        "## 3. Breakdown by Functional Cell Category",
        "",
        "| Category | Cell Count | Total Size | Min Size | Max Size | Mean Size | Median Size |",
        "|---|---|---|---|---|---|---|",
    ]

    for c in report.categories:
        lines.append(
            f"| **{c.category}** | {c.count} | {c.total_bytes / 1024:.1f} KB | "
            f"{c.min_bytes:,} B | {c.max_bytes:,} B | {c.mean_bytes:.0f} B | "
            f"{c.median_bytes:.0f} B |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Size Percentile Distribution",
        "",
        "| Percentile | Size (Bytes) | Size (KB) |",
        "|---|---|---|",
    ])
    for pct_name, val in report.percentiles.items():
        lines.append(f"| **{pct_name}** | {val:,.1f} B | {val / 1024:.2f} KB |")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Size Bin Histogram",
        "",
        "| Size Range | Cell Count | Percentage |",
        "|---|---|---|",
    ])
    for name, cnt in report.bin_counts.items():
        pct = (cnt / report.total_files) * 100
        lines.append(f"| `{name}` | {cnt} | {pct:.2f}% |")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Extremes: Top 5 Smallest & Largest Cells",
        "",
        "### Top 5 Smallest Cells",
        "",
        "| Rank | File Size | Cell Name | Path | Functional Description |",
        "|---|---|---|---|---|",
    ])
    for i, e in enumerate(report.smallest_files, 1):
        lines.append(
            f"| {i} | {e.size_bytes:,} B ({e.size_bytes / 1024:.2f} KB) | "
            f"`{e.cell_name}` | `{e.path}` | Physical fill/tap cell |"
        )

    lines.extend([
        "",
        "### Top 5 Largest Cells",
        "",
        "| Rank | File Size | Cell Name | Path | Functional Description |",
        "|---|---|---|---|---|",
    ])
    for i, e in enumerate(report.largest_files, 1):
        lines.append(
            f"| {i} | {e.size_bytes:,} B ({e.size_bytes / 1024:.2f} KB) | "
            f"`{e.cell_name}` | `{e.path}` | Complex sequential / isolation macro |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 7. Comparison: Rule2DRC Testcases vs. Sky130 HD Standard Cells",
        "",
        "| Metric | Rule2DRC Testcase GDS (`testcases.parquet`) | "
        "Sky130 HD Standard Cell GDS (`sky130_fd_sc_hd`) |",
        "|---|---|---|",
        f"| **Total Files** | 13,921 synthetic rule snippets | "
        f"{report.total_files} production library cells |",
        f"| **Total Size** | 4.68 MB | {report.total_bytes / (1024 * 1024):.2f} MB |",
        f"| **Mean Size** | 352.6 Bytes | "
        f"{report.mean_bytes:.0f} Bytes (~{report.mean_bytes / 1024:.1f} KB) |",
        f"| **Median Size** | 362.0 Bytes | "
        f"{report.median_bytes:.0f} Bytes (~{report.median_bytes / 1024:.1f} KB) |",
        f"| **Size Range** | 106 B – 1,930 B (0.10 KB – 1.88 KB) | "
        f"{report.min_bytes:,} B – {report.max_bytes:,} B "
        f"({report.min_bytes / 1024:.1f} KB – {report.max_bytes / 1024:.1f} KB) |",
        "| **Layout Content** | Minimal test polygons targeting single DRC rules "
        "(e.g. 2 shapes with specific spacing) | "
        "Full production standard cell layouts (wells, diffusions, poly gates, contacts, pins, "
        "local interconnect, power rails) |",
        "",
    ])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
    console.log(f"Wrote report to: [bold green]{output_file.resolve()}[/bold green]")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def parse_args() -> argparse.Namespace:
    """Parse CLI options for the Sky130 statistics collector."""
    parser = argparse.ArgumentParser(
        description="Collect and tabulate GDS statistics from the SkyWater sky130_fd_sc_hd library."
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_MD,
        help=f"Path to output markdown report (default: {DEFAULT_OUTPUT_MD})",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_args()
    collector = Sky130GDSStatsCollector()

    try:
        entries = collector.fetch_gds_entries()
        report = collector.compute_report(entries)
        display_console(report)
        generate_markdown(report, args.output_file)
    except Sky130StatsError as err:
        error_console.print(f"\n[bold red]Error:[/bold red] {err}")
        sys.exit(1)
    except Exception as err:
        error_console.print(f"\n[bold red]Unexpected Error:[/bold red] {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
