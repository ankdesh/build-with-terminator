"""Benchmark scorer for classifying repair outcomes, detecting regressions, and exporting reports.

Computes fine-grained verdicts:
  - CLEAN_SUCCESS: 0 violations remaining, 0 regressions
  - PARTIAL_SUCCESS: violation count strictly reduced, 0 regressions
  - REGRESSION: new violation categories introduced or total violation count increased
  - FAILED_UNCHANGED: violation count unchanged
  - EXECUTION_ERROR: patch execution failed, timed out, or missing output
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from klayout_drc.benchmark.types import (
    BenchmarkCaseSpec,
    BenchmarkSummary,
    BenchmarkVerdict,
    DifficultyTier,
    EvaluationResult,
)


class BenchmarkScorer:
    """Evaluates and scores repair candidates across benchmark cases."""

    @staticmethod
    def classify_verdict(
        initial_violations: Dict[str, int],
        final_violations: Dict[str, int],
        execution_error: Optional[str] = None,
    ) -> BenchmarkVerdict:
        """Classify evaluation outcome into a strongly typed BenchmarkVerdict.

        Args:
            initial_violations: Mapping of rule_id -> count before fix.
            final_violations: Mapping of rule_id -> count after fix.
            execution_error: Error message if repair execution crashed or timed out.

        Returns:
            BenchmarkVerdict classification.
        """
        if execution_error is not None:
            return BenchmarkVerdict.EXECUTION_ERROR

        initial_total = sum(initial_violations.values())
        final_total = sum(final_violations.values())

        # Check for regressions: any rule with violations present in final that wasn't in initial
        initial_rules: Set[str] = {r for r, count in initial_violations.items() if count > 0}
        final_rules: Set[str] = {r for r, count in final_violations.items() if count > 0}

        new_rules = final_rules - initial_rules
        if len(new_rules) > 0 or final_total > initial_total:
            return BenchmarkVerdict.REGRESSION

        if final_total == 0:
            return BenchmarkVerdict.CLEAN_SUCCESS

        if final_total < initial_total:
            return BenchmarkVerdict.PARTIAL_SUCCESS

        return BenchmarkVerdict.FAILED_UNCHANGED

    @classmethod
    def aggregate(
        cls,
        benchmark_version: str,
        mode: str,
        results: List[EvaluationResult],
        total_runtime_s: float,
    ) -> BenchmarkSummary:
        """Aggregate list of EvaluationResult instances into a BenchmarkSummary.

        Args:
            benchmark_version: Benchmark suite version.
            mode: Evaluation solver mode (e.g. 'heuristic', 'agent').
            results: List of individual case outcomes.
            total_runtime_s: Total elapsed seconds.

        Returns:
            Aggregated BenchmarkSummary instance.
        """
        total_cases = len(results)
        clean_count = sum(1 for r in results if r.verdict == BenchmarkVerdict.CLEAN_SUCCESS)
        partial_count = sum(1 for r in results if r.verdict == BenchmarkVerdict.PARTIAL_SUCCESS)
        regression_count = sum(1 for r in results if r.verdict == BenchmarkVerdict.REGRESSION)
        failed_count = sum(1 for r in results if r.verdict == BenchmarkVerdict.FAILED_UNCHANGED)
        error_count = sum(1 for r in results if r.verdict == BenchmarkVerdict.EXECUTION_ERROR)

        clean_rate = (clean_count / total_cases) if total_cases > 0 else 0.0

        # Breakdown by difficulty tier
        tier_breakdown: Dict[str, Dict[str, int]] = {}
        for tier in DifficultyTier:
            tier_results = [r for r in results if r.tier == tier]
            tier_breakdown[tier.value] = {
                "total": len(tier_results),
                "clean_success": sum(1 for r in tier_results if r.verdict == BenchmarkVerdict.CLEAN_SUCCESS),
                "partial_success": sum(1 for r in tier_results if r.verdict == BenchmarkVerdict.PARTIAL_SUCCESS),
                "regression": sum(1 for r in tier_results if r.verdict == BenchmarkVerdict.REGRESSION),
                "failed_unchanged": sum(1 for r in tier_results if r.verdict == BenchmarkVerdict.FAILED_UNCHANGED),
                "execution_error": sum(1 for r in tier_results if r.verdict == BenchmarkVerdict.EXECUTION_ERROR),
            }

        # Breakdown by rule family
        rule_breakdown: Dict[str, Dict[str, int]] = {}
        all_rules = sorted({r.rule_id for r in results})
        for rule_id in all_rules:
            rule_results = [r for r in results if r.rule_id == rule_id]
            rule_breakdown[rule_id] = {
                "total": len(rule_results),
                "clean_success": sum(1 for r in rule_results if r.verdict == BenchmarkVerdict.CLEAN_SUCCESS),
                "partial_success": sum(1 for r in rule_results if r.verdict == BenchmarkVerdict.PARTIAL_SUCCESS),
                "regression": sum(1 for r in rule_results if r.verdict == BenchmarkVerdict.REGRESSION),
                "failed_unchanged": sum(1 for r in rule_results if r.verdict == BenchmarkVerdict.FAILED_UNCHANGED),
                "execution_error": sum(1 for r in rule_results if r.verdict == BenchmarkVerdict.EXECUTION_ERROR),
            }

        return BenchmarkSummary(
            benchmark_version=benchmark_version,
            mode=mode,
            total_cases=total_cases,
            clean_success_count=clean_count,
            partial_success_count=partial_count,
            regression_count=regression_count,
            failed_unchanged_count=failed_count,
            execution_error_count=error_count,
            clean_success_rate=clean_rate,
            total_runtime_s=total_runtime_s,
            tier_breakdown=tier_breakdown,
            rule_breakdown=rule_breakdown,
            results=results,
        )

    @staticmethod
    def export_json(summary: BenchmarkSummary, output_path: Path) -> None:
        """Export benchmark summary to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2)

    @staticmethod
    def export_csv(summary: BenchmarkSummary, output_path: Path) -> None:
        """Export case-level results to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "case_id",
            "rule_id",
            "tier",
            "mode",
            "initial_total",
            "final_total",
            "verdict",
            "area_added_um2",
            "area_removed_um2",
            "execution_time_s",
            "error_message",
            "run_dir",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in summary.results:
                row = r.to_dict()
                # Omit nested dicts for CSV flatness
                row.pop("initial_violations", None)
                row.pop("final_violations", None)
                writer.writerow(row)

    @staticmethod
    def export_markdown(summary: BenchmarkSummary) -> str:
        """Generate human-readable markdown summary report."""
        lines: List[str] = []
        lines.append(f"# ASAP7 DRC Benchmark Evaluation Report")
        lines.append(f"")
        lines.append(f"- **Benchmark Version**: `{summary.benchmark_version}`")
        lines.append(f"- **Evaluation Mode**: `{summary.mode}`")
        lines.append(f"- **Total Cases Evaluated**: `{summary.total_cases}`")
        lines.append(f"- **Clean Success Rate**: `{summary.clean_success_rate * 100:.1f}%` ({summary.clean_success_count}/{summary.total_cases})")
        lines.append(f"- **Total Runtime**: `{summary.total_runtime_s:.2f}s`")
        lines.append(f"")
        lines.append(f"### High-Level Verdict Summary")
        lines.append(f"| Verdict | Count | Share |")
        lines.append(f"| :--- | :--- | :--- |")
        lines.append(f"| **Clean Success** | {summary.clean_success_count} | {summary.clean_success_count / summary.total_cases * 100:.1f}% |")
        lines.append(f"| **Partial Success** | {summary.partial_success_count} | {summary.partial_success_count / summary.total_cases * 100:.1f}% |")
        lines.append(f"| **Regression** | {summary.regression_count} | {summary.regression_count / summary.total_cases * 100:.1f}% |")
        lines.append(f"| **Failed Unchanged** | {summary.failed_unchanged_count} | {summary.failed_unchanged_count / summary.total_cases * 100:.1f}% |")
        lines.append(f"| **Execution Error** | {summary.execution_error_count} | {summary.execution_error_count / summary.total_cases * 100:.1f}% |")
        lines.append(f"")

        lines.append(f"### Breakdown by Difficulty Tier")
        lines.append(f"| Tier | Total | Clean Success | Partial | Regression | Unchanged | Error | Pass Rate |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for tier_name, stats in summary.tier_breakdown.items():
            tot = stats["total"]
            clean = stats["clean_success"]
            rate_str = f"{clean / tot * 100:.1f}%" if tot > 0 else "N/A"
            lines.append(
                f"| `{tier_name}` | {tot} | {clean} | {stats['partial_success']} | {stats['regression']} | {stats['failed_unchanged']} | {stats['execution_error']} | {rate_str} |"
            )
        lines.append(f"")

        lines.append(f"### Breakdown by Rule Family")
        lines.append(f"| Rule | Total | Clean Success | Partial | Regression | Unchanged | Error | Pass Rate |")
        lines.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for rule_id, stats in summary.rule_breakdown.items():
            tot = stats["total"]
            clean = stats["clean_success"]
            rate_str = f"{clean / tot * 100:.1f}%" if tot > 0 else "N/A"
            lines.append(
                f"| `{rule_id}` | {tot} | {clean} | {stats['partial_success']} | {stats['regression']} | {stats['failed_unchanged']} | {stats['execution_error']} | {rate_str} |"
            )
        lines.append(f"")

        return "\n".join(lines)
