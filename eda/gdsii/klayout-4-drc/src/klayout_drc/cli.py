"""Command-line interface for running KLayout DRC, context processors, and report generators.

Supports fine-grained operations matching the flow graph nodes, as well as end-to-end execution,
with human-readable text and structured JSON output for the DeepSeek Harness subsystem.
"""

import argparse
import json
import sys
from pathlib import Path

from .config import (
    DEFAULT_DATA_DIR,
    DEFAULT_FIX_SCRIPT_PATH,
    DEFAULT_GDS_PATH,
    DEFAULT_DRC_SCRIPT_PATH,
    DEFAULT_KNOWLEDGE_DIR,
    DEFAULT_REPORT_DB_PATH,
    DEFAULT_TEXT_REPORT_PATH,
    DEFAULT_WINDOW_HALO_UM,
    DEFAULT_RUNS_DIR,
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
from .profile import DRCProfileManager
from .run_manifest import RunSpec
from .single_shot import SingleShotOrchestrator
from .benchmark.generator import BenchmarkGenerator
from .benchmark.manifest import BenchmarkManifestManager
from .benchmark.evaluator import BenchmarkEvaluator
from .benchmark.types import DifficultyTier

DEFAULT_BENCHMARK_DIR: Path = DEFAULT_DATA_DIR / "benchmark_v1"


def execute_benchmark_list(
    benchmark_dir: Path,
    rules: list[str] | None = None,
    tiers: list[str] | None = None,
    limit: int | None = None,
) -> dict:
    """List benchmark cases with filtering options."""
    manifest_path = benchmark_dir / "manifest.json"
    manifest = BenchmarkManifestManager.load(manifest_path)

    parsed_tiers = [DifficultyTier(t.strip().lower()) for t in tiers] if tiers else None
    filtered = BenchmarkManifestManager.filter_cases(manifest, rules=rules, tiers=parsed_tiers, limit=limit)

    return {
        "status": "success",
        "benchmark_version": manifest.benchmark_version,
        "total_manifest_cases": manifest.case_count,
        "filtered_count": len(filtered),
        "cases": [c.to_dict() for c in filtered],
    }


def execute_benchmark_verify(benchmark_dir: Path) -> dict:
    """Verify cryptographic integrity of benchmark GDS files against manifest."""
    manifest_path = benchmark_dir / "manifest.json"
    manifest = BenchmarkManifestManager.load(manifest_path)
    integrity = BenchmarkManifestManager.verify_integrity(manifest, benchmark_dir)
    from .benchmark.acceptance import verify_case
    profile = DRCProfileManager().get_profile("asap7_curated")
    for case in manifest.cases:
        try:
            verify_case(case, benchmark_dir, profile)
        except (ValueError, OSError, DRCError):
            integrity[case.case_id] = False

    failed = [case_id for case_id, ok in integrity.items() if not ok]
    all_ok = len(failed) == 0

    return {
        "status": "success" if all_ok else "failed",
        "benchmark_version": manifest.benchmark_version,
        "total_cases": manifest.case_count,
        "verified_cases": sum(1 for ok in integrity.values() if ok),
        "failed_cases": failed,
        "all_valid": all_ok,
    }


def execute_benchmark_generate(output_dir: Path) -> dict:
    """Deterministically regenerate benchmark dataset and manifest."""
    generator = BenchmarkGenerator()
    manifest = generator.generate_all(output_dir)
    return {
        "status": "success",
        "output_dir": str(output_dir.resolve()),
        "case_count": manifest.case_count,
        "benchmark_version": manifest.benchmark_version,
    }


def execute_benchmark_evaluate(
    benchmark_dir: Path,
    output_dir: Path | None = None,
    candidate_mode: str = "heuristic",
    candidate_script: Path | None = None,
    rules: list[str] | None = None,
    tiers: list[str] | None = None,
    limit: int | None = None,
    profile_name: str = "asap7_curated",
) -> dict:
    """Execute single-shot repair evaluation across benchmark cases."""
    manifest_path = benchmark_dir / "manifest.json"
    manifest = BenchmarkManifestManager.load(manifest_path)

    parsed_tiers = [DifficultyTier(t.strip().lower()) for t in tiers] if tiers else None
    filtered_cases = BenchmarkManifestManager.filter_cases(manifest, rules=rules, tiers=parsed_tiers, limit=limit)

    evaluator = BenchmarkEvaluator(
        base_dir=benchmark_dir,
        output_dir=output_dir,
        profile_name=profile_name,
    )
    summary = evaluator.evaluate_batch(
        cases=filtered_cases,
        mode=candidate_mode,
        candidate_script=candidate_script,
    )
    return {
        "status": "success",
        "output_dir": str(evaluator.output_dir.resolve()),
        "summary": summary.to_dict(),
    }


def run_pipeline(
    input_gds: Path,
    drc_script: Path,
    output_lyrdb: Path,
    text_report_path: Path | None = None,
    profile_name: str | None = None,
) -> dict:
    """Execute end-to-end DRC check, parse results, and generate textual report."""
    profile_mgr = DRCProfileManager()
    profile = profile_mgr.get_profile(profile_name) if profile_name else profile_mgr.find_profile_for_deck(drc_script)
    config = DRCJobConfig(
        input_gds=input_gds,
        drc_script=drc_script,
        output_lyrdb=output_lyrdb,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
        extra_params=profile.extra_params,
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


def execute_run_drc(
    input_gds: Path,
    drc_script: Path,
    output_lyrdb: Path,
    profile_name: str | None = None,
) -> dict:
    """Execute DRC batch check only and return database path and violation count."""
    profile_mgr = DRCProfileManager()
    profile = profile_mgr.get_profile(profile_name) if profile_name else profile_mgr.find_profile_for_deck(drc_script)
    config = DRCJobConfig(
        input_gds=input_gds,
        drc_script=drc_script,
        output_lyrdb=output_lyrdb,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
        extra_params=profile.extra_params,
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


def execute_violation_context(report_db: Path, text_report_path: Path | None = None, edit_policy: Path | None = None) -> dict:
    """Parse .lyrdb database and format formatted textual violations."""
    parser = DRCParser()
    data = parser.parse(report_db)
    if edit_policy:
        from .edit_policy import policy_report
        data = policy_report(data, edit_policy)
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


def execute_drc_context(drc_script: Path, report_db: Path, edit_policy: Path | None = None,
                        profile_name: str | None = None) -> dict:
    """Extract DRC rule definitions matching violated categories found in .lyrdb."""
    parser = DRCParser()
    data = parser.parse(report_db)
    if edit_policy:
        from .edit_policy import policy_report
        data = policy_report(data, edit_policy)
    reporter = DRCReporter(data)
    violated_rules = list(reporter.get_summary().keys())

    proc = DRCContextProcessor(drc_script)
    rules_text = proc.format_as_text(violated_rules)
    if profile_name == 'asap7_c2c3_v1':
        rules_text += ('\nC2+C3 checker qualification: DBU is 0.25 nm; the manufacturing grid is 1 nm. '
                       'The pinned V1.M2.EN.2 expression has a fine-DBU transition at 5.25 nm. '
                       'For its rectangular end-cap fixtures, a 6 nm cap is legal on the manufacturing grid; '
                       'a 5 nm cap is checker-illegal. Use this verified checker behavior rather than '
                       'the nominal 5 nm description. V2.M3.EN.2 passes with a 5 nm cap on this grid. '
                       'V2.M2.EN.1 requires at least two opposite sides enclosed by 5 nm.\n')

    return {
        "status": "success",
        "drc_script": str(drc_script.resolve()),
        "violated_rules": violated_rules,
        "drc_rules_text": rules_text,
    }


def execute_gds_context(gds_path: Path, report_db: Path, halo_um: float, edit_policy: Path | None = None) -> dict:
    """Extract local layout windows around violation coordinates."""
    parser = DRCParser()
    data = parser.parse(report_db)

    proc = GDSContextProcessor(gds_path=gds_path, halo_um=halo_um)
    if edit_policy:
        from .edit_policy import policy_context
        sections_text = json.dumps(policy_context(gds_path, json.loads(edit_policy.read_text())), sort_keys=True)
    else:
        sections_text = proc.format_as_text(data)

    return {
        "status": "success",
        "gds_path": str(gds_path.resolve()),
        "halo_um": halo_um,
        "gds_sections_text": sections_text,
    }


def execute_load_knowledge(knowledge_dir: Path, profile_name: str = "legacy_mini") -> dict:
    """Load and concatenate all markdown files from the knowledge directory."""
    loader = KnowledgeLoader(knowledge_dir, profile_name)
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


def execute_single_shot(
    input_gds: Path,
    drc_script: Path,
    profile_name: str | None = None,
    candidate_mode: str = "heuristic",
    candidate_script: Path | None = None,
    run_id: str | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> dict:
    """Execute single-shot evaluation: preflight DRC -> apply patch -> validate -> recheck -> report."""
    resolved_profile = profile_name or DRCProfileManager().find_profile_for_deck(drc_script).name
    spec = RunSpec(
        case_name=input_gds.stem,
        input_gds=input_gds,
        drc_script=drc_script,
        profile_name=resolved_profile,
        candidate_mode=candidate_mode,
        candidate_script=candidate_script,
        run_id=run_id,
        output_root=runs_dir,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    return {
        "status": "success" if summary.verdict == "success_geometry_only" else summary.verdict,
        "run_id": orchestrator.manifest_manager.run_id,
        "run_dir": str(orchestrator.paths.run_dir),
        "verdict": summary.verdict,
        "validation_level": summary.validation_level,
        "total_violations_before": summary.total_before,
        "total_violations_after": summary.total_after,
        "violations_before": summary.violations_before,
        "violations_after": summary.violations_after,
        "execution_status": summary.execution_result.status,
        "execution_duration": round(summary.execution_result.duration_seconds, 3),
        "error_message": summary.error_message,
        "report_md_file": str(orchestrator.paths.report_md),
        "results_json_file": str(orchestrator.paths.results_json),
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run KLayout DRC and context processors for LLM layout repair."
    )
    parser.add_argument(
        "--mode",
        choices=[
            "full",
            "single-shot",
            "run-drc",
            "violation-ctx",
            "drc-ctx",
            "gds-ctx",
            "load-knowledge",
            "save-script",
            "benchmark-list",
            "benchmark-verify",
            "benchmark-generate",
            "benchmark-evaluate",
        ],
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
    parser.add_argument(
        "--candidate-mode",
        choices=["script_file", "heuristic", "agent"],
        default="heuristic",
        help="Repair candidate source mode for single-shot evaluation (default: %(default)s)",
    )
    parser.add_argument(
        "--candidate-script",
        type=Path,
        help="Path to pre-existing Python repair script when using --candidate-mode script_file",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="DRC execution profile name (default: auto-detected from deck)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        help="Custom run ID override for isolated run directory naming",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help="Root directory for run evaluation bundles (default: %(default)s)",
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=DEFAULT_BENCHMARK_DIR,
        help="Root directory containing benchmark dataset (default: %(default)s)",
    )
    parser.add_argument(
        "--benchmark-rules",
        type=str,
        help="Comma-separated list of rule families to filter benchmark cases (e.g. M1.W.1,M2.W.1)",
    )
    parser.add_argument(
        "--benchmark-tiers",
        type=str,
        help="Comma-separated list of difficulty tiers to filter benchmark cases (e.g. isolated,boundary)",
    )
    parser.add_argument(
        "--benchmark-limit",
        type=int,
        help="Maximum number of benchmark cases to process",
    )
    parser.add_argument(
        "--benchmark-output",
        type=Path,
        help="Destination directory for benchmark evaluation results and summaries",
    )

    parser.add_argument("--edit-policy", type=Path, help="Public case edit policy JSON")
    args = parser.parse_args()

    try:
        if args.profile and args.deck == DEFAULT_DRC_SCRIPT_PATH and not any(a in sys.argv for a in ("--deck", "-d")):
            args.deck = DRCProfileManager().get_profile(args.profile).deck_path
        # Benchmark mode dispatches
        if args.mode == "benchmark-list":
            rules = [r.strip() for r in args.benchmark_rules.split(",")] if args.benchmark_rules else None
            tiers = [t.strip() for t in args.benchmark_tiers.split(",")] if args.benchmark_tiers else None
            results = execute_benchmark_list(
                benchmark_dir=args.benchmark_dir,
                rules=rules,
                tiers=tiers,
                limit=args.benchmark_limit,
            )
        elif args.mode == "benchmark-verify":
            results = execute_benchmark_verify(benchmark_dir=args.benchmark_dir)
        elif args.mode == "benchmark-generate":
            out_dir = args.benchmark_output or args.benchmark_dir
            results = execute_benchmark_generate(output_dir=out_dir)
        elif args.mode == "benchmark-evaluate":
            rules = [r.strip() for r in args.benchmark_rules.split(",")] if args.benchmark_rules else None
            tiers = [t.strip() for t in args.benchmark_tiers.split(",")] if args.benchmark_tiers else None
            results = execute_benchmark_evaluate(
                benchmark_dir=args.benchmark_dir,
                output_dir=args.benchmark_output,
                candidate_mode=args.candidate_mode,
                candidate_script=args.candidate_script,
                rules=rules,
                tiers=tiers,
                limit=args.benchmark_limit,
                profile_name=args.profile or "asap7_curated",
            )
        elif args.mode == "single-shot":
            results = execute_single_shot(
                input_gds=args.gds,
                drc_script=args.deck,
                profile_name=args.profile,
                candidate_mode=args.candidate_mode,
                candidate_script=args.candidate_script,
                run_id=args.run_id,
                runs_dir=args.runs_dir,
            )
        elif args.mode == "run-drc":
            results = execute_run_drc(args.gds, args.deck, args.report_db, profile_name=args.profile)
        elif args.mode == "violation-ctx":
            results = execute_violation_context(args.report_db, args.text_report, args.edit_policy)
        elif args.mode == "drc-ctx":
            results = execute_drc_context(args.deck, args.report_db, args.edit_policy, args.profile)
        elif args.mode == "gds-ctx":
            results = execute_gds_context(args.gds, args.report_db, args.halo_um, args.edit_policy)
        elif args.mode == "load-knowledge":
            results = execute_load_knowledge(args.knowledge_dir, args.profile or "legacy_mini")
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
                profile_name=args.profile,
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

        return 0 if results.get("status") == "success" else 1

    except DRCError as exc:
        from .api_reference import APIReferenceError
        detail = {"status": "error", "message": str(exc)}
        if isinstance(exc, APIReferenceError):
            detail['stage'] = 'api_reference'
        if args.json:
            print(json.dumps(detail), file=sys.stderr)
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
