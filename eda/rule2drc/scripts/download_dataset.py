#!/usr/bin/env python3
"""Rule2DRC Dataset Downloader Script.

This script downloads the official Rule2DRC benchmark dataset from Hugging Face
('jusjinuk/Rule2DRC'), validates dataset integrity, and saves local Parquet files
for offline benchmark execution.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq
from datasets import Dataset, load_dataset
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ==============================================================================
# Centralized Hoisted Constants
# ==============================================================================
DATASET_REPO: str = "jusjinuk/Rule2DRC"
CONFIG_TASKS: str = "tasks"
CONFIG_TESTCASES: str = "testcases"
DEFAULT_SPLIT: str = "test"

EXPECTED_TASKS_COUNT: int = 1000
EXPECTED_TESTCASES_COUNT: int = 13921

DEFAULT_OUTPUT_DIR: Path = Path("data")
TASKS_FILENAME: str = "tasks.parquet"
TESTCASES_FILENAME: str = "testcases.parquet"

EXPECTED_TASKS_REQUIRED_COLUMNS: tuple[str, ...] = (
    "problem_id",
    "prompt",
    "gold_drc",
    "spec_yaml",
)
EXPECTED_TESTCASES_REQUIRED_COLUMNS: tuple[str, ...] = (
    "problem_id",
    "testcase_id",
    "gds",
    "label",
)

console = Console()
error_console = Console(stderr=True)


# ==============================================================================
# Domain Exceptions
# ==============================================================================
class Rule2DRCError(Exception):
    """Base exception for all Rule2DRC errors."""


class DatasetDownloadError(Rule2DRCError):
    """Raised when downloading a dataset subset from Hugging Face fails."""


class DatasetValidationError(Rule2DRCError):
    """Raised when the downloaded dataset fails schema or row count validation."""


# ==============================================================================
# Dataset Downloader Implementation
# ==============================================================================
@dataclass(frozen=True)
class DownloadResult:
    """Encapsulates the output artifacts of a dataset download operation."""

    tasks_path: Path
    testcases_path: Path | None
    tasks_count: int
    testcases_count: int | None


class Rule2DRCDownloader:
    """Downloader and validator for the Rule2DRC Hugging Face dataset."""

    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR, force: bool = False) -> None:
        """Initialize the downloader with destination path and overwrite options."""
        self.output_dir = output_dir
        self.force = force

    def _fetch_subset(self, config_name: str) -> Dataset:
        """Download a specific configuration subset from Hugging Face."""
        console.log(
            f"[bold cyan]Fetching subset:[/bold cyan] {config_name} (split: {DEFAULT_SPLIT})"
        )
        try:
            subset = load_dataset(DATASET_REPO, config_name, split=DEFAULT_SPLIT)
            if not isinstance(subset, Dataset):
                raise DatasetDownloadError(
                    f"Unexpected dataset type returned for {config_name}: {type(subset)}"
                )
            return subset
        except Exception as exc:
            raise DatasetDownloadError(
                f"Failed to download '{config_name}' from '{DATASET_REPO}': {exc}"
            ) from exc

    def _validate_tasks(self, tasks: Dataset) -> None:
        """Validate row count and schema requirements for tasks."""
        row_count = len(tasks)
        console.log(f"Validating tasks: found {row_count} rows (expected: {EXPECTED_TASKS_COUNT})")
        if row_count != EXPECTED_TASKS_COUNT:
            raise DatasetValidationError(
                f"Task count mismatch: expected {EXPECTED_TASKS_COUNT}, found {row_count}"
            )

        column_names = set(tasks.column_names)
        for col in EXPECTED_TASKS_REQUIRED_COLUMNS:
            if col not in column_names:
                raise DatasetValidationError(
                    f"Tasks missing column '{col}'. Available: {sorted(column_names)}"
                )

    def _validate_testcases(self, testcases: Dataset) -> None:
        """Validate row count and schema requirements for testcases."""
        row_count = len(testcases)
        console.log(
            f"Validating testcases: found {row_count} rows (expected: {EXPECTED_TESTCASES_COUNT})"
        )
        if row_count != EXPECTED_TESTCASES_COUNT:
            raise DatasetValidationError(
                f"Testcase count mismatch: expected {EXPECTED_TESTCASES_COUNT}, found {row_count}"
            )

        column_names = set(testcases.column_names)
        for col in EXPECTED_TESTCASES_REQUIRED_COLUMNS:
            if col not in column_names:
                raise DatasetValidationError(
                    f"Testcases missing column '{col}'. Available: {sorted(column_names)}"
                )

    def run(self, include_testcases: bool = True) -> DownloadResult:
        """Execute the download, validation, and export to parquet files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tasks_file = self.output_dir / TASKS_FILENAME
        testcases_file = self.output_dir / TESTCASES_FILENAME

        # Step 1: Download & Validate Tasks
        if tasks_file.exists() and not self.force:
            console.log(
                f"[yellow]Tasks file exists at {tasks_file}. Skipping fetch (use --force).[/yellow]"
            )
            tasks_table = pq.read_table(tasks_file)
            tasks_count = tasks_table.num_rows
        else:
            tasks_dataset = self._fetch_subset(CONFIG_TASKS)
            self._validate_tasks(tasks_dataset)
            console.log(f"Exporting tasks to Parquet: [bold green]{tasks_file}[/bold green]")
            tasks_dataset.to_parquet(str(tasks_file))
            tasks_count = len(tasks_dataset)

        # Step 2: Download & Validate Testcases
        testcases_count: int | None = None
        if include_testcases:
            if testcases_file.exists() and not self.force:
                console.log(
                    f"[yellow]Testcases file exists at {testcases_file}. "
                    "Skipping fetch (use --force).[/yellow]"
                )
                testcases_table = pq.read_table(testcases_file)
                testcases_count = testcases_table.num_rows
            else:
                testcases_dataset = self._fetch_subset(CONFIG_TESTCASES)
                self._validate_testcases(testcases_dataset)
                console.log(
                    f"Exporting testcases to Parquet: [bold green]{testcases_file}[/bold green]"
                )
                testcases_dataset.to_parquet(str(testcases_file))
                testcases_count = len(testcases_dataset)

        return DownloadResult(
            tasks_path=tasks_file,
            testcases_path=testcases_file if include_testcases else None,
            tasks_count=tasks_count,
            testcases_count=testcases_count,
        )


# ==============================================================================
# Presentation & Summary Helpers
# ==============================================================================
def display_summary(result: DownloadResult) -> None:
    """Print a clean visual summary of the downloaded dataset."""
    table = Table(title="Rule2DRC Dataset Summary", show_header=True, header_style="bold magenta")
    table.add_column("Subset", style="dim", width=12)
    table.add_column("Rows", justify="right")
    table.add_column("File Size", justify="right")
    table.add_column("Local Path")

    tasks_size = f"{result.tasks_path.stat().st_size / (1024 * 1024):.2f} MB"
    table.add_row("Tasks", str(result.tasks_count), tasks_size, str(result.tasks_path))

    if result.testcases_path and result.testcases_path.exists():
        tc_size = f"{result.testcases_path.stat().st_size / (1024 * 1024):.2f} MB"
        table.add_row("Testcases", str(result.testcases_count), tc_size, str(result.testcases_path))

    console.print(table)

    try:
        tasks_schema = pq.read_schema(result.tasks_path)
        console.print(
            Panel(
                f"[bold]Tasks Columns:[/bold] {', '.join(tasks_schema.names)}",
                title="Tasks Schema Overview",
            )
        )
        if result.testcases_path and result.testcases_path.exists():
            tc_schema = pq.read_schema(result.testcases_path)
            console.print(
                Panel(
                    f"[bold]Testcases Columns:[/bold] {', '.join(tc_schema.names)}",
                    title="Testcases Schema Overview",
                )
            )
    except Exception as exc:
        console.log(f"[yellow]Could not read schema for preview: {exc}[/yellow]")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the downloader script."""
    parser = argparse.ArgumentParser(
        description="Download and validate Rule2DRC benchmark dataset from Hugging Face."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save Parquet files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if Parquet files already exist locally.",
    )
    parser.add_argument(
        "--skip-testcases",
        action="store_true",
        help="Skip downloading the GDS testcases subset (download tasks only).",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_args()
    downloader = Rule2DRCDownloader(output_dir=args.output_dir, force=args.force)

    console.print(
        Panel.fit(
            f"[bold blue]Rule2DRC Benchmark Dataset Downloader[/bold blue]\n"
            f"Source: [link=https://huggingface.co/datasets/{DATASET_REPO}]"
            f"https://huggingface.co/datasets/{DATASET_REPO}[/link]\n"
            f"Destination: [green]{args.output_dir.resolve()}[/green]",
            title="Rule2DRC",
        )
    )

    try:
        result = downloader.run(include_testcases=not args.skip_testcases)
        console.print(
            "\n[bold green]✓ Download and validation completed successfully![/bold green]\n"
        )
        display_summary(result)
    except Rule2DRCError as err:
        error_console.print(f"\n[bold red]Error:[/bold red] {err}")
        sys.exit(1)
    except Exception as err:
        error_console.print(f"\n[bold red]Unexpected Error:[/bold red] {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
