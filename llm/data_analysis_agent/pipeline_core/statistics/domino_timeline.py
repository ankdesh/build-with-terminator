"""
Multi-metric changepoint detection (PELT) and lead-lag causality ordering (DominoTimeline).
Emits synchronized Apache ECharts sparklines with vertical T=0 reference line.
Zero backend plotting binary dependencies (air-gapped and lightweight).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Exception definitions: base fallback classes defined first for static typing
class DiagnosticEngineError(Exception):
    """Base fallback diagnostic exception when backend package is not available."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ChangepointDetectionError(DiagnosticEngineError):
    """Fallback changepoint detection exception."""
    pass


# Dynamic upgrade to backend domain exceptions at runtime if available (air-gapped AST safe)
try:
    _backend_exc = sys.modules.get("backend.exceptions") or importlib.import_module("backend.exceptions")
    DiagnosticEngineError = getattr(_backend_exc, "DiagnosticEngineError", DiagnosticEngineError)  # type: ignore[assignment,misc]
    ChangepointDetectionError = getattr(_backend_exc, "ChangepointDetectionError", ChangepointDetectionError)  # type: ignore[assignment,misc]
except Exception:
    pass



class DominoTimeline:
    """Multi-metric changepoint detector and cascade timeline analyzer."""

    def __init__(self, min_size: int = 2) -> None:
        self.min_size = min_size

    def detect_cascade(
        self,
        df: pd.DataFrame,
        time_col: str,
        metric_cols: List[str],
        penalty: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Detects changepoints across metrics, identifies root initiator, and orders cascade timeline.

        Args:
            df: Input pandas DataFrame.
            time_col: Time/timestamp column name.
            metric_cols: List of continuous numeric metric column names.
            penalty: Optional PELT penalty value. Defaults to 2 * ln(T) (BIC penalty).
            **kwargs: Keyword argument aliases.

        Returns:
            Dict containing t0_timestamp, root_cause_metric, cascade_order, and echarts_spec.
        """
        if not isinstance(df, pd.DataFrame):
            raise ChangepointDetectionError("Input df must be a pandas DataFrame.")
        if df.empty or len(df) < 10:
            raise ChangepointDetectionError("Timeline cascade analysis requires at least 10 observations.")
        if time_col not in df.columns:
            raise ChangepointDetectionError(f"Time column '{time_col}' not found in dataset.")
        if not metric_cols:
            raise ChangepointDetectionError("At least one metric column must be specified.")
        for col in metric_cols:
            if col not in df.columns:
                raise ChangepointDetectionError(f"Metric column '{col}' not found in dataset.")

        sorted_df = df.sort_values(by=time_col).reset_index(drop=True)
        timestamps = [str(t) for t in sorted_df[time_col]]
        n = len(sorted_df)

        bic_penalty = float(2.0 * np.log(n)) if penalty is None else float(penalty)

        metric_results: List[Dict[str, Any]] = []
        metric_data: Dict[str, List[float]] = {}

        for col in metric_cols:
            y_series = pd.to_numeric(sorted_df[col], errors="coerce").ffill().bfill()
            y = y_series.to_numpy(dtype=float)
            metric_data[col] = y.tolist()

            var = float(np.var(y))
            if var < 1e-12:
                # Constant metric with zero variance
                metric_results.append({
                    "metric": col,
                    "changepoints": [],
                    "first_cp_index": None,
                    "jump_magnitude": 0.0,
                    "is_constant": True,
                })
                continue

            # Standardize for scale-invariant PELT
            std = float(np.sqrt(var))
            z = (y - float(np.mean(y))) / std

            cps = self._pelt(z, penalty=bic_penalty, min_size=self.min_size)
            first_cp = cps[0] if cps else None

            jump_mag = 0.0
            if first_cp is not None and first_cp > 0:
                pre_mean = float(np.mean(z[:first_cp]))
                post_mean = float(np.mean(z[first_cp:min(n, first_cp + 5)]))
                jump_mag = abs(post_mean - pre_mean)

            metric_results.append({
                "metric": col,
                "changepoints": cps,
                "first_cp_index": first_cp,
                "jump_magnitude": jump_mag,
                "is_constant": False,
            })

        metrics_with_cp = [m for m in metric_results if m["first_cp_index"] is not None]
        if not metrics_with_cp:
            # Fallback if no metric had changepoints
            root_metric = metric_cols[0]
            t0_index = 0
            t0_timestamp = timestamps[0]
        else:
            # Earliest changepoint first; tie-break by jump magnitude descending, then metric name
            metrics_with_cp.sort(key=lambda m: (m["first_cp_index"], -m["jump_magnitude"], m["metric"]))
            root = metrics_with_cp[0]
            root_metric = root["metric"]
            t0_index = int(root["first_cp_index"])
            t0_timestamp = timestamps[t0_index]

        root_series = np.array(metric_data[root_metric], dtype=float)
        ordered_metrics: List[Dict[str, Any]] = []

        for m in metric_results:
            col = m["metric"]
            cp_idx = m["first_cp_index"]
            is_root = (col == root_metric)
            is_constant = m["is_constant"]

            if is_constant:
                lag_steps = None
                relative_delay = "No changepoint detected (constant)"
                max_corr = 0.0
                opt_lag = 0
            elif cp_idx is None:
                lag_steps = None
                relative_delay = "No changepoint detected"
                max_corr = 0.0
                opt_lag = 0
            elif is_root:
                lag_steps = 0
                relative_delay = "0 steps (Root Cause)"
                max_corr = 1.0
                opt_lag = 0
            else:
                lag_steps = int(cp_idx - t0_index)
                relative_delay = f"+{lag_steps} steps"
                opt_lag, max_corr = self._cross_correlation(root_series, np.array(metric_data[col], dtype=float))

            ordered_metrics.append({
                "metric": col,
                "changepoint_index": cp_idx,
                "changepoint_time": timestamps[cp_idx] if cp_idx is not None else None,
                "lag_steps": lag_steps,
                "relative_delay": relative_delay,
                "max_cross_corr": round(float(max_corr), 3),
                "optimal_lag": int(opt_lag),
                "is_root": is_root,
                "jump_magnitude": round(float(m["jump_magnitude"]), 3),
            })

        def sort_key(item: Dict[str, Any]) -> Tuple[int, int, float, str]:
            if item["is_root"]:
                return (0, 0, 0.0, item["metric"])
            if item["lag_steps"] is not None:
                return (1, item["lag_steps"], -item["jump_magnitude"], item["metric"])
            return (2, 999999, 0.0, item["metric"])

        ordered_metrics.sort(key=sort_key)

        echarts_option = self._build_echarts_spec(
            ordered_metrics=ordered_metrics,
            timestamps=timestamps,
            metric_data=metric_data,
            t0_timestamp=t0_timestamp,
            root_metric=root_metric,
        )

        echarts_spec = dict(echarts_option)
        echarts_spec["option"] = echarts_option

        return {
            "t0_timestamp": t0_timestamp,
            "root_timestamp": t0_timestamp,
            "root_cause_metric": root_metric,
            "cascade_order": ordered_metrics,
            "ordered_metrics": ordered_metrics,
            "echarts_spec": echarts_spec,
            "echarts_option": echarts_option,
            "total_metrics_analyzed": len(metric_cols),
            "metrics_with_changepoint": len(metrics_with_cp),
        }

    def _pelt(self, z: np.ndarray, penalty: float, min_size: int = 2) -> List[int]:
        """Pure NumPy PELT algorithm with L2 cost function and linear-time candidate pruning."""
        n = len(z)
        if n < 2 * min_size:
            return []

        y_cumsum = np.concatenate(([0.0], np.cumsum(z)))
        y2_cumsum = np.concatenate(([0.0], np.cumsum(z ** 2)))

        F = np.zeros(n + 1)
        F[0] = -penalty
        cp = np.zeros(n + 1, dtype=int)
        R: List[int] = [0]

        for t in range(min_size, n + 1):
            candidates = [s for s in R if t - s >= min_size]
            pending = [s for s in R if t - s < min_size]
            if not candidates:
                R = pending + [t]
                continue

            cand_arr = np.array(candidates, dtype=int)
            cnts = t - cand_arr
            sy = y_cumsum[t] - y_cumsum[cand_arr]
            sy2 = y2_cumsum[t] - y2_cumsum[cand_arr]
            costs = np.maximum(sy2 - (sy * sy) / cnts, 0.0)

            total_costs = F[cand_arr] + costs + penalty
            best_idx = int(np.argmin(total_costs))
            F[t] = total_costs[best_idx]
            cp[t] = cand_arr[best_idx]

            keep_mask = (total_costs - penalty) <= F[t]
            survivors = cand_arr[keep_mask].tolist()
            R = survivors + pending + [t]

        changepoints: List[int] = []
        curr = int(cp[n])
        while curr > 0:
            changepoints.append(curr)
            curr = int(cp[curr])
        changepoints.reverse()
        return changepoints

    def _cross_correlation(self, y_root: np.ndarray, y_m: np.ndarray, max_lag: int = 20) -> Tuple[int, float]:
        """Computes peak cross-correlation lag k >= 0 where y_m(t + k) correlates with y_root(t)."""
        zr = (y_root - np.mean(y_root)) / (np.std(y_root) + 1e-12)
        zm = (y_m - np.mean(y_m)) / (np.std(y_m) + 1e-12)
        n = len(zr)
        bound = min(max_lag, max(1, n // 3))

        best_lag = 0
        best_corr = float(np.mean(zr * zm))

        for k in range(1, bound + 1):
            corr = float(np.mean(zr[:n - k] * zm[k:]))
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = k

        return best_lag, best_corr

    def _build_echarts_spec(
        self,
        ordered_metrics: List[Dict[str, Any]],
        timestamps: List[str],
        metric_data: Dict[str, List[float]],
        t0_timestamp: str,
        root_metric: str,
    ) -> Dict[str, Any]:
        """Constructs Apache ECharts option tree with synchronized vertical sparklines and T=0 reference line."""
        m_count = len(ordered_metrics)
        if m_count == 0:
            return {"title": {"text": "Domino Timeline"}, "series": []}

        top_margin = 15.0
        bottom_margin = 8.0
        available_height = 100.0 - top_margin - bottom_margin
        gap = 3.5 if m_count > 1 else 0.0
        row_height = (available_height - (m_count - 1) * gap) / m_count

        colors = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981", "#64748b"]

        grids = []
        x_axes = []
        y_axes = []
        series = []

        for idx, item in enumerate(ordered_metrics):
            col_name = item["metric"]
            is_root = item.get("is_root", False)
            color = "#ef4444" if is_root else colors[idx % len(colors)]
            row_top = top_margin + idx * (row_height + gap)

            grids.append({
                "left": "20%",
                "right": "8%",
                "top": f"{row_top:.1f}%",
                "height": f"{row_height:.1f}%",
                "containLabel": False,
            })

            is_last = (idx == m_count - 1)
            x_axes.append({
                "type": "category",
                "gridIndex": idx,
                "data": timestamps,
                "show": is_last,
                "axisLabel": {"color": "#64748b", "fontSize": 10} if is_last else {},
                "axisLine": {"lineStyle": {"color": "#cbd5e1"}} if is_last else {"show": False},
                "axisTick": {"show": is_last},
            })

            y_axes.append({
                "type": "value",
                "gridIndex": idx,
                "name": f"{col_name} ({item.get('relative_delay', '')})",
                "nameLocation": "left",
                "nameTextStyle": {"color": color, "fontSize": 10, "fontWeight": "bold"},
                "splitLine": {"show": False},
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": {"fontSize": 9, "color": "#94a3b8"},
            })

            s_entry: Dict[str, Any] = {
                "name": col_name,
                "type": "line",
                "xAxisIndex": idx,
                "yAxisIndex": idx,
                "data": [round(float(v), 3) if v is not None else None for v in metric_data[col_name]],
                "itemStyle": {"color": color},
                "lineStyle": {"width": 2.5 if is_root else 1.8, "color": color},
                "showSymbol": False,
                "markLine": {
                    "symbol": "none",
                    "lineStyle": {"type": "dashed", "color": "#ef4444", "width": 2 if is_root else 1.5},
                    "data": [
                        {
                            "xAxis": str(t0_timestamp),
                            "label": {
                                "show": is_root,
                                "formatter": "⚠️ T=0 Incident Start",
                                "position": "end",
                                "color": "#ef4444",
                                "fontSize": 10,
                            },
                        }
                    ],
                },
            }

            cp_time = item.get("changepoint_time")
            if cp_time and cp_time in timestamps:
                t_idx = timestamps.index(cp_time)
                y_val = metric_data[col_name][t_idx]
                s_entry["markPoint"] = {
                    "symbol": "pin",
                    "symbolSize": 36 if is_root else 28,
                    "itemStyle": {"color": color},
                    "data": [
                        {
                            "coord": [str(cp_time), round(float(y_val), 3)],
                            "value": "T=0 Root" if is_root else item.get("relative_delay", "Break"),
                            "label": {"color": "#ffffff", "fontSize": 8},
                        }
                    ],
                }

            series.append(s_entry)

        title_text = f"Root Cause: {root_metric} broke first at {t0_timestamp}" if root_metric else "Multi-Metric Timeline"
        subtext = f"Cascade timeline across {m_count} metrics • Ordered by lead-lag delay from T=0"

        return {
            "title": {
                "text": title_text,
                "subtext": subtext,
                "left": "left",
                "textStyle": {"fontSize": 14, "fontWeight": 600, "color": "#0f172a"},
                "subtextStyle": {"fontSize": 11, "color": "#64748b"},
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {
                    "type": "cross",
                    "lineStyle": {"color": "#94a3b8", "type": "dashed"},
                    "link": [{"xAxisIndex": "all"}],
                },
            },
            "axisPointer": {"link": [{"xAxisIndex": "all"}]},
            "grid": grids,
            "xAxis": x_axes,
            "yAxis": y_axes,
            "series": series,
        }
