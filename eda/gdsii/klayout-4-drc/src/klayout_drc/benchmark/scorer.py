"""Gate-aware geometry-only scoring and consistent report exports."""
import csv
import json
from collections import Counter
from pathlib import Path
from .types import BenchmarkSummary, BenchmarkVerdict as V, DifficultyTier


class BenchmarkScorer:
    @staticmethod
    def classify_verdict(initial_violations, final_violations, execution_error=None,
                         *, pipeline_verdict=None, validation=None, changed=False,
                         marker_comparison=None):
        mapping = {"invalid_patch": V.INVALID_PATCH, "model_error": V.MODEL_ERROR,
                   "drc_error": V.CHECKER_ERROR, "timeout": V.EXECUTION_ERROR,
                   "blocked": V.BLOCKED, "oracle_mismatch": V.ORACLE_MISMATCH}
        if pipeline_verdict in mapping:
            return mapping[pipeline_verdict]
        if validation is not None and not validation.is_valid:
            return V.INVALID_PATCH
        if pipeline_verdict and validation is None:
            return V.CHECKER_ERROR
        if execution_error is not None:
            return V.EXECUTION_ERROR
        if initial_violations is None or final_violations is None:
            return V.CHECKER_ERROR
        if any(n > initial_violations.get(rule, 0) for rule, n in final_violations.items()):
            return V.REGRESSION
        if marker_comparison:
            if marker_comparison["introduced"]:
                return V.REGRESSION
            if marker_comparison["ambiguous"]:
                return V.AMBIGUOUS
        if not sum(initial_violations.values()):
            return V.UNNECESSARY_EDIT if changed else V.CLEAN_UNCHANGED
        if not sum(final_violations.values()):
            return V.CLEAN_SUCCESS
        if sum(final_violations.values()) < sum(initial_violations.values()):
            return V.PARTIAL_SUCCESS
        return V.FAILED_UNCHANGED

    @classmethod
    def aggregate(cls, benchmark_version, mode, results, total_runtime_s):
        counts = Counter(r.verdict.value for r in results)
        dirty = sum(not r.initially_clean for r in results)
        def breakdown(items):
            return {"total": len(items), **{v.value: sum(r.verdict == v for r in items) for v in V}}
        groups = {}
        for r in results:
            groups.setdefault(r.duplicate_group or r.case_id, []).append(r)
        return BenchmarkSummary(
            benchmark_version, mode, len(results), counts[V.CLEAN_SUCCESS.value],
            counts[V.PARTIAL_SUCCESS.value], counts[V.REGRESSION.value],
            counts[V.FAILED_UNCHANGED.value], counts[V.EXECUTION_ERROR.value],
            counts[V.CLEAN_SUCCESS.value] / dirty if dirty else 0., total_runtime_s,
            {t.value: breakdown([r for r in results if r.tier == t]) for t in DifficultyTier},
            {rule: breakdown([r for r in results if r.rule_id == rule]) for rule in sorted({r.rule_id for r in results})},
            results, dirty, len(results)-dirty, dict(counts),
            {g: {"case_ids": [r.case_id for r in rs], "verdicts": [r.verdict.value for r in rs],
                 "all_geometry_success": all(r.verdict in (V.CLEAN_SUCCESS, V.CLEAN_UNCHANGED) for r in rs)}
             for g, rs in groups.items()})

    @staticmethod
    def export_json(summary, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = output_path.with_suffix('.tmp')
        temp.write_text(json.dumps(summary.to_dict(), indent=2))
        temp.replace(output_path)

    @staticmethod
    def export_csv(summary, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fields = list(summary.results[0].to_dict()) if summary.results else ["case_id", "verdict"]
        with output_path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
            for r in summary.results:
                writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                 for k, v in r.to_dict().items()})

    @staticmethod
    def export_markdown(summary):
        lines = ['# Single-shot DRC development benchmark', '',
                 f'- Dataset: {summary.benchmark_version}; mode: {summary.mode}',
                 '- Validation: geometry_only; connectivity unverified.',
                 f'- Dirty entries: {summary.dirty_cases}; clean controls: {summary.clean_controls}.',
                 f'- Geometry repair success: {summary.clean_success_count}/{summary.dirty_cases} ({summary.clean_success_rate:.1%}).',
                 f'- Distinct layout groups: {len(summary.duplicate_groups)}.',
                 '- One attempt per entry. No held-out generalization or consistency claim.', '',
                 '| Outcome | Count |', '|---|---:|']
        lines += [f'| {v.value} | {summary.verdict_counts.get(v.value, 0)} |' for v in V]
        for name, breakdown in [('Tier', summary.tier_breakdown), ('Rule', summary.rule_breakdown)]:
            lines += ['', f'## {name} results', '', '| Group | Entries | Outcomes |', '|---|---:|---|']
            for key, stats in breakdown.items():
                outcomes = ', '.join(f'{k}: {n}' for k, n in stats.items() if k != 'total' and n)
                lines.append(f'| {key} | {stats["total"]} | {outcomes} |')
        return '\n'.join(lines) + '\n'
