"""
Subgroup slice isolation engine using multi-predicate beam search and Welch's t-test.
Produces Apache ECharts option trees adhering strictly to the 3-Layer Visual Hierarchy rule.
Zero runtime plotting binary dependencies (air-gapped and lightweight).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import scipy.stats as stats

# Exception definitions: base fallback classes defined first for static typing
class DiagnosticEngineError(Exception):
    """Base fallback diagnostic exception when backend package is not available."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class SubgroupSliceError(DiagnosticEngineError):
    """Fallback slice exception."""
    pass


# Dynamic upgrade to backend domain exceptions at runtime if available (air-gapped AST safe)
try:
    _backend_exc = sys.modules.get("backend.exceptions") or importlib.import_module("backend.exceptions")
    DiagnosticEngineError = getattr(_backend_exc, "DiagnosticEngineError", DiagnosticEngineError)  # type: ignore[assignment,misc]
    SubgroupSliceError = getattr(_backend_exc, "SubgroupSliceError", SubgroupSliceError)  # type: ignore[assignment,misc]
except Exception:
    pass



def _welch_t_test(y_s: np.ndarray, y_rest: np.ndarray) -> Tuple[float, float, float]:
    """Calculates Welch's two-sample t-statistic, two-tailed p-value, and degrees of freedom."""
    n_s, n_rest = len(y_s), len(y_rest)
    if n_s < 2 or n_rest < 2:
        return 0.0, 1.0, 1.0

    mean_s, mean_rest = float(np.mean(y_s)), float(np.mean(y_rest))
    var_s = float(np.var(y_s, ddof=1))
    var_rest = float(np.var(y_rest, ddof=1))

    se2_s = var_s / n_s
    se2_rest = var_rest / n_rest
    se_total = np.sqrt(se2_s + se2_rest)

    if se_total < 1e-12:
        if abs(mean_s - mean_rest) < 1e-12:
            return 0.0, 1.0, float(n_s + n_rest - 2)
        t_val = float("inf") if mean_s > mean_rest else float("-inf")
        return t_val, 0.0, float(n_s + n_rest - 2)

    t_stat = (mean_s - mean_rest) / se_total

    denom = (se2_s**2 / max(1, n_s - 1)) + (se2_rest**2 / max(1, n_rest - 1))
    if denom < 1e-15:
        df = float(n_s + n_rest - 2)
    else:
        df = float(((se2_s + se2_rest) ** 2) / denom)

    p_val = float(2.0 * stats.t.sf(np.abs(t_stat), df=df))
    return float(t_stat), p_val, df


class AnomalySpotlight:
    """Isolates dataset subgroups contributing disproportionately to metric degradation."""

    def isolate_slices(
        self,
        df: pd.DataFrame,
        metric_col: str,
        baseline_val: Optional[float] = None,
        dimension_columns: Optional[List[str]] = None,
        max_depth: int = 2,
        beam_width: int = 5,
        min_support: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Isolates anomalous subgroups contributing disproportionately to metric degradation.

        Args:
            df: Input pandas DataFrame.
            metric_col: Continuous numeric column to evaluate.
            baseline_val: Reference baseline value. Defaults to complement/dataset mean.
            dimension_columns: Optional list of candidate categorical/discrete columns.
            max_depth: Maximum predicate conjunction depth (1 or 2, default 2).
            beam_width: Number of beam candidate seeds to retain (default 5).
            min_support: Minimum row count required for a slice to be valid.
            **kwargs: Keyword argument aliases (e.g. metric_column, dimension_cols).

        Returns:
            Dictionary containing culprits, echarts_spec, confidence_badge, and summary.
        """
        metric = kwargs.get("metric_column", metric_col)
        dimensions = kwargs.get("dimension_cols", dimension_columns)

        if not isinstance(df, pd.DataFrame):
            raise SubgroupSliceError("Input df must be a pandas DataFrame.")
        if metric not in df.columns:
            raise SubgroupSliceError(f"Metric column '{metric}' not found in DataFrame.")

        numeric_series = pd.to_numeric(df[metric], errors="coerce")
        clean_mask = numeric_series.notna()
        clean_df = df[clean_mask].copy()

        if len(clean_df) < 5:
            # Handle boundary small dataset safely
            return self._empty_result(clean_df, metric, baseline_val or 0.0)

        y_total = numeric_series[clean_mask].to_numpy(dtype=float)
        total_var = float(np.var(y_total))
        total_mean = float(np.mean(y_total))
        base_val = float(baseline_val) if baseline_val is not None else total_mean

        if total_var < 1e-12:
            # Zero variance flatline across entire dataset
            return self._empty_result(clean_df, metric, base_val)

        n_rows = len(clean_df)
        min_supp = min_support if min_support is not None else max(5, int(0.01 * n_rows))
        min_supp = max(2, min_supp)

        # Dimension feature discovery and discretization
        candidates_dict: Dict[str, pd.Series] = {}
        target_cols = dimensions if dimensions else [c for c in clean_df.columns if c != metric]

        for col in target_cols:
            if col == metric or col not in clean_df.columns:
                continue
            series = clean_df[col]
            n_unique = series.nunique()
            if n_unique < 2:
                continue

            col_lower = col.lower()
            if (
                "uuid" in col_lower
                or col_lower in ("id", "uid")
                or col_lower.endswith("_id")
                or col_lower.startswith("id_")
                or (n_unique > 50 and (n_unique / n_rows) > 0.5)
                or n_unique > 100
            ):
                continue

            if (
                pd.api.types.is_string_dtype(series)
                or pd.api.types.is_object_dtype(series)
                or isinstance(series.dtype, pd.CategoricalDtype)
                or series.dtype == "bool"
            ):
                if n_unique <= 50:
                    candidates_dict[col] = series.astype(str)
            elif pd.api.types.is_numeric_dtype(series):
                if 2 <= n_unique <= 10:
                    candidates_dict[col] = series.astype(str)
                elif n_unique > 10:
                    try:
                        binned = pd.qcut(series, q=3, labels=["Low", "Medium", "High"], duplicates="drop")
                        if binned.nunique() >= 2:
                            candidates_dict[col] = binned.astype(str)
                    except Exception:
                        pass

        if not candidates_dict:
            return self._empty_result(clean_df, metric, base_val)

        has_baseline = baseline_val is not None
        is_overall_spike = bool(total_mean > base_val) if has_baseline else False

        def evaluate_slice(predicates: Tuple[Tuple[str, str], ...]) -> Optional[Dict[str, Any]]:
            mask = np.ones(n_rows, dtype=bool)
            for c, v in predicates:
                mask &= (candidates_dict[c] == v).to_numpy()

            n_s = int(np.sum(mask))
            n_rest = n_rows - n_s
            if n_s < min_supp or n_rest < 2:
                return None

            y_s = y_total[mask]
            y_rest = y_total[~mask]
            mean_s = float(np.mean(y_s))
            mean_rest = float(np.mean(y_rest))
            is_slice_drop = bool(mean_s < mean_rest)

            if has_baseline:
                slice_baseline = base_val
                delta_s = (base_val - mean_s) * n_s
                if is_overall_spike:
                    impact_s = (mean_s - base_val) * n_s
                    impact_total = (total_mean - base_val) * n_rows
                else:
                    impact_s = (base_val - mean_s) * n_s
                    impact_total = (base_val - total_mean) * n_rows

                if impact_total > 1e-9:
                    pct_drop = min(100.0, max(0.0, (impact_s / impact_total) * 100.0))
                else:
                    ss_between = (n_s * n_rest / n_rows) * ((mean_s - mean_rest) ** 2)
                    ss_total = n_rows * total_var
                    pct_drop = min(100.0, max(0.0, (ss_between / ss_total) * 100.0)) if ss_total > 1e-12 else 0.0
            else:
                # baseline_val is None: compare slice divergence relative to rest_mean and total variance
                slice_baseline = mean_rest
                delta_s = (mean_rest - mean_s) * n_s
                impact_s = max(0.0, delta_s)
                ss_between = (n_s * n_rest / n_rows) * ((mean_s - mean_rest) ** 2)
                ss_total = n_rows * total_var
                pct_drop = min(100.0, max(0.0, (ss_between / ss_total) * 100.0)) if ss_total > 1e-12 else 0.0

            ratio = (mean_s / mean_rest) if abs(mean_rest) > 1e-9 else 0.0
            t_stat, p_val, _ = _welch_t_test(y_s, y_rest)

            score = max(0.0, impact_s) * (1.0 - (n_s / n_rows))
            if score <= 0.0:
                score = abs(mean_s - mean_rest) * np.sqrt(n_s) * (1.0 - (n_s / n_rows))

            pred_dict = dict(predicates)
            pred_label = " AND ".join(f"{c} = '{v}'" for c, v in predicates)

            return {
                "predicates": pred_dict,
                "predicate_label": pred_label,
                "slice_mean": mean_s,
                "rest_mean": mean_rest,
                "baseline_val": slice_baseline,
                "ratio_vs_normal": ratio,
                "drop_contribution": delta_s,
                "pct_drop_explained": pct_drop,
                "drop_contribution_pct": pct_drop,
                "t_statistic": t_stat,
                "p_value": p_val,
                "sample_size": n_s,
                "rest_sample_size": n_rest,
                "score": score,
                "is_drop": is_slice_drop,
            }

        # Beam Search Level 1: Single Predicates
        depth_1_candidates: List[Dict[str, Any]] = []
        for col, col_series in candidates_dict.items():
            for val in col_series.unique():
                res = evaluate_slice(((col, str(val)),))
                if res is not None:
                    depth_1_candidates.append(res)

        if not depth_1_candidates:
            return self._empty_result(clean_df, metric, base_val)

        depth_1_candidates.sort(key=lambda x: x["score"], reverse=True)
        current_beam = depth_1_candidates[:beam_width]
        all_culprits = list(depth_1_candidates)

        # Beam Search Level 2: Conjunctions
        if max_depth >= 2:
            depth_2_candidates: List[Dict[str, Any]] = []
            for seed in current_beam:
                seed_cols = set(seed["predicates"].keys())
                for col, col_series in candidates_dict.items():
                    if col in seed_cols:
                        continue
                    for val in col_series.unique():
                        new_preds = tuple(sorted(list(seed["predicates"].items()) + [(col, str(val))]))
                        res = evaluate_slice(new_preds)
                        if res and res["score"] > seed["score"] * 1.05:
                            depth_2_candidates.append(res)
            all_culprits.extend(depth_2_candidates)

        # Rank and deduplicate
        seen_preds = set()
        deduped: List[Dict[str, Any]] = []
        for item in sorted(all_culprits, key=lambda x: (x["score"], abs(x["drop_contribution"])), reverse=True):

            p_key = frozenset(item["predicates"].items())
            if p_key not in seen_preds:
                seen_preds.add(p_key)
                p_val, n_s = item["p_value"], item["sample_size"]
                if p_val < 0.01 and n_s >= 30:
                    badge = {
                        "level": "high",
                        "icon": "🟢",
                        "badge": "🟢 High Confidence Finding",
                        "title": "High Confidence Finding",
                        "subtitle": f"Based on {n_s} observations — statistically reliable.",
                    }
                elif p_val < 0.05 and n_s >= 15:
                    badge = {
                        "level": "moderate",
                        "icon": "🟢",
                        "badge": "🟢 Moderate Confidence Finding",
                        "title": "Moderate Confidence Finding",
                        "subtitle": f"Based on {n_s} observations (p < 0.05).",
                    }
                else:
                    badge = {
                        "level": "warning",
                        "icon": "🟡",
                        "badge": "🟡 Low Sample Warning",
                        "title": "Low Sample Warning",
                        "subtitle": f"Only {n_s} observations in this group — treat with caution.",
                    }
                item["confidence_badge"] = badge
                deduped.append(item)

        if not deduped:
            return self._empty_result(clean_df, metric, base_val)

        top_culprit = deduped[0]
        chart_baseline = float(baseline_val) if baseline_val is not None else float(top_culprit["rest_mean"])
        echarts_option = self._build_echarts_option(metric, top_culprit, chart_baseline)

        summary = (
            f"Isolated {len(deduped)} anomalous slice(s). Top culprit: {top_culprit['predicate_label']} "
            f"({top_culprit['sample_size']} rows) with {metric}={top_culprit['slice_mean']:.2f} "
            f"vs normal {top_culprit['rest_mean']:.2f} ({top_culprit['pct_drop_explained']:.1f}% drop explained)."
        )

        echarts_spec = dict(echarts_option)
        echarts_spec["option"] = echarts_option

        return {
            "culprits": deduped[:10],
            "culprit_predicate": top_culprit,
            "echarts_spec": echarts_spec,
            "echarts_option": echarts_option,
            "confidence_badge": top_culprit["confidence_badge"],
            "summary": summary,
        }

    def _build_echarts_option(
        self,
        metric_col: str,
        top_culprit: Dict[str, Any],
        baseline_val: float,
    ) -> Dict[str, Any]:
        """Constructs Apache ECharts option tree obeying the 3-Layer Visual Hierarchy rule."""
        slice_label = top_culprit["predicate_label"]
        slice_mean = round(top_culprit["slice_mean"], 2)
        rest_mean = round(top_culprit["rest_mean"], 2)
        base_val = round(baseline_val, 2)
        badge = top_culprit["confidence_badge"]
        n_records = top_culprit["sample_size"]

        raw_slice_mean = top_culprit["slice_mean"]
        raw_rest_mean = top_culprit["rest_mean"]

        # Directional sign checking: compare slice_mean vs rest_mean directly, fallback to baseline_val if equal
        if abs(raw_slice_mean - raw_rest_mean) > 1e-6:
            is_drop = bool(raw_slice_mean < raw_rest_mean)
            ref_mean = raw_rest_mean
        else:
            is_drop = bool(raw_slice_mean < baseline_val)
            ref_mean = baseline_val

        if is_drop:
            delta = ref_mean - raw_slice_mean
            if abs(ref_mean) > 1e-9:
                drop_pct = round((delta / abs(ref_mean)) * 100)
                headline = f"{slice_label} {metric_col} Dropped {drop_pct}% Below Normal"
            else:
                headline = f"{slice_label} {metric_col} Dropped {abs(delta):.2f} Below Normal"
        else:
            delta = raw_slice_mean - ref_mean
            if abs(ref_mean) > 1e-9:
                if ref_mean > 0 and raw_slice_mean >= 0:
                    mult = raw_slice_mean / ref_mean
                else:
                    mult = 1.0 + (delta / abs(ref_mean))
                headline = f"{slice_label} {metric_col} Spiked {mult:.1f}x Above Normal"
            else:
                headline = f"{slice_label} {metric_col} Spiked +{delta:.2f} Above Normal"

        subtitle = f"Comparison against baseline • {badge['icon']} {badge['title']} ({n_records:,} records)"

        return {
            "title": {
                "text": headline,
                "subtext": subtitle,
                "left": "left",
                "textStyle": {"fontSize": 14, "fontWeight": 600, "color": "#0f172a"},
                "subtextStyle": {"fontSize": 11, "color": "#64748b"},
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "formatter": (
                    f"{{b}}<br/>{metric_col}: <b>{{c}}</b><br/>Baseline: {base_val}"
                ),
            },
            "grid": {"left": "3%", "right": "8%", "bottom": "6%", "top": "20%", "containLabel": True},
            "xAxis": {
                "type": "value",
                "name": metric_col,
                "splitLine": {"lineStyle": {"type": "dashed", "color": "#e2e8f0"}},
            },
            "yAxis": {
                "type": "category",
                "data": ["Rest of Business", slice_label],
                "axisLabel": {"fontWeight": 500, "color": "#334155"},
            },
            "series": [
                {
                    "name": metric_col,
                    "type": "bar",
                    "barWidth": "38%",
                    "data": [
                        {"value": rest_mean, "itemStyle": {"color": "#94a3b8", "borderRadius": [0, 4, 4, 0]}},
                        {"value": slice_mean, "itemStyle": {"color": "#ef4444", "borderRadius": [0, 4, 4, 0]}},
                    ],
                    "markLine": {
                        "silent": True,
                        "lineStyle": {"type": "dashed", "color": "#64748b", "width": 2},
                        "data": [
                            {
                                "xAxis": base_val,
                                "label": {
                                    "formatter": f"Baseline: {base_val}",
                                    "position": "end",
                                    "color": "#64748b",
                                    "fontSize": 11,
                                },
                            }
                        ],
                    },
                }
            ],
        }

    def _empty_result(self, df: pd.DataFrame, metric_col: str, baseline_val: float) -> Dict[str, Any]:
        """Fallback neutral result when no significant subgroup or variance exists."""
        base_val = round(baseline_val, 2)
        mean_val = round(float(df[metric_col].mean()), 2) if not df.empty and metric_col in df.columns else base_val
        option = {
            "title": {
                "text": f"{metric_col}: No Anomalous Subgroup Identified",
                "subtext": f"Metric distribution is uniform across dimensions • Baseline: {base_val}",
                "left": "left",
            },
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "3%", "right": "8%", "bottom": "6%", "top": "20%", "containLabel": True},
            "xAxis": {"type": "value", "name": metric_col},
            "yAxis": {"type": "category", "data": ["All Data"]},
            "series": [
                {
                    "name": metric_col,
                    "type": "bar",
                    "data": [{"value": mean_val, "itemStyle": {"color": "#94a3b8"}}],
                    "markLine": {
                        "data": [{"xAxis": base_val, "label": {"formatter": f"Baseline: {base_val}"}}]
                    },
                }
            ],
        }
        spec = dict(option)
        spec["option"] = option
        badge = {
            "level": "moderate",
            "icon": "🟢",
            "badge": "🟢 Baseline Normal",
            "title": "Baseline Normal",
            "subtitle": "No anomalous subgroup divergence detected.",
        }
        return {
            "culprits": [],
            "culprit_predicate": None,
            "echarts_spec": spec,
            "echarts_option": option,
            "confidence_badge": badge,
            "summary": "No anomalous subgroup identified across tested dimensions.",
        }
