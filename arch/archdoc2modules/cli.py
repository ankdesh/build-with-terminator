"""Command-Line Interface (CLI) for archdoc2modules.

Provides commands to run Stage 1 (PDF -> MD + Assets), Stage 2 (Decomposition),
or end-to-end processing of hardware specification documents.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_STAGE1_OUTPUT_DIR,
    DEFAULT_STAGE2_OUTPUT_DIR,
)
from stage1_parser import Stage1DoclingParser
from stage2_decomposer import Stage2Decomposer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging format and verbosity level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def run_stage1(pdf_path: str, output_dir: str) -> Path:
    """Execute Stage 1 parser."""
    print(f"=== [Stage 1] Parsing PDF specification: {pdf_path} ===")
    parser = Stage1DoclingParser(output_dir=output_dir)
    sections = parser.parse_pdf(pdf_path)
    print(f"Stage 1 Complete: Generated {len(sections)} modular sections under '{output_dir}'.")
    return Path(output_dir)


def run_stage2(stage1_dir: str, output_dir: str, model: str) -> Path:
    """Execute Stage 2 decomposer."""
    print(f"=== [Stage 2] Decomposing architecture from: {stage1_dir} ===")
    decomposer = Stage2Decomposer(
        stage1_dir=stage1_dir, output_dir=output_dir, openai_model=model
    )
    summary = decomposer.decompose()
    print(
        f"Stage 2 Complete: System '{summary['system_name']}' decomposed into "
        f"{summary['total_modules']} modules at '{output_dir}'."
    )
    return Path(output_dir)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="archdoc2modules",
        description="Two-stage pipeline for extracting and decomposing PDF hardware specifications.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose debug logging"
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")

    # Command: run (end-to-end)
    run_parser = subparsers.add_parser("run", help="Run end-to-end Stage 1 and Stage 2 pipeline")
    run_parser.add_argument("--pdf", required=True, type=str, help="Path to input PDF specification")
    run_parser.add_argument(
        "--stage1-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Intermediate directory for Stage 1 parsed outputs",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE2_OUTPUT_DIR),
        help="Final output directory for decomposed modules",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_OPENAI_MODEL,
        help="OpenAI model identifier for Stage 2 decomposition (default gpt-4o)",
    )

    # Command: stage1
    s1_parser = subparsers.add_parser("stage1", help="Run Stage 1 only (PDF to MD + Assets)")
    s1_parser.add_argument("--pdf", required=True, type=str, help="Path to input PDF specification")
    s1_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Directory to save Stage 1 sections and assets",
    )

    # Command: stage2
    s2_parser = subparsers.add_parser("stage2", help="Run Stage 2 only (Decomposition)")
    s2_parser.add_argument(
        "--input-dir",
        type=str,
        default=str(DEFAULT_STAGE1_OUTPUT_DIR),
        help="Directory containing Stage 1 manifest and sections",
    )
    s2_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_STAGE2_OUTPUT_DIR),
        help="Directory to save decomposed modules",
    )
    s2_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_OPENAI_MODEL,
        help="OpenAI model identifier for Stage 2 decomposition",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.command == "run":
            stage1_path = run_stage1(args.pdf, args.stage1_dir)
            run_stage2(str(stage1_path), args.output_dir, args.model)
        elif args.command == "stage1":
            run_stage1(args.pdf, args.output_dir)
        elif args.command == "stage2":
            run_stage2(args.input_dir, args.output_dir, args.model)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
