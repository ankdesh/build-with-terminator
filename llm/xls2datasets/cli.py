"""Command-Line Interface (CLI) for xls2datasets.

Provides commands to run Stage 1 (XLS -> CSVs), Stage 2 (LLM Schema Analysis),
or end-to-end processing of XLS/XLSX files.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import (
    DEFAULT_LLM_CONFIG_PATH,
    DEFAULT_STAGE1_OUTPUT_DIR,
    DEFAULT_STAGE2_OUTPUT_DIR,
)
from stage1_extractor import Stage1XlsExtractor
from stage2_schema_analyzer import Stage2SchemaAnalyzer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging format and verbosity level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def run_stage1(xls_path: str, output_dir: str) -> Path:
    """Execute Stage 1 extractor."""
    print(f"=== [Stage 1] Extracting tables from: {xls_path} ===")
    extractor = Stage1XlsExtractor(output_dir=output_dir)
    csv_files = extractor.extract(xls_path)
    print(f"Stage 1 Complete: Extracted {len(csv_files)} tables to '{output_dir}'.")
    return Path(output_dir)


def run_stage2(stage1_dir: str, output_dir: str, config_path: str) -> Path:
    """Execute Stage 2 schema analyzer."""
    print(f"=== [Stage 2] Analyzing schemas from: {stage1_dir} ===")
    analyzer = Stage2SchemaAnalyzer(
        stage1_dir=stage1_dir,
        output_dir=output_dir,
        config_path=config_path,
    )
    summary = analyzer.analyze()
    print(
        f"Stage 2 Complete: Generated schemas for "
        f"{summary['total_tables']} tables at '{output_dir}'."
    )
    return Path(output_dir)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="xls2datasets",
        description="Two-stage pipeline for extracting tables from XLS/XLSX files "
        "and generating analysis-ready CSV datasets with LLM schema metadata.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose debug logging"
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")

    # Command: run (end-to-end)
    run_parser = subparsers.add_parser("run", help="Run end-to-end Stage 1 and Stage 2 pipeline")
    run_parser.add_argument("--xls", required=True, type=str, help="Path to input XLS/XLSX file")
    run_parser.add_argument(
        "--stage1-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Intermediate directory for Stage 1 extracted tables",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE2_OUTPUT_DIR),
        help="Final output directory for schemas and data dictionary",
    )
    run_parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_LLM_CONFIG_PATH),
        help="Path to LLM configuration YAML file",
    )

    # Command: stage1
    s1_parser = subparsers.add_parser("stage1", help="Run Stage 1 only (XLS -> CSVs)")
    s1_parser.add_argument("--xls", required=True, type=str, help="Path to input XLS/XLSX file")
    s1_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Directory to save extracted CSVs and manifest",
    )

    # Command: stage2
    s2_parser = subparsers.add_parser("stage2", help="Run Stage 2 only (Schema Analysis)")
    s2_parser.add_argument(
        "--input-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Directory containing Stage 1 manifest and CSVs",
    )
    s2_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE2_OUTPUT_DIR),
        help="Directory to save schemas and data dictionary",
    )
    s2_parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_LLM_CONFIG_PATH),
        help="Path to LLM configuration YAML file",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.command == "run":
            stage1_path = run_stage1(args.xls, args.stage1_dir)
            run_stage2(str(stage1_path), args.output_dir, args.config)
        elif args.command == "stage1":
            run_stage1(args.xls, args.output_dir)
        elif args.command == "stage2":
            run_stage2(args.input_dir, args.output_dir, args.config)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
