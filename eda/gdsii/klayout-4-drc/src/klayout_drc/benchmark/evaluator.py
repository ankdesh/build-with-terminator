"""Benchmark evaluator for orchestrating single-shot repair evaluation across cases.

Integrates SingleShotOrchestrator with BenchmarkManifest and BenchmarkScorer,
providing batch evaluation, cost filtering, regression tracking, and reporting.
"""

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Dict, List, Optional
import shutil

from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.scorer import BenchmarkScorer
from klayout_drc.benchmark.types import (
    BenchmarkCaseSpec,
    BenchmarkManifest,
    BenchmarkSummary,
    BenchmarkVerdict,
    DifficultyTier,
    EvaluationResult,
)
from klayout_drc.config import DEFAULT_RUNS_DIR, DRCConfigurationError
from klayout_drc.profile import DRCProfileManager
from klayout_drc.run_manifest import RunSpec
from klayout_drc.single_shot import SingleShotOrchestrator


class BenchmarkEvaluator:
    """Executes single-shot repair evaluation across benchmark test cases."""

    def __init__(
        self,
        base_dir: Path,
        output_dir: Optional[Path] = None,
        profile_name: str = "asap7_curated",
        profile_manager: Optional[DRCProfileManager] = None,
    ) -> None:
        """Initialize evaluator.

        Args:
            base_dir: Root directory of benchmark dataset containing cases/ and manifest.json.
            output_dir: Destination directory for evaluation runs and summary reports.
            profile_name: DRC profile name (defaults to 'asap7_curated').
            profile_manager: Optional DRCProfileManager.
        """
        self.base_dir = base_dir
        self.profile_name = profile_name
        self.profile_manager = profile_manager or DRCProfileManager()

        if output_dir is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.output_dir = DEFAULT_RUNS_DIR / f"benchmark_{ts}"
        else:
            self.output_dir = output_dir

        self.runs_dir = self.output_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_case(
        self,
        case: BenchmarkCaseSpec,
        mode: str = "heuristic",
        candidate_script: Optional[Path] = None,
    ) -> EvaluationResult:
        """Run single-shot evaluation for a single benchmark case.

        Args:
            case: BenchmarkCaseSpec defining case metadata.
            mode: Solver mode ('heuristic', 'agent', 'script_file').
            candidate_script: Script path if mode is 'script_file'.

        Returns:
            EvaluationResult with fine-grained verdict and metrics.
        """
        gds_path = self.base_dir / case.gds_rel_path
        if not gds_path.exists():
            return EvaluationResult(
                case_id=case.case_id,
                rule_id=case.rule_id,
                tier=case.tier,
                mode=mode,
                initial_violations={},
                final_violations={},
                initial_total=case.expected_initial_violations,
                final_total=-1,
                verdict=BenchmarkVerdict.EXECUTION_ERROR,
                area_added_um2=0.0,
                area_removed_um2=0.0,
                execution_time_s=0.0,
                error_message=f"GDS file not found: {gds_path}",
            )

        start_time = time.perf_counter()
        profile = self.profile_manager.get_profile(self.profile_name)

        # Handle negative clean cases: if initially clean, verify 0 violations
        if case.tier == DifficultyTier.NEGATIVE and case.expected_initial_violations == 0:
            # For negative cases, the layout is already legal; evaluate no-op or pass-through
            spec = RunSpec(
                case_name=case.case_id,
                input_gds=gds_path,
                drc_script=profile.deck_path,
                profile_name=self.profile_name,
                candidate_mode="heuristic",
                output_root=self.runs_dir,
            )
            try:
                orchestrator = SingleShotOrchestrator(spec, self.profile_manager)
                summary = orchestrator.run()
                elapsed = time.perf_counter() - start_time

                init_v = summary.violations_before
                final_v = summary.violations_after or {}
                verdict = BenchmarkScorer.classify_verdict(init_v, final_v)

                return EvaluationResult(
                    case_id=case.case_id,
                    rule_id=case.rule_id,
                    tier=case.tier,
                    mode=mode,
                    initial_violations=init_v,
                    final_violations=final_v,
                    initial_total=summary.total_before,
                    final_total=summary.total_after if summary.total_after is not None else -1,
                    verdict=verdict,
                    area_added_um2=summary.diff_report.total_added_area_um2 if summary.diff_report else 0.0,
                    area_removed_um2=summary.diff_report.total_removed_area_um2 if summary.diff_report else 0.0,
                    execution_time_s=elapsed,
                    run_dir=str(orchestrator.paths.run_dir),
                )
            except Exception as exc:
                elapsed = time.perf_counter() - start_time
                return EvaluationResult(
                    case_id=case.case_id,
                    rule_id=case.rule_id,
                    tier=case.tier,
                    mode=mode,
                    initial_violations={},
                    final_violations={},
                    initial_total=0,
                    final_total=-1,
                    verdict=BenchmarkVerdict.EXECUTION_ERROR,
                    area_added_um2=0.0,
                    area_removed_um2=0.0,
                    execution_time_s=elapsed,
                    error_message=str(exc),
                )

        spec = RunSpec(
            case_name=case.case_id,
            input_gds=gds_path,
            drc_script=profile.deck_path,
            profile_name=self.profile_name,
            candidate_mode=mode,
            candidate_script=candidate_script,
            output_root=self.runs_dir,
        )

        try:
            orchestrator = SingleShotOrchestrator(spec, self.profile_manager)
            summary = orchestrator.run()
            elapsed = time.perf_counter() - start_time

            init_v = summary.violations_before
            final_v = summary.violations_after or {}
            verdict = BenchmarkScorer.classify_verdict(init_v, final_v, execution_error=summary.error_message)

            return EvaluationResult(
                case_id=case.case_id,
                rule_id=case.rule_id,
                tier=case.tier,
                mode=mode,
                initial_violations=init_v,
                final_violations=final_v,
                initial_total=summary.total_before,
                final_total=summary.total_after if summary.total_after is not None else -1,
                verdict=verdict,
                area_added_um2=summary.diff_report.total_added_area_um2 if summary.diff_report else 0.0,
                area_removed_um2=summary.diff_report.total_removed_area_um2 if summary.diff_report else 0.0,
                execution_time_s=elapsed,
                error_message=summary.error_message,
                run_dir=str(orchestrator.paths.run_dir),
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            return EvaluationResult(
                case_id=case.case_id,
                rule_id=case.rule_id,
                tier=case.tier,
                mode=mode,
                initial_violations={},
                final_violations={},
                initial_total=case.expected_initial_violations,
                final_total=-1,
                verdict=BenchmarkVerdict.EXECUTION_ERROR,
                area_added_um2=0.0,
                area_removed_um2=0.0,
                execution_time_s=elapsed,
                error_message=str(exc),
            )

    def evaluate_batch(
        self,
        cases: List[BenchmarkCaseSpec],
        mode: str = "heuristic",
        candidate_script: Optional[Path] = None,
        verbose: bool = True,
    ) -> BenchmarkSummary:
        """Run evaluation across a batch of benchmark cases.

        Args:
            cases: List of BenchmarkCaseSpec to evaluate.
            mode: Solver mode ('heuristic', 'agent', 'script_file').
            candidate_script: Script path if mode is 'script_file'.
            verbose: If True, prints progress to console.

        Returns:
            Aggregated BenchmarkSummary instance.
        """
        results: List[EvaluationResult] = []
        start_batch = time.perf_counter()

        for idx, case in enumerate(cases, 1):
            if verbose:
                print(f"[{idx}/{len(cases)}] Evaluating {case.case_id} ({case.rule_id}, tier={case.tier.value})...", end=" ", flush=True)

            res = self.evaluate_case(case, mode=mode, candidate_script=candidate_script)
            results.append(res)

            if verbose:
                print(f"-> {res.verdict.value.upper()} (init={res.initial_total}, final={res.final_total}, time={res.execution_time_s:.2f}s)")

        total_runtime = time.perf_counter() - start_batch
        manifest_path = self.base_dir / "manifest.json"
        version = "1.0.0"
        if manifest_path.exists():
            try:
                m = BenchmarkManifestManager.load(manifest_path)
                version = m.benchmark_version
            except Exception:
                pass

        summary = BenchmarkScorer.aggregate(
            benchmark_version=version,
            mode=mode,
            results=results,
            total_runtime_s=total_runtime,
        )

        # Export report files to output directory
        json_path = self.output_dir / "summary.json"
        csv_path = self.output_dir / "summary.csv"
        md_path = self.output_dir / "report.md"

        BenchmarkScorer.export_json(summary, json_path)
        BenchmarkScorer.export_csv(summary, csv_path)
        md_content = BenchmarkScorer.export_markdown(summary)
        md_path.write_text(md_content, encoding="utf-8")

        if verbose:
            print(f"\nEvaluation Complete! Results saved to {self.output_dir}")
            print(f"Clean Success Rate: {summary.clean_success_rate * 100:.1f}% ({summary.clean_success_count}/{summary.total_cases})")

        return summary
