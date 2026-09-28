#!/usr/bin/env python3
"""Large Sky130 GDS Layout Downloader.

This script downloads production-scale SkyWater 130nm layout files on-demand:
1. 'user_proj_example.gds' (~53.4 MB) - Hardened digital sub-system from caravel_user_project
2. 'caravel.gds' (~54.6 MB gz / ~250 MB raw) - Full-chip Caravel SoC harness from efabless
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

# ==============================================================================
# Centralized Hoisted Constants
# ==============================================================================
DEFAULT_OUTPUT_DIR: Path = Path("data/large_gds")
GDSII_HEADER_MAGIC: bytes = b"\x00\x06\x00\x02"
CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1 MB chunk stream buffer

TARGET_CONFIGS: dict[str, dict[str, str | bool]] = {
    "user_proj_example": {
        "name": "User Project Example Core",
        "url": (
            "https://raw.githubusercontent.com/efabless/caravel_user_project/"
            "main/gds/user_proj_example.gds"
        ),
        "filename": "user_proj_example.gds",
        "is_compressed": False,
        "description": "Hardened 32-bit digital sub-system core (Sky130)",
    },
    "caravel": {
        "name": "Caravel Full SoC Harness",
        "url": "https://raw.githubusercontent.com/efabless/caravel/main/gds/caravel.gds.gz",
        "filename": "caravel.gds",
        "is_compressed": True,
        "description": "Full-chip SoC with PicoRV32 RISC-V core & padframe (Sky130)",
    },
}

console = Console()
error_console = Console(stderr=True)


# ==============================================================================
# Domain Exceptions
# ==============================================================================
class LargeGDSError(Exception):
    """Base exception for large GDS downloader tooling."""


class DownloadNetworkError(LargeGDSError):
    """Raised when an HTTP download connection fails or is interrupted."""


class FileCorruptedError(LargeGDSError):
    """Raised when a downloaded layout fails GDSII format validation."""


# ==============================================================================
# Data Models
# ==============================================================================
@dataclass(frozen=True)
class DownloadItemResult:
    """Result information for a single downloaded GDS file."""

    key: str
    name: str
    target_path: Path
    file_size_bytes: int
    was_cached: bool


# ==============================================================================
# Downloader Implementation (One Primary Class)
# ==============================================================================
class LargeGDSDownloader:
    """Downloads, decompresses, and validates large Sky130 GDS layout files."""

    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR, force: bool = False) -> None:
        """Initialize with target directory and force-overwrite setting."""
        self.output_dir = output_dir
        self.force = force

    def _validate_gds_header(self, file_path: Path) -> None:
        """Validate that the first 4 bytes match the GDSII header record."""
        with file_path.open("rb") as f:
            header = f.read(4)
        if header != GDSII_HEADER_MAGIC:
            raise FileCorruptedError(
                f"File '{file_path}' does not start with valid GDSII header. "
                f"Expected {GDSII_HEADER_MAGIC.hex()}, found {header.hex()}."
            )

    def _stream_download(self, url: str, dest_path: Path, title: str) -> None:
        """Stream an HTTP resource to disk with a Rich progress bar."""
        req = urllib.request.Request(url, headers={"User-Agent": "LargeGDSDownloader/1.0"})
        try:
            with urllib.request.urlopen(req) as response:
                content_len = response.headers.get("Content-Length")
                total_bytes = int(content_len) if content_len and content_len.isdigit() else None

                with Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Downloading {title}...", total=total_bytes)

                    with dest_path.open("wb") as out_file:
                        while True:
                            chunk = response.read(CHUNK_SIZE_BYTES)
                            if not chunk:
                                break
                            out_file.write(chunk)
                            progress.advance(task, len(chunk))
        except Exception as exc:
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadNetworkError(f"Download failed for '{url}': {exc}") from exc

    def download_target(self, key: str) -> DownloadItemResult:
        """Download and prepare a specific target."""
        if key not in TARGET_CONFIGS:
            raise LargeGDSError(f"Unknown target key '{key}'. Available: {list(TARGET_CONFIGS)}")

        cfg = TARGET_CONFIGS[key]
        name = str(cfg["name"])
        url = str(cfg["url"])
        filename = str(cfg["filename"])
        is_compressed = bool(cfg["is_compressed"])

        final_path = self.output_dir / filename

        if final_path.exists() and not self.force:
            console.log(
                f"[yellow]{name} already exists at {final_path}. Skipping (use --force).[/yellow]"
            )
            return DownloadItemResult(
                key=key,
                name=name,
                target_path=final_path,
                file_size_bytes=final_path.stat().st_size,
                was_cached=True,
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

        if is_compressed:
            temp_gz_path = self.output_dir / f"{filename}.gz.tmp"
            console.log(f"Fetching compressed archive: [cyan]{url}[/cyan]")
            self._stream_download(url, temp_gz_path, title=name)

            console.log(f"Decompressing GDSII layout to: [bold green]{final_path}[/bold green]")
            with gzip.open(temp_gz_path, "rb") as gz_in, final_path.open("wb") as out_f:
                shutil.copyfileobj(gz_in, out_f)
            temp_gz_path.unlink()
        else:
            temp_path = self.output_dir / f"{filename}.tmp"
            console.log(f"Fetching GDSII layout: [cyan]{url}[/cyan]")
            self._stream_download(url, temp_path, title=name)
            temp_path.rename(final_path)

        console.log(f"Validating GDSII binary structure: [green]{final_path.name}[/green]")
        self._validate_gds_header(final_path)

        return DownloadItemResult(
            key=key,
            name=name,
            target_path=final_path,
            file_size_bytes=final_path.stat().st_size,
            was_cached=False,
        )

    def run(self, targets: Sequence[str]) -> list[DownloadItemResult]:
        """Download all requested targets and return summary results."""
        results: list[DownloadItemResult] = []
        for target_key in targets:
            console.print(f"\n[bold magenta]Processing Target:[/bold magenta] {target_key}")
            result = self.download_target(target_key)
            results.append(result)
        return results


# ==============================================================================
# Presentation Helper
# ==============================================================================
def display_summary(results: list[DownloadItemResult]) -> None:
    """Print clean summary table of downloaded GDS files."""
    table = Table(
        title="Large Sky130 GDS Layouts Download Summary",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Key", style="bold")
    table.add_column("Design Name")
    table.add_column("File Size", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Local Path")

    for r in results:
        size_str = f"{r.file_size_bytes / (1024 * 1024):.2f} MB"
        status_str = "[yellow]Cached[/yellow]" if r.was_cached else "[green]Downloaded[/green]"
        table.add_row(r.key, r.name, size_str, status_str, str(r.target_path))

    console.print(table)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def parse_args() -> argparse.Namespace:
    """Parse CLI options for the downloader."""
    parser = argparse.ArgumentParser(
        description="Download large production Sky130 GDS layout files on demand."
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=["user_proj_example", "caravel", "all"],
        default=["all"],
        help="Target layouts to download (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save GDS files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite existing files.",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_args()
    selected = list(TARGET_CONFIGS.keys()) if "all" in args.targets else args.targets

    downloader = LargeGDSDownloader(output_dir=args.output_dir, force=args.force)

    console.print(
        Panel.fit(
            f"[bold blue]SkyWater 130nm Large IP GDS Downloader[/bold blue]\n"
            f"Targets: [cyan]{', '.join(selected)}[/cyan]\n"
            f"Destination: [green]{args.output_dir.resolve()}[/green]",
            title="Large GDS Tool",
        )
    )

    try:
        results = downloader.run(selected)
        console.print("\n[bold green]✓ Download and validation completed![/bold green]\n")
        display_summary(results)
    except LargeGDSError as err:
        error_console.print(f"\n[bold red]Error:[/bold red] {err}")
        sys.exit(1)
    except Exception as err:
        error_console.print(f"\n[bold red]Unexpected Error:[/bold red] {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
