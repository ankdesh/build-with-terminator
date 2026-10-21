"""Run reporter and audit artifact generator.

Compares before/after DRC reports, validates physical changes, assigns truthful verdicts,
and writes structured results.json and human-readable report.md into the run bundle.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Final

from .repair_executor import ExecutionResult
from .validator import ValidationResult
from .layout_diff import LayoutDiffReport

# Typed Verdict Constants
VERDICT_SUCCESS_GEOMETRY_ONLY: Final[str] = "success_geometry_only"
VERDICT_PARTIAL: Final[str] = "partial"
VERDICT_NO_CHANGE: Final[str] = "no_change"
VERDICT_INVALID_PATCH: Final[str] = "invalid_patch"
VERDICT_MODEL_ERROR: Final[str] = "model_error"
VERDICT_TIMEOUT: Final[str] = "timeout"
VERDICT_DRC_ERROR: Final[str] = "drc_error"


@dataclass(frozen=True)
class EvaluationSummary:
    """Consolidated summary of a single-shot layout evaluation."""

    verdict: str
    validation_level: str
    total_before: int
    total_after: int | None
    violations_before: dict[str, int]
    violations_after: dict[str, int] | None
    execution_result: ExecutionResult
    validation_result: ValidationResult | None
    diff_report: LayoutDiffReport | None
    error_message: str | None = None


class RunReporter:
    """Generates auditable reports and structured results for single-shot evaluations."""

    def __init__(
        self,
        run_id: str,
        case_name: str,
        profile_name: str,
        candidate_mode: str,
        output_dir: Path,
    ) -> None:
        """Initialize reporter with run metadata and destination directory."""
        self.run_id = run_id
        self.case_name = case_name
        self.profile_name = profile_name
        self.candidate_mode = candidate_mode
        self.output_dir = Path(output_dir).resolve()

    def evaluate(
        self,
        execution: ExecutionResult,
        violations_before: dict[str, int],
        total_before: int,
        violations_after: dict[str, int] | None = None,
        total_after: int | None = None,
        validation: ValidationResult | None = None,
        diff_report: LayoutDiffReport | None = None,
        generation_error: str | None = None,
        drc_error: str | None = None,
    ) -> EvaluationSummary:
        """Assign typed verdict based on observed execution, validation, and DRC signals."""
        if generation_error:
            verdict = VERDICT_MODEL_ERROR
        elif drc_error:
            verdict = VERDICT_DRC_ERROR
        elif execution.status == "timeout":
            verdict = VERDICT_TIMEOUT
        elif execution.status in ("syntax_error", "nonzero_exit", "missing_output"):
            verdict = VERDICT_INVALID_PATCH
        elif validation is not None and not validation.is_valid:
            verdict = VERDICT_INVALID_PATCH
        elif total_after is None:
            verdict = VERDICT_DRC_ERROR
        elif total_after == 0:
            verdict = VERDICT_SUCCESS_GEOMETRY_ONLY
        elif total_after < total_before:
            verdict = VERDICT_PARTIAL
        elif total_after == total_before:
            verdict = VERDICT_NO_CHANGE
        else:
            verdict = VERDICT_INVALID_PATCH

        return EvaluationSummary(
            verdict=verdict,
            validation_level="geometry_only",
            total_before=total_before,
            total_after=total_after,
            violations_before=violations_before,
            violations_after=violations_after,
            execution_result=execution,
            validation_result=validation,
            diff_report=diff_report,
            error_message=generation_error or drc_error or execution.error_message,
        )

    def write_results_json(self, summary: EvaluationSummary, output_path: Path) -> dict[str, Any]:
        """Write structured results.json artifact."""
        data: dict[str, Any] = {
            "run_id": self.run_id,
            "case_name": self.case_name,
            "profile_name": self.profile_name,
            "candidate_mode": self.candidate_mode,
            "verdict": summary.verdict,
            "validation_level": summary.validation_level,
            "caveats": [
                "Truthful reporting: DRC clean does not prove electrical connectivity (LVS unverified)."
            ],
            "drc_metrics": {
                "total_before": summary.total_before,
                "total_after": summary.total_after,
                "violations_before": summary.violations_before,
                "violations_after": summary.violations_after,
            },
            "execution": {
                "status": summary.execution_result.status,
                "exit_code": summary.execution_result.exit_code,
                "duration_seconds": round(summary.execution_result.duration_seconds, 4),
                "error_message": summary.error_message,
            },
            "validation": summary.validation_result.to_dict() if summary.validation_result else None,
            "layout_diff": summary.diff_report.to_dict() if summary.diff_report else None,
        }
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def write_report_md(self, summary: EvaluationSummary, output_path: Path) -> str:
        """Write human-readable report.md artifact."""
        lines = [
            f"# Layout Repair Evaluation Report: {self.case_name}",
            "",
            f"- **Run ID:** `{self.run_id}`",
            f"- **Profile:** `{self.profile_name}`",
            f"- **Candidate Mode:** `{self.candidate_mode}`",
            f"- **Verdict:** **`{summary.verdict}`**",
            f"- **Validation Level:** `{summary.validation_level}`",
            "",
            "## 1. DRC Comparison Before vs After",
            "",
            "| Rule Name | Before (Baseline) | After (Patched) | Delta |",
            "|---|---|---|---|",
        ]

        all_rules = sorted(
            set(summary.violations_before.keys())
            | set((summary.violations_after or {}).keys())
        )
        if all_rules:
            for rule in all_rules:
                count_before = summary.violations_before.get(rule, 0)
                count_after = (
                    summary.violations_after.get(rule, 0)
                    if summary.violations_after is not None
                    else "N/A"
                )
                delta = (
                    count_after - count_before
                    if isinstance(count_after, int)
                    else "N/A"
                )
                lines.append(f"| `{rule}` | {count_before} | {count_after} | {delta} |")
            lines.append(
                f"| **TOTAL** | **{summary.total_before}** | "
                f"**{summary.total_after if summary.total_after is not None else 'N/A'}** | |"
            )
        else:
            lines.append("| (No violations detected) | 0 | 0 | 0 |")

        lines.extend([
            "",
            "## 2. Patch Execution & Diagnostics",
            "",
            f"- **Status:** `{summary.execution_result.status}`",
            f"- **Exit Code:** `{summary.execution_result.exit_code}`",
            f"- **Duration:** {summary.execution_result.duration_seconds:.3f} s",
        ])

        if summary.error_message:
            lines.extend([
                "",
                "### Error Details",
                f"```text\n{summary.error_message}\n```",
            ])

        lines.extend([
            "",
            "## 3. Layout Integrity & Diff",
        ])

        if summary.validation_result:
            vr = summary.validation_result
            lines.extend([
                f"- **Top Cell:** `{vr.top_cell_name}`",
                f"- **Database Unit (DBU):** `{vr.dbu_um} µm`",
                f"- **Total Shapes:** {vr.total_shapes}",
                f"- **Bounding Box:** `{vr.bbox_um}`",
                f"- **Integrity Valid:** `{vr.is_valid}`",
            ])
            if vr.violations:
                lines.append("- **Integrity Violations:**")
                for viol in vr.violations:
                    lines.append(f"  - ⚠️ {viol}")
        else:
            lines.append("- Layout validation was skipped (no valid output layout produced).")

        if summary.diff_report:
            dr = summary.diff_report
            lines.extend([
                "",
                "### Geometric Area Delta",
                f"- **Total Added Area:** {dr.total_added_area_um2:.4f} µm²",
                f"- **Total Removed Area:** {dr.total_removed_area_um2:.4f} µm²",
                f"- **Net Area Delta:** {dr.net_area_delta_um2:.4f} µm²",
                f"- **Modified Layers:** `{dr.modified_layers}`",
            ])

        lines.extend([
            "",
            "## 4. Caveats & Scope Limitations",
            "",
            "> [!NOTE]",
            "> A DRC pass confirms geometric compliance with the checked rule deck only.",
            "> It does not verify netlist extraction or electrical continuity/short freedom (LVS unverified).",
            "",
        ])

        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return content
