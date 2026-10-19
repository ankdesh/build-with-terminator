"""Command-line interface for running KLayout DRC, context processors, and report generators.

Supports fine-grained operations matching the flow graph nodes, as well as end-to-end execution,
with human-readable text and structured JSON output for the DeepSeek Harness subsystem.
"""

import argparse
import json
import sys
from pathlib import Path

from .config import (
    DEFAULT_FIX_SCRIPT_PATH,
    DEFAULT_GDS_PATH,
    DEFAULT_DRC_SCRIPT_PATH,
    DEFAULT_KNOWLEDGE_DIR,
    DEFAULT_REPORT_DB_PATH,
    DEFAULT_TEXT_REPORT_PATH,
    DEFAULT_WINDOW_HALO_UM,
    DRCJobConfig,
    DRCError,
    DRCConfigurationError,
)
from .runner import DRCRunner
from .parser import DRCParser
from .reporter import DRCReporter
from .fixer import DRCFixer
from .drc_context import DRCContextProcessor
from .gds_context import GDSContextProcessor
from .knowledge_loader import KnowledgeLoader


def run_pipeline(
    input_gds: Path,
    drc_script: Path,
    output_lyrdb: Path,
    text_report_path: Path | None = None,
) -> dict:
    """Execute end-to-end DRC check, parse results, and generate textual report."""
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


def execute_run_drc(input_gds: Path, drc_script: Path, output_lyrdb: Path) -> dict:
    """Execute DRC batch check only and return database path and violation count."""
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

    return {
        "status": "success",
        "input_gds": str(input_gds.resolve()),
        "drc_script": str(drc_script.resolve()),
        "report_db": str(report_file.resolve()),
        "total_violations": data.total_violations,
        "rule_summary": reporter.get_summary(),
    }


def execute_violation_context(report_db: Path, text_report_path: Path | None = None) -> dict:
    """Parse .lyrdb database and format formatted textual violations."""
    parser = DRCParser()
    data = parser.parse(report_db)
    reporter = DRCReporter(data)
    text_report = reporter.generate_textual_report()

    written_text_path = None
    if text_report_path:
        written_text_path = reporter.write_textual_report(text_report_path)

    return {
        "status": "success",
        "report_db": str(report_db.resolve()),
        "total_violations": data.total_violations,
        "rule_summary": reporter.get_summary(),
        "violations_text": text_report,
        "text_report_file": str(written_text_path.resolve()) if written_text_path else None,
    }


def execute_drc_context(drc_script: Path, report_db: Path) -> dict:
    """Extract DRC rule definitions matching violated categories found in .lyrdb."""
    parser = DRCParser()
    data = parser.parse(report_db)
    reporter = DRCReporter(data)
    violated_rules = list(reporter.get_summary().keys())

    proc = DRCContextProcessor(drc_script)
    rules_text = proc.format_as_text(violated_rules)

    return {
        "status": "success",
        "drc_script": str(drc_script.resolve()),
        "violated_rules": violated_rules,
        "drc_rules_text": rules_text,
    }


def execute_gds_context(gds_path: Path, report_db: Path, halo_um: float) -> dict:
    """Extract local layout windows around violation coordinates."""
    parser = DRCParser()
    data = parser.parse(report_db)

    proc = GDSContextProcessor(gds_path=gds_path, halo_um=halo_um)
    sections_text = proc.format_as_text(data)

    return {
        "status": "success",
        "gds_path": str(gds_path.resolve()),
        "halo_um": halo_um,
        "gds_sections_text": sections_text,
    }


def execute_load_knowledge(knowledge_dir: Path) -> dict:
    """Load and concatenate all markdown files from the knowledge directory."""
    loader = KnowledgeLoader(knowledge_dir)
    knowledge_text = loader.format_as_text()

    return {
        "status": "success",
        "knowledge_dir": str(knowledge_dir.resolve()),
        "knowledge_text": knowledge_text,
    }


def execute_save_script(script_content: str, output_path: Path) -> dict:
    """Save generated Python script to disk."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script_content, encoding="utf-8")

    return {
        "status": "success",
        "saved_path": str(output_path),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run KLayout DRC and context processors for LLM layout repair."
    )
    parser.add_argument(
        "--mode",
        choices=["full", "run-drc", "violation-ctx", "drc-ctx", "gds-ctx", "load-knowledge", "save-script"],
        default="full",
        help="Pipeline mode to execute (default: %(default)s)",
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
        help="Path for generated/existing .lyrdb database (default: %(default)s)",
    )
    parser.add_argument(
        "--text-report",
        "-t",
        type=Path,
        default=DEFAULT_TEXT_REPORT_PATH,
        help="Path for generated textual report (default: %(default)s)",
    )
    parser.add_argument(
        "--knowledge-dir",
        "-k",
        type=Path,
        default=DEFAULT_KNOWLEDGE_DIR,
        help="Path to markdown knowledge base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--halo-um",
        type=float,
        default=DEFAULT_WINDOW_HALO_UM,
        help="Halo window margin in micrometers around violations (default: %(default)s)",
    )
    parser.add_argument(
        "--output-script",
        type=Path,
        default=DEFAULT_FIX_SCRIPT_PATH,
        help="Destination path for generated Python fix script (default: %(default)s)",
    )
    parser.add_argument(
        "--script-content",
        type=str,
        help="Content string of Python script when using --mode save-script",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON to stdout instead of standard text.",
    )
    parser.add_argument(
        "--fix-output",
        type=Path,
        help="If specified (in full mode), programmatically repair violations and output healed GDS.",
    )

    args = parser.parse_args()

    try:
        if args.mode == "run-drc":
            results = execute_run_drc(args.gds, args.deck, args.report_db)
        elif args.mode == "violation-ctx":
            results = execute_violation_context(args.report_db, args.text_report)
        elif args.mode == "drc-ctx":
            results = execute_drc_context(args.deck, args.report_db)
        elif args.mode == "gds-ctx":
            results = execute_gds_context(args.gds, args.report_db, args.halo_um)
        elif args.mode == "load-knowledge":
            results = execute_load_knowledge(args.knowledge_dir)
        elif args.mode == "save-script":
            if not args.script_content:
                # Read from stdin if not passed via argument
                content = sys.stdin.read()
            else:
                content = args.script_content
            results = execute_save_script(content, args.output_script)
        else:
            # Full mode
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
            if "violations_text" in results:
                print(results["violations_text"])
            elif "drc_rules_text" in results:
                print(results["drc_rules_text"])
            elif "gds_sections_text" in results:
                print(results["gds_sections_text"])
            elif "knowledge_text" in results:
                print(results["knowledge_text"])
            elif "textual_report" in results:
                print(results["textual_report"])
            elif "saved_path" in results:
                print(f"Script saved to: {results['saved_path']}")
            else:
                print(json.dumps(results, indent=2))

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
