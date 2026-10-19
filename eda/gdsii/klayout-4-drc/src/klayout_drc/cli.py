"""Command-line interface for running KLayout DRC and generating reports.

Supports both human-readable console execution and structured JSON output
for seamless integration with the DeepSeek Harness flow system.
"""

import argparse
import json
import sys
from pathlib import Path

from .config import (
    DEFAULT_GDS_PATH,
    DEFAULT_DRC_SCRIPT_PATH,
    DEFAULT_REPORT_DB_PATH,
    DEFAULT_TEXT_REPORT_PATH,
    DRCJobConfig,
    DRCError,
)
from .runner import DRCRunner
from .parser import DRCParser
from .reporter import DRCReporter
from .fixer import DRCFixer


def run_pipeline(
    input_gds: Path,
    drc_script: Path,
    output_lyrdb: Path,
    text_report_path: Path | None = None,
) -> dict:
    """Execute end-to-end DRC check, parse results, and generate textual report.
    
    Args:
        input_gds: Path to input GDS layout.
        drc_script: Path to KLayout DRC deck.
        output_lyrdb: Destination path for .lyrdb report database.
        text_report_path: Optional path to save formatted text report.
        
    Returns:
        dict: Structured result dictionary with metrics and report text.
    """
    config = DRCJobConfig(
        input_gds=input_gds,
        drc_script=drc_script,
        output_lyrdb=output_lyrdb,
    )
    runner = DRCRunner(config)
    report_file = runner.run()

    parser = DRCParser()
    data = parser.parse(report_file)

    reporter = DRCReporter(data)
    text_report = reporter.generate_textual_report()

    written_text_path = None
    if text_report_path:
        written_text_path = reporter.write_textual_report(text_report_path)

    return {
        "status": "success",
        "input_gds": str(input_gds.resolve()),
        "drc_script": str(drc_script.resolve()),
        "report_db": str(report_file.resolve()),
        "text_report_file": str(written_text_path.resolve()) if written_text_path else None,
        "total_violations": data.total_violations,
        "rule_summary": reporter.get_summary(),
        "textual_report": text_report,
        "details": data.to_dict(),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run KLayout DRC in batch mode and generate textual and structured reports."
    )
    parser.add_argument(
        "--gds",
        "-g",
        type=Path,
        default=DEFAULT_GDS_PATH,
        help="Path to input GDS layout file (default: %(default)s)",
    )
    parser.add_argument(
        "--deck",
        "-d",
        type=Path,
        default=DEFAULT_DRC_SCRIPT_PATH,
        help="Path to KLayout DRC script (default: %(default)s)",
    )
    parser.add_argument(
        "--report-db",
        "-r",
        type=Path,
        default=DEFAULT_REPORT_DB_PATH,
        help="Path for generated .lyrdb database (default: %(default)s)",
    )
    parser.add_argument(
        "--text-report",
        "-t",
        type=Path,
        default=DEFAULT_TEXT_REPORT_PATH,
        help="Path for generated textual report (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON to stdout instead of standard human text.",
    )
    parser.add_argument(
        "--fix-output",
        type=Path,
        help="If specified, programmatically repair violations and output healed GDS.",
    )

    args = parser.parse_args()

    try:
        results = run_pipeline(
            input_gds=args.gds,
            drc_script=args.deck,
            output_lyrdb=args.report_db,
            text_report_path=args.text_report,
        )

        if args.fix_output:
            fixer = DRCFixer(input_gds=args.gds, output_gds=args.fix_output)
            fixed_gds = fixer.fix()
            results["fixed_gds"] = str(fixed_gds.resolve())

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(results["textual_report"])
            if args.fix_output:
                print(f"Repaired layout written to: {args.fix_output}")

        return 0

    except DRCError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "fatal", "message": str(exc)}), file=sys.stderr)
        else:
            print(f"Fatal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
