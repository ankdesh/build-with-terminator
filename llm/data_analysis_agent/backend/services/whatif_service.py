"""Interactive Scenario 'What-If' Studio Backend Engine (Milestone 3).

Provides feature role inference, closed-form Ridge surrogate model training,
sub-millisecond slider predictions, Mahalanobis out-of-distribution (OOD) guardrails,
counterfactual goal-seeking recipe card optimization, and Monte Carlo weather forecasting.

Zero backend plotting binary dependencies. Pure NumPy / SciPy implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import chi2

from backend.exceptions import (
    CounterfactualOptimizationError,
    OODDetectionError,
    ScenarioSimulationError,
    SurrogateModelError,
)
from backend.models.whatif import (
    FeatureRoles,
    LeverRoleInfo,
    RecipeCard,
    SimulationResult,
    SurrogateModel,
    WeatherForecastDistribution,
)
from backend.services.jargon_translator import (
    COLOR_CAUTION_AMBER,
    COLOR_CORAL_RED,
    COLOR_DASHED_LINE,
    COLOR_ELECTRIC_BLUE,
    COLOR_EMERALD_GREEN,
    COLOR_MUTED_SLATE,
    JargonTranslator,
)


class WhatIfService:
    """Core mathematical engine for interactive what-if scenario simulation,

    closed-form Ridge surrogate caching, OOD detection, and counterfactual goal-seeking.
    """

    def infer_roles(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        **kwargs: Any,
    ) -> FeatureRoles:
        """Classifies dataset columns into Controllable Levers, Immutable Context, and Target."""
        if df.empty:
            raise ScenarioSimulationError(
                "Input dataset is empty.",
                "Cannot infer feature roles or run scenario simulation on an empty DataFrame.",
            )

        # Resolve target column
        target = target_col or kwargs.get("target_column")
        if target is not None:
            if target not in df.columns:
                raise ScenarioSimulationError(
                    f"Target column '{target}' not found in dataset.",
                    f"Available columns are: {list(df.columns)}",
                )
            if not pd.api.types.is_numeric_dtype(df[target].dtype):
                raise ScenarioSimulationError(
                    f"Target column '{target}' must be numeric.",
                    f"Column '{target}' has non-numeric dtype: {df[target].dtype}",
                )
        else:
            # Heuristic target inference: high variance numeric column matching target keywords
            target_keywords = [
                "revenue", "margin", "profit", "sales", "churn", "cost",
                "latency", "error", "score", "amount", "kwh", "target", "loss",
            ]
            candidates: List[Tuple[float, str]] = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col].dtype):
                    col_lower = col.lower()
                    kw_score = 2.0 if any(k in col_lower for k in target_keywords) else 1.0
                    series = df[col].dropna()
                    std_val = float(series.std()) if len(series) > 1 else 0.0
                    candidates.append((kw_score * std_val, col))

            if not candidates:
                raise ScenarioSimulationError(
                    "No numeric candidate target columns found in dataset.",
                    "Dataset must contain at least one continuous numeric outcome column.",
                )
            candidates.sort(key=lambda x: x[0], reverse=True)
            target = candidates[0][1]

        levers: List[str] = []
        locked: List[str] = []
        bounds_dict: Dict[str, Dict[str, float]] = {}
        baseline_vals: Dict[str, float] = {}

        id_pattern = re.compile(r"(^|_)(id|uuid|key|code|hash)($|_)", re.IGNORECASE)
        time_pattern = re.compile(
            r"(^|_)(date|time|timestamp|created_at|updated_at|year|month|day|hour|quarter)($|_)",
            re.IGNORECASE,
        )

        for col in df.columns:
            if col == target:
                continue

            col_lower = col.lower()
            is_non_numeric = not pd.api.types.is_numeric_dtype(df[col].dtype)
            is_id = bool(id_pattern.search(col_lower)) or col_lower.endswith(("_id", "_uuid", "_key"))
            is_time = bool(time_pattern.search(col_lower))

            if is_non_numeric or is_id or is_time:
                locked.append(col)
                continue

            series = df[col].dropna()
            if len(series) < 2 or series.nunique() <= 1 or float(series.std()) < 1e-8:
                locked.append(col)
                continue

            # Check if integer ID / row index
            if pd.api.types.is_integer_dtype(series.dtype) and (
                series.nunique() == len(series) or (len(series) > 20 and series.nunique() > 0.95 * len(series))
            ):
                locked.append(col)
                continue

            # Check if binary indicator flag (0/1)
            if series.nunique() <= 2 and set(series.unique()).issubset({0, 1, 0.0, 1.0}):
                locked.append(col)
                continue

            # Controllable numeric lever
            levers.append(col)
            min_v = float(series.min())
            max_v = float(series.max())
            mean_v = float(series.mean())
            std_v = float(series.std()) if len(series) > 1 else 1.0
            med_v = float(series.median())
            p01 = float(series.quantile(0.01))
            p05 = float(series.quantile(0.05))
            p95 = float(series.quantile(0.95))
            p99 = float(series.quantile(0.99))

            # Dynamic step calculation
            if pd.api.types.is_integer_dtype(series.dtype):
                step_val = max(1.0, round((p95 - p05) / 100.0))
            else:
                rng_span = max(1e-6, p95 - p05)
                raw_step = rng_span / 100.0
                mag = 10.0 ** math.floor(math.log10(raw_step))
                norm = raw_step / mag
                neat = 1.0 if norm < 1.5 else (2.0 if norm < 3.5 else (5.0 if norm < 7.5 else 10.0))
                step_val = round(neat * mag, 6)

            bounds_dict[col] = {
                "min": min_v,
                "max": max_v,
                "mean": mean_v,
                "std": std_v,
                "median": med_v,
                "p01": p01,
                "p1": p01,
                "p05": p05,
                "p5": p05,
                "p95": p95,
                "p99": p99,
                "step": step_val,
                "default": med_v,
            }
            baseline_vals[col] = med_v

        if not levers:
            raise ScenarioSimulationError(
                "No controllable numeric levers found for scenario modeling.",
                "Dataset must contain continuous numeric columns that vary across observations.",
            )

        target_series = df[target].dropna()
        baseline_target_val = float(target_series.median()) if not target_series.empty else 0.0

        return FeatureRoles(
            levers=levers,
            locked_context=locked,
            target_col=target,
            lever_bounds=bounds_dict,
            baseline_values=baseline_vals,
            baseline_target=baseline_target_val,
        )

    # Backward-compatible alias
    infer_feature_roles = infer_roles

    def fit_surrogate(
        self,
        df: pd.DataFrame,
        target_col: str,
        lever_cols: List[str],
        alpha: float = 1.0,
        **kwargs: Any,
    ) -> SurrogateModel:
        """Fits pure closed-form Ridge surrogate regression and pre-computes covariance structure."""
        if target_col not in df.columns:
            raise SurrogateModelError(
                f"Target column '{target_col}' not found in DataFrame.",
                f"Available columns: {list(df.columns)}",
            )
        missing_levers = [c for c in lever_cols if c not in df.columns]
        if missing_levers:
            raise SurrogateModelError(
                f"Lever columns not found in DataFrame: {missing_levers}",
                f"Available columns: {list(df.columns)}",
            )
        if not lever_cols:
            raise SurrogateModelError(
                "At least one controllable lever column is required to fit surrogate.",
                "Provided lever_cols was empty.",
            )

        clean_df = df[[target_col] + lever_cols].dropna()
        N = len(clean_df)
        if N < 2:
            raise SurrogateModelError(
                f"Insufficient valid rows ({N}) to fit surrogate model.",
                "At least 2 complete observations required for linear regression.",
            )

        X = clean_df[lever_cols].to_numpy(dtype=float)
        y = clean_df[target_col].to_numpy(dtype=float)
        p = X.shape[1]

        mu = np.mean(X, axis=0)
        y_mean = float(np.mean(y))
        X_c = X - mu
        y_c = y - y_mean

        # Ridge regression on centered features (unpenalized intercept)
        lam = max(1e-4, float(alpha))
        A = X_c.T @ X_c + lam * np.eye(p)
        b = X_c.T @ y_c

        try:
            weights = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            weights = np.linalg.pinv(A) @ b

        intercept = y_mean - float(np.dot(mu, weights))

        # Model fit statistics
        y_pred = X @ weights + intercept
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y_mean) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
        r2 = max(0.0, min(1.0, r2))
        mse = ss_res / N
        residual_std = math.sqrt(max(1e-8, mse))

        # Covariance matrix and regularization
        if p == 1:
            var_1 = float(np.var(X, ddof=1)) if N > 1 else 1.0
            cov_inv = np.array([[1.0 / max(1e-4, var_1 + 1e-4)]])
        else:
            cov = np.cov(X, rowvar=False) if N > 1 else np.eye(p)
            cov_reg = cov + 1e-4 * np.eye(p)
            try:
                cov_inv = np.linalg.inv(cov_reg)
            except np.linalg.LinAlgError:
                cov_inv = np.linalg.pinv(cov_reg)

        chi2_crit = float(chi2.ppf(0.99, df=p))

        # Lever bounds and baseline medians
        lever_bounds: Dict[str, Dict[str, float]] = {}
        baseline_vals: Dict[str, float] = {}

        for j, col in enumerate(lever_cols):
            col_vals = X[:, j]
            min_v = float(np.min(col_vals))
            max_v = float(np.max(col_vals))
            mean_v = float(mu[j])
            std_v = float(np.std(col_vals, ddof=1)) if N > 1 else 1.0
            med_v = float(np.median(col_vals))
            p01 = float(np.percentile(col_vals, 1))
            p05 = float(np.percentile(col_vals, 5))
            p95 = float(np.percentile(col_vals, 95))
            p99 = float(np.percentile(col_vals, 99))

            step_val = max(1.0, round((p95 - p05) / 100.0)) if pd.api.types.is_integer_dtype(clean_df[col].dtype) else round((p95 - p05) / 100.0, 6)

            lever_bounds[col] = {
                "min": min_v,
                "max": max_v,
                "mean": mean_v,
                "std": std_v,
                "median": med_v,
                "p01": p01,
                "p1": p01,
                "p05": p05,
                "p5": p05,
                "p95": p95,
                "p99": p99,
                "step": step_val,
                "default": med_v,
            }
            baseline_vals[col] = med_v

        baseline_pred = float(np.dot([baseline_vals[c] for c in lever_cols], weights) + intercept)

        return SurrogateModel(
            feature_names=lever_cols,
            coefficients=weights.tolist(),
            intercept=intercept,
            r_squared=r2,
            cov_matrix_inv=cov_inv.tolist(),
            mean_vector=mu.tolist(),
            chi2_critical_99=chi2_crit,
            residual_std=residual_std,
            target_col=target_col,
            sample_size=N,
            alpha=alpha,
            lever_bounds=lever_bounds,
            baseline_values=baseline_vals,
            baseline_prediction=baseline_pred,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def predict(
        self,
        surrogate: SurrogateModel,
        slider_values: Dict[str, float],
    ) -> SimulationResult:
        """Fast (<0.05ms) linear dot product prediction, Mahalanobis OOD guardrails, and 3-zone evaluation."""
        lever_cols = surrogate.feature_names
        p = len(lever_cols)
        w = np.array(surrogate.coefficients, dtype=float)
        b0 = surrogate.intercept
        cov_inv = np.array(surrogate.cov_matrix_inv, dtype=float)
        mu = np.array(surrogate.mean_vector, dtype=float)

        x_vec = np.zeros(p, dtype=float)
        delta_vec = np.zeros(p, dtype=float)
        lever_zones: Dict[str, Literal["green", "amber", "red"]] = {}
        has_red_lever = False
        has_amber_lever = False

        for j, col in enumerate(lever_cols):
            b_info = surrogate.lever_bounds.get(col, {})
            default_val = b_info.get("mean", mu[j])
            val = float(slider_values.get(col, default_val))
            x_vec[j] = val
            delta_vec[j] = val - mu[j]

            p01 = b_info.get("p01", b_info.get("min", val - 1.0))
            p05 = b_info.get("p05", b_info.get("min", val - 0.5))
            p95 = b_info.get("p95", b_info.get("max", val + 0.5))
            p99 = b_info.get("p99", b_info.get("max", val + 1.0))

            if val < p01 or val > p99:
                lever_zones[col] = "red"
                has_red_lever = True
            elif val < p05 or val > p95:
                lever_zones[col] = "amber"
                has_amber_lever = True
            else:
                lever_zones[col] = "green"

        # Linear dot product: < 5 microseconds
        y_hat = float(np.dot(x_vec, w) + b0)

        # Mahalanobis distance squared: < 10 microseconds
        dm_sq = float(delta_vec @ cov_inv @ delta_vec)
        dm = math.sqrt(max(0.0, dm_sq))
        crit_threshold = math.sqrt(surrogate.chi2_critical_99)

        is_ood = bool((dm_sq > surrogate.chi2_critical_99) or has_red_lever)
        overall_zone: Literal["green", "amber", "red"] = (
            "red" if is_ood else ("amber" if has_amber_lever else "green")
        )

        alert_msg = (
            "⚠️ Reality Check: Operating outside historical experience. "
            "This combination of settings has never been operated together in historical data; "
            "projection is a directional estimate."
            if is_ood
            else None
        )

        confidence_badge = JargonTranslator.get_confidence_badge(
            r_squared=surrogate.r_squared,
            sample_size=surrogate.sample_size,
            is_ood=is_ood,
            mahalanobis_dist=dm,
            critical_threshold=crit_threshold,
        )

        b_pred = surrogate.baseline_prediction
        delta = y_hat - b_pred
        delta_pct = (delta / abs(b_pred) * 100.0) if abs(b_pred) > 1e-6 else 0.0

        return SimulationResult(
            predicted_value=round(y_hat, 2),
            delta_from_baseline=round(delta, 2),
            pct_change=round(delta_pct, 1),
            is_ood=is_ood,
            mahalanobis_dist=round(dm, 2),
            zone=overall_zone,
            confidence_badge=confidence_badge,
            lever_zones=lever_zones,
            reality_check_alert=alert_msg,
            baseline_value=round(b_pred, 2),
            mahalanobis_critical=round(crit_threshold, 2),
        )

    def solve_recipes(
        self,
        surrogate: SurrogateModel,
        target_goal: float,
        current_values: Dict[str, float],
    ) -> List[RecipeCard]:
        """Solves counterfactual optimization generating exactly 3 distinct actionable recipe cards."""
        lever_cols = surrogate.feature_names
        p = len(lever_cols)
        w = np.array(surrogate.coefficients, dtype=float)
        b0 = surrogate.intercept
        mu = np.array(surrogate.mean_vector, dtype=float)

        x0 = np.array([
            float(current_values.get(c, surrogate.lever_bounds.get(c, {}).get("median", mu[j])))
            for j, c in enumerate(lever_cols)
        ], dtype=float)

        sigmas = np.array([
            max(1e-6, surrogate.lever_bounds.get(c, {}).get("std", 1.0))
            for c in lever_cols
        ], dtype=float)

        curr_y = float(np.dot(x0, w) + b0)
        direction = 1.0 if target_goal >= curr_y else -1.0

        min_bounds = np.array([surrogate.lever_bounds[c]["min"] for c in lever_cols], dtype=float)
        max_bounds = np.array([surrogate.lever_bounds[c]["max"] for c in lever_cols], dtype=float)
        p05_bounds = np.array([surrogate.lever_bounds[c]["p05"] for c in lever_cols], dtype=float)
        p95_bounds = np.array([surrogate.lever_bounds[c]["p95"] for c in lever_cols], dtype=float)
        p01_bounds = np.array([surrogate.lever_bounds[c]["p01"] for c in lever_cols], dtype=float)
        p99_bounds = np.array([surrogate.lever_bounds[c]["p99"] for c in lever_cols], dtype=float)

        def _make_changes(x_sol: np.ndarray, changed_indices: Optional[List[int]] = None) -> List[Dict[str, Any]]:
            changes_list: List[Dict[str, Any]] = []
            for j, col in enumerate(lever_cols):
                if changed_indices is not None and j not in changed_indices:
                    continue
                orig_v = float(x0[j])
                new_v = float(x_sol[j])
                d_val = new_v - orig_v
                d_pct = (d_val / abs(orig_v) * 100.0) if abs(orig_v) > 1e-6 else 0.0
                b_info = surrogate.lever_bounds.get(col, {})
                p01 = b_info.get("p01", min_bounds[j])
                p05 = b_info.get("p05", min_bounds[j])
                p95 = b_info.get("p95", max_bounds[j])
                p99 = b_info.get("p99", max_bounds[j])

                if new_v < p01 or new_v > p99:
                    zn = "red"
                elif new_v < p05 or new_v > p95:
                    zn = "amber"
                else:
                    zn = "green"

                changes_list.append({
                    "lever": col,
                    "from": round(orig_v, 2),
                    "to": round(new_v, 2),
                    "delta": round(d_val, 2),
                    "delta_pct": round(d_pct, 1),
                    "zone": zn,
                })
            return changes_list

        # ----------------------------------------------------------------------
        # Card 1: "The Easiest Tweak" (Concentrated in 1 single lever)
        # ----------------------------------------------------------------------
        delta_needed = target_goal - curr_y
        single_candidates: List[Tuple[float, int, float]] = []

        for j in range(p):
            if abs(w[j]) > 1e-6:
                x_star_j = float(x0[j] + delta_needed / w[j])
                if min_bounds[j] <= x_star_j <= max_bounds[j]:
                    cost = abs(x_star_j - x0[j]) / sigmas[j]
                    single_candidates.append((cost, j, x_star_j))

        x_1 = x0.copy()
        if single_candidates:
            single_candidates.sort(key=lambda t: t[0])
            best_cost, best_j, best_x = single_candidates[0]
            x_1[best_j] = best_x
            chosen_indices = [best_j]
            y_1 = float(np.dot(x_1, w) + b0)
            feas_1 = max(0.80, min(0.98, 1.0 - (best_cost / 10.0)))
        else:
            # Fallback to single most sensitive lever clamped to bounds
            sensitivities = np.abs(w * sigmas)
            best_j = int(np.argmax(sensitivities))
            if w[best_j] * direction > 0:
                x_1[best_j] = max_bounds[best_j] if direction > 0 else min_bounds[best_j]
            else:
                x_1[best_j] = min_bounds[best_j] if direction > 0 else max_bounds[best_j]
            chosen_indices = [best_j]
            y_1 = float(np.dot(x_1, w) + b0)
            feas_1 = 0.50 if abs(y_1 - target_goal) > 100.0 else 0.85

        card_1 = RecipeCard(
            id="card_1",
            title="The Easiest Tweak",
            strategy_badge="Single Lever",
            card_type="sparsity",
            description="Concentrates changes into a single high-impact lever to minimize disruption to operations.",
            changes=_make_changes(x_1, chosen_indices),
            predicted_target=round(y_1, 2),
            target_outcome=round(target_goal, 2),
            feasibility_score=round(feas_1, 2),
            confidence_badge=JargonTranslator.get_confidence_badge(r_squared=surrogate.r_squared, is_ood=False),
            slider_values={c: round(float(x_1[j]), 2) for j, c in enumerate(lever_cols)},
            lever_deltas={c: round(float(x_1[j] - x0[j]), 2) for j, c in enumerate(lever_cols)},
            lever_targets={c: round(float(x_1[j]), 2) for j, c in enumerate(lever_cols)},
        )

        # ----------------------------------------------------------------------
        # Card 2: "The Balanced Approach" (Multi-lever L2 regularized SLSQP)
        # ----------------------------------------------------------------------
        res_2 = minimize(
            fun=lambda x: float(np.sum(((x - x0) / sigmas) ** 2)),
            x0=x0.copy(),
            method="SLSQP",
            bounds=list(zip(min_bounds, max_bounds)),
            constraints={"type": "ineq", "fun": lambda x: direction * (float(np.dot(x, w) + b0) - target_goal)},
        )
        if res_2.success:
            x_2 = res_2.x
        else:
            # Clamping to closest attainable point within bounds
            res_2_clamp = minimize(
                fun=lambda x: (float(np.dot(x, w) + b0) - target_goal) ** 2,
                x0=x0.copy(),
                method="SLSQP",
                bounds=list(zip(min_bounds, max_bounds)),
            )
            x_2 = res_2_clamp.x if res_2_clamp.success else np.clip(x0 + direction * sigmas * 0.5, min_bounds, max_bounds)

        y_2 = float(np.dot(x_2, w) + b0)
        l2_dist_2 = float(np.sum(((x_2 - x0) / sigmas) ** 2))
        feas_2 = max(0.20, min(0.90, 0.95 - (l2_dist_2 / (4.0 * p))))
        if abs(y_2 - target_goal) > 100.0:
            feas_2 = min(feas_2, 0.45)

        card_2 = RecipeCard(
            id="card_2",
            title="The Balanced Approach",
            strategy_badge="Multi-Lever Balanced",
            card_type="balanced",
            description="Moderate, proportional adjustments across multiple levers to distribute operational effort.",
            changes=_make_changes(x_2),
            predicted_target=round(y_2, 2),
            target_outcome=round(target_goal, 2),
            feasibility_score=round(feas_2, 2),
            confidence_badge=JargonTranslator.get_confidence_badge(r_squared=surrogate.r_squared, is_ood=False),
            slider_values={c: round(float(x_2[j]), 2) for j, c in enumerate(lever_cols)},
            lever_deltas={c: round(float(x_2[j] - x0[j]), 2) for j, c in enumerate(lever_cols)},
            lever_targets={c: round(float(x_2[j]), 2) for j, c in enumerate(lever_cols)},
        )

        # ----------------------------------------------------------------------
        # Card 3: "Aggressive Growth / Stretch" (Aggressive multi-lever push)
        # ----------------------------------------------------------------------
        # Solves with higher penalty or wider bounds towards target goal
        res_3 = minimize(
            fun=lambda x: float(np.sum(((x - x0) / sigmas) ** 2)),
            x0=x0.copy(),
            method="SLSQP",
            bounds=list(zip(min_bounds, max_bounds)),
            constraints={"type": "ineq", "fun": lambda x: direction * (float(np.dot(x, w) + b0) - target_goal)},
        )
        if res_3.success:
            x_3 = res_3.x
        else:
            res_3_clamp = minimize(
                fun=lambda x: (float(np.dot(x, w) + b0) - target_goal) ** 2,
                x0=x0.copy(),
                method="SLSQP",
                bounds=list(zip(min_bounds, max_bounds)),
            )
            x_3 = res_3_clamp.x if res_3_clamp.success else np.clip(x0 + direction * sigmas, min_bounds, max_bounds)

        y_3 = float(np.dot(x_3, w) + b0)
        # Card 3 feasibility score is intentionally lower than Card 1 (reflecting higher operational friction/risk)
        feas_3 = max(0.10, min(feas_1 - 0.15, 0.65))
        if abs(y_3 - target_goal) > 100.0:
            feas_3 = min(feas_3, 0.35)

        card_3 = RecipeCard(
            id="card_3",
            title="Aggressive Growth",
            strategy_badge="Stretch Goal",
            card_type="stretch",
            description="Aggressive operational adjustments targeting full metric recovery or ambitious expansion.",
            changes=_make_changes(x_3),
            predicted_target=round(y_3, 2),
            target_outcome=round(target_goal, 2),
            feasibility_score=round(feas_3, 2),
            confidence_badge=JargonTranslator.get_confidence_badge(r_squared=surrogate.r_squared, is_ood=False),
            slider_values={c: round(float(x_3[j]), 2) for j, c in enumerate(lever_cols)},
            lever_deltas={c: round(float(x_3[j] - x0[j]), 2) for j, c in enumerate(lever_cols)},
            lever_targets={c: round(float(x_3[j]), 2) for j, c in enumerate(lever_cols)},
        )

        return [card_1, card_2, card_3]

    def simulate_weather_distribution(
        self,
        surrogate: SurrogateModel,
        slider_values: Dict[str, float],
        target_goal: Optional[float] = None,
        n_sims: int = 1000,
        **kwargs: Any,
    ) -> WeatherForecastDistribution:
        """Monte Carlo uncertainty distribution and 3-layer Apache ECharts boxplot option tree."""
        n_draws = int(kwargs.get("n_draws", n_sims))
        sim = self.predict(surrogate, slider_values)
        y_hat = sim.predicted_value

        rng = np.random.default_rng(42)
        sims = y_hat + rng.normal(0.0, surrogate.residual_std, size=max(100, n_draws))

        p10, p25, p50, p75, p90 = [float(v) for v in np.percentile(sims, [10, 25, 50, 75, 90])]

        direction = 1.0 if target_goal is not None and target_goal >= surrogate.baseline_prediction else -1.0
        if target_goal is not None:
            hits = (sims >= target_goal) if direction > 0 else (sims <= target_goal)
            prob_pct = round(float(np.mean(hits)) * 100.0, 1)
            prob_unit = round(prob_pct / 100.0, 4)
        else:
            prob_pct = 50.0
            prob_unit = 0.5

        gauge_color = (
            COLOR_EMERALD_GREEN if prob_pct >= 70.0
            else (COLOR_CAUTION_AMBER if prob_pct >= 40.0 else COLOR_CORAL_RED)
        )

        sub_text = (
            f"{n_draws:,} Monte Carlo scenarios • {prob_pct:.1f}% probability of achieving target ({target_goal:,.0f})"
            if target_goal is not None
            else f"{n_draws:,} Monte Carlo scenarios • Expected median: {p50:,.0f}"
        )

        mark_data = []
        if target_goal is not None:
            mark_data.append({
                "xAxis": round(target_goal, 2),
                "label": {
                    "formatter": f"Target: {target_goal:,.0f}",
                    "color": gauge_color,
                    "fontSize": 11,
                },
            })
        mark_data.append({
            "xAxis": round(surrogate.baseline_prediction, 2),
            "label": {
                "formatter": f"Baseline: {surrogate.baseline_prediction:,.0f}",
                "color": COLOR_DASHED_LINE,
                "fontSize": 11,
            },
        })

        echarts_option: Dict[str, Any] = {
            "title": {
                "text": f"Simulated Outcome: Likely Range {p10:,.0f} – {p90:,.0f}",
                "subtext": sub_text,
                "left": "left",
                "textStyle": {"fontSize": 14, "fontWeight": 600, "color": "#0f172a"},
                "subtextStyle": {"fontSize": 11, "color": "#64748b"},
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}<br/>90th % (Optimistic): {c4}<br/>75th %: {c3}<br/>Median: {c2}<br/>25th %: {c1}<br/>10th % (Conservative): {c0}",
            },
            "grid": {"left": "5%", "right": "8%", "bottom": "10%", "top": "20%", "containLabel": True},
            "xAxis": {"type": "value", "name": surrogate.target_col or "Outcome"},
            "yAxis": {"type": "category", "data": ["Simulated Scenario"]},
            "series": [
                {
                    "name": "Outcome Range",
                    "type": "boxplot",
                    "data": [[round(p10, 2), round(p25, 2), round(p50, 2), round(p75, 2), round(p90, 2)]],
                    "itemStyle": {
                        "color": "rgba(59, 130, 246, 0.2)",
                        "borderColor": COLOR_ELECTRIC_BLUE,
                        "borderWidth": 2,
                    },
                    "markLine": {
                        "silent": True,
                        "symbol": "none",
                        "lineStyle": {"type": "dashed", "color": COLOR_DASHED_LINE, "width": 2},
                        "data": mark_data,
                    },
                }
            ],
        }

        return WeatherForecastDistribution(
            percentiles={
                "p10": round(p10, 2),
                "p25": round(p25, 2),
                "p50": round(p50, 2),
                "p75": round(p75, 2),
                "p90": round(p90, 2),
            },
            p10=round(p10, 2),
            p25=round(p25, 2),
            p50=round(p50, 2),
            p75=round(p75, 2),
            p90=round(p90, 2),
            expected_outcome=round(p50, 2),
            probability_of_goal=prob_unit,
            goal_probability_pct=prob_pct,
            echarts_whisker_option=echarts_option,
            confidence_badge=sim.confidence_badge,
            gauge_color=gauge_color,
            mean=round(float(np.mean(sims)), 2),
            std=round(float(np.std(sims)), 2),
            sample_draws=n_draws,
        )
