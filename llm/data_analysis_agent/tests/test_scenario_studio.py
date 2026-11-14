"""Comprehensive unit and integration test suite for What-If Studio (Milestone 3).

Covers:
- Feature role inference (happy path, constants, zero numeric, missing values)
- Closed-form Ridge surrogate fitting (recovery, collinearity, single feature, underdetermined N < P)
- Mahalanobis OOD guardrails and 3-zone track classification
- 3 Distinct counterfactual recipe cards (feasibility, bounds, monotonicity)
- Monte Carlo weather forecast distribution & Apache ECharts option trees
- SessionStore surrogate cache lifecycle & session isolation
- Sub-100ms API response latency benchmarks
- Air-gap & zero-bloat compliance (no matplotlib/seaborn/plotly)
"""

import ast
from pathlib import Path
import time
from typing import Any, Dict, List
import numpy as np
import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app
from backend.exceptions import (
    CounterfactualOptimizationError,
    OODDetectionError,
    ScenarioSimulationError,
    SessionNotFoundError,
    SurrogateModelError,
)
from backend.models.whatif import (
    FeatureRoles,
    RecipeCard,
    SimulationResult,
    SurrogateModel,
    WeatherForecastDistribution,
)
from backend.services.session_store import SessionStore
from backend.services.whatif_service import WhatIfService


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def synthetic_retail_df() -> pd.DataFrame:
    """Standard synthetic retail scenario dataset."""
    rng = np.random.default_rng(42)
    n = 300
    discount = rng.uniform(0.05, 0.40, size=n)
    ad_spend = rng.uniform(200.0, 2000.0, size=n)
    inventory = rng.uniform(50.0, 500.0, size=n)
    margin = 5000.0 - 4500.0 * discount + 1.8 * ad_spend + 3.2 * inventory + rng.normal(0, 20.0, size=n)

    return pd.DataFrame({
        "Store_ID": [f"STORE_{i:03d}" for i in range(n)],
        "Region": rng.choice(["East", "West", "North"], size=n),
        "Discount_Pct": discount,
        "Ad_Spend": ad_spend,
        "Inventory_Depth": inventory,
        "Revenue_Margin": margin,
    })


# ==============================================================================
# 1. Feature Role Inference Tests
# ==============================================================================

class TestFeatureRoleInference:
    """Verifies heuristic column classification into levers vs locked context."""

    def test_role_inference_happy_path(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        roles = service.infer_roles(df=synthetic_retail_df, target_col="Revenue_Margin")

        assert isinstance(roles, FeatureRoles)
        assert roles.target_col == "Revenue_Margin"
        assert "Discount_Pct" in roles.levers
        assert "Ad_Spend" in roles.levers
        assert "Inventory_Depth" in roles.levers
        assert "Store_ID" in roles.locked_context
        assert "Region" in roles.locked_context

        # Verify safe-zone bounds (P05 and P95)
        for lever in roles.levers:
            bounds = roles.lever_bounds[lever]
            assert bounds["min"] <= bounds["p05"] < bounds["p95"] <= bounds["max"]
            assert bounds["p01"] <= bounds["p05"]
            assert bounds["p95"] <= bounds["p99"]

    def test_role_inference_zero_numeric_columns(self) -> None:
        service = WhatIfService()
        df = pd.DataFrame({"ID": ["A", "B", "C"], "Category": ["X", "Y", "Z"]})
        with pytest.raises(ScenarioSimulationError):
            service.infer_roles(df=df, target_col="Category")

    def test_role_inference_constant_column_excluded_from_levers(self) -> None:
        service = WhatIfService()
        df = pd.DataFrame({
            "Ad_Spend": [100.0] * 50,  # Zero variance
            "Discount": np.linspace(0.1, 0.4, 50),
            "Target": np.linspace(10, 100, 50),
        })
        roles = service.infer_roles(df=df, target_col="Target")
        assert "Discount" in roles.levers
        assert "Ad_Spend" in roles.locked_context  # Constant column locked

    def test_role_inference_handles_missing_values(self) -> None:
        service = WhatIfService()
        df = pd.DataFrame({
            "Discount": [0.1, 0.2, np.nan, 0.4, 0.5, 0.3],
            "Ad_Spend": [100.0, np.nan, 300.0, 400.0, 500.0, 250.0],
            "Target": [10.0, 20.0, 30.0, 40.0, 50.0, 35.0],
        })
        roles = service.infer_roles(df=df, target_col="Target")
        assert "Discount" in roles.levers
        assert not np.isnan(roles.lever_bounds["Discount"]["p05"])


# ==============================================================================
# 2. Closed-Form Ridge Surrogate Fitting Tests
# ==============================================================================

class TestRidgeSurrogateFitting:
    """Verifies pure NumPy Ridge training and boundary conditions."""

    def test_ridge_accurate_linear_recovery(self) -> None:
        rng = np.random.default_rng(123)
        n = 500
        x1 = rng.uniform(10, 50, size=n)
        x2 = rng.uniform(100, 500, size=n)
        y = 20.0 + 3.0 * x1 - 0.5 * x2 + rng.normal(0, 0.5, size=n)

        df = pd.DataFrame({"X1": x1, "X2": x2, "Target": y})
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=df, target_col="Target", lever_cols=["X1", "X2"], alpha=0.1)

        assert isinstance(surrogate, SurrogateModel)
        assert surrogate.r_squared > 0.98
        assert abs(surrogate.coefficients[0] - 3.0) < 0.2
        assert abs(surrogate.coefficients[1] - (-0.5)) < 0.1

    def test_ridge_perfect_collinearity(self) -> None:
        x = np.linspace(1, 10, 50)
        df = pd.DataFrame({"L1": x, "L2": x, "Target": 2 * x})
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=df, target_col="Target", lever_cols=["L1", "L2"], alpha=1.0)
        assert surrogate is not None
        assert not np.isnan(surrogate.coefficients[0])

    def test_ridge_single_feature(self) -> None:
        df = pd.DataFrame({"Speed": [10.0, 20.0, 30.0, 40.0], "Dist": [20.0, 40.0, 60.0, 80.0]})
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=df, target_col="Dist", lever_cols=["Speed"])
        pred = service.predict(surrogate, {"Speed": 25.0})
        assert abs(pred.predicted_value - 50.0) < 1.0

    def test_ridge_underdetermined_system_n_less_than_p(self) -> None:
        """N=3 rows, P=5 levers. Closed-form Ridge must regularize without crashing."""
        df = pd.DataFrame({
            f"Lever_{i}": [1.0, 2.0, 3.0] for i in range(5)
        })
        df["Target"] = [10.0, 20.0, 30.0]
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=df, target_col="Target", lever_cols=[f"Lever_{i}" for i in range(5)], alpha=1.0)
        assert surrogate is not None
        assert len(surrogate.coefficients) == 5


# ==============================================================================
# 3. Mahalanobis OOD Distance & Zone Classification Tests
# ==============================================================================

class TestMahalanobisOOD:
    """Verifies historical covariance ellipsoid and 3-zone slider tracks."""

    def test_mahalanobis_center_in_distribution(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        levers = ["Discount_Pct", "Ad_Spend", "Inventory_Depth"]
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=levers)

        # Vector at exact mean has Mahalanobis distance ~ 0
        mean_vals = {lever: float(synthetic_retail_df[lever].mean()) for lever in levers}
        pred = service.predict(surrogate, mean_vals)

        assert pred.is_ood is False
        assert pred.mahalanobis_dist < 1.0
        assert pred.zone == "green"

    def test_mahalanobis_contradictory_extreme_ood(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        levers = ["Discount_Pct", "Ad_Spend"]
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=levers)

        # 95% discount with $10,000 ad spend (far outside historical covariance)
        extreme_slider = {"Discount_Pct": 0.95, "Ad_Spend": 10000.0}
        pred = service.predict(surrogate, extreme_slider)

        assert pred.is_ood is True
        assert pred.mahalanobis_dist > surrogate.chi2_critical_99
        assert pred.zone == "red"

    def test_3_zone_track_classification(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=["Discount_Pct"])

        p01 = surrogate.lever_bounds["Discount_Pct"]["p01"]
        p05 = surrogate.lever_bounds["Discount_Pct"]["p05"]
        p95 = surrogate.lever_bounds["Discount_Pct"]["p95"]
        p99 = surrogate.lever_bounds["Discount_Pct"]["p99"]

        # Green zone
        pred_green = service.predict(surrogate, {"Discount_Pct": (p05 + p95) / 2})
        assert pred_green.zone == "green"

        # Amber zone (between p95 and p99)
        pred_amber = service.predict(surrogate, {"Discount_Pct": (p95 + p99) / 2})
        assert pred_amber.zone == "amber"

        # Red zone (beyond p99)
        pred_red = service.predict(surrogate, {"Discount_Pct": p99 * 2.0})
        assert pred_red.zone == "red"


# ==============================================================================
# 4. Counterfactual Recipe Cards Tests
# ==============================================================================

class TestCounterfactualRecipes:
    """Verifies reverse what-if solver producing 3 actionable recipe cards."""

    def test_recipe_cards_triad_generation(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        levers = ["Discount_Pct", "Ad_Spend", "Inventory_Depth"]
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=levers)

        current = {"Discount_Pct": 0.20, "Ad_Spend": 500.0, "Inventory_Depth": 200.0}
        target_goal = 6000.0
        recipes = service.solve_recipes(surrogate, target_goal=target_goal, current_values=current)

        assert len(recipes) == 3
        card1, card2, card3 = recipes[0], recipes[1], recipes[2]

        # Card 1: Easiest tweak (concentrated in 1 lever)
        assert len(card1.changes) == 1
        # Card 2: Balanced approach (multi-lever regularized)
        assert len(card2.changes) >= 1
        # Card 3: Aggressive / Stretch
        assert card3.predicted_outcome >= target_goal or abs(card3.predicted_outcome - target_goal) < 50.0

        # Feasibility score ordering: Card 1 >= Card 3
        assert card1.feasibility_score >= card3.feasibility_score
        assert all(0.0 <= r.feasibility_score <= 1.0 for r in recipes)

    def test_recipe_cards_bounds_adherence(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        levers = ["Discount_Pct", "Ad_Spend"]
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=levers)

        current = {"Discount_Pct": 0.20, "Ad_Spend": 500.0}
        recipes = service.solve_recipes(surrogate, target_goal=5500.0, current_values=current)

        for card in recipes:
            for change in card.changes:
                lever = change["lever"]
                bounds = surrogate.lever_bounds[lever]
                assert bounds["min"] <= change["to"] <= bounds["max"]

    def test_recipe_cards_unreachable_target_clamping(self, synthetic_retail_df: pd.DataFrame) -> None:
        """Physically impossible target must not hang; clamps to highest achievable boundary."""
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=["Discount_Pct"])
        recipes = service.solve_recipes(surrogate, target_goal=1e9, current_values={"Discount_Pct": 0.20})
        assert len(recipes) == 3
        for card in recipes:
            assert card.feasibility_score <= 0.5


# ==============================================================================
# 5. Monte Carlo Weather Forecast & ECharts Visuals Tests
# ==============================================================================

class TestWeatherForecast:
    """Verifies Monte Carlo uncertainty distribution and ECharts option trees."""

    def test_weather_percentiles_monotonicity(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        levers = ["Discount_Pct", "Ad_Spend"]
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=levers)

        current = {"Discount_Pct": 0.20, "Ad_Spend": 500.0}
        forecast = service.simulate_weather_distribution(surrogate, current, target_goal=5500.0, n_sims=1000)

        assert isinstance(forecast, WeatherForecastDistribution)
        p = forecast.percentiles
        assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]
        assert forecast.probability_of_goal is not None
        assert 0.0 <= forecast.probability_of_goal <= 1.0
        assert forecast.goal_probability_pct is not None
        assert 0.0 <= forecast.goal_probability_pct <= 100.0

    def test_weather_echarts_whisker_and_gauge_spec(self, synthetic_retail_df: pd.DataFrame) -> None:
        service = WhatIfService()
        surrogate = service.fit_surrogate(df=synthetic_retail_df, target_col="Revenue_Margin", lever_cols=["Discount_Pct"])
        forecast = service.simulate_weather_distribution(surrogate, {"Discount_Pct": 0.20}, target_goal=5500.0)

        spec = forecast.echarts_whisker_option
        assert "series" in spec
        assert "title" in spec
        assert "text" in spec["title"]


# ==============================================================================
# 6. SessionStore Surrogate Cache Lifecycle Tests
# ==============================================================================

class TestSessionStoreSurrogateCache:
    """Verifies in-memory surrogate cache lifecycle and invalidation in SessionStore."""

    def test_surrogate_cache_lifecycle(self, tmp_path: Any) -> None:
        store = SessionStore(base_dir=tmp_path)
        sess = store.create_session("Cache Session")
        model = SurrogateModel(
            feature_names=["A"],
            coefficients=[2.0],
            intercept=10.0,
            r_squared=0.99,
            cov_matrix_inv=[[1.0]],
            mean_vector=[5.0],
            chi2_critical_99=6.63,
            residual_std=1.0,
            lever_bounds={"A": {"min": 0, "max": 10, "p05": 1, "p95": 9, "p01": 0.5, "p99": 9.5}},
        )

        store.set_surrogate(sess.session_id, "Target", model)
        cached = store.get_surrogate(sess.session_id, "Target")
        assert cached is not None
        assert cached.intercept == 10.0

        # Session B cannot access Session A's cache
        assert store.get_surrogate("other_session", "Target") is None

        # Cache invalidation clears models
        store.invalidate_surrogate_cache(sess.session_id)
        assert store.get_surrogate(sess.session_id, "Target") is None

    def test_dataset_save_clears_surrogate_cache(self, tmp_path: Any) -> None:
        store = SessionStore(base_dir=tmp_path)
        sess = store.create_session("Save Dataset Test")
        model = SurrogateModel(
            feature_names=["A"],
            coefficients=[2.0],
            intercept=10.0,
            r_squared=0.99,
            cov_matrix_inv=[[1.0]],
            mean_vector=[5.0],
            chi2_critical_99=6.63,
            residual_std=1.0,
            lever_bounds={"A": {"min": 0, "max": 10, "p05": 1, "p95": 9, "p01": 0.5, "p99": 9.5}},
        )
        store.set_surrogate(sess.session_id, "Target", model)

        # Re-saving dataset must clear surrogate cache
        store.save_dataset(sess.session_id, b"a,b\n1,2", "test.csv", "desc", "desc.txt", 1, 2)
        assert store.get_surrogate(sess.session_id, "Target") is None

    def test_multi_instance_surrogate_cache_invalidation(self, tmp_path: Path) -> None:
        """Regression test for Finding 1 (reviewer_m3_2):
        Verifies that multiple SessionStore instances share the in-memory surrogate cache,
        and that cache invalidation via save_dataset, invalidate_surrogate_cache, or delete_session
        on one instance immediately evicts the cached model from all instances.
        """
        store1 = SessionStore(base_dir=tmp_path)
        store2 = SessionStore(base_dir=tmp_path)
        sess = store1.create_session("Multi-Instance Cache Invalidation")

        model = SurrogateModel(
            feature_names=["spend"],
            coefficients=[2.5],
            intercept=10.0,
            r_squared=0.98,
            cov_matrix_inv=[[1.0]],
            mean_vector=[100.0],
            chi2_critical_99=6.63,
            residual_std=1.0,
            lever_bounds={"spend": {"min": 0, "max": 200, "p05": 10, "p95": 190, "p01": 5, "p99": 195}},
        )

        # 1. Save surrogate in store1, verify store2 can read it
        store1.set_surrogate(sess.session_id, "margin", model)
        cached_model = store2.get_surrogate(sess.session_id, "margin")
        assert cached_model is not None, "store2 must see surrogate model saved by store1"
        assert cached_model.intercept == 10.0

        # 2. Invalidate via store2, verify store1 sees None
        store2.invalidate_surrogate_cache(sess.session_id)
        assert store1.get_surrogate(sess.session_id, "margin") is None, (
            "store1 must see cache evicted after store2.invalidate_surrogate_cache"
        )

        # 3. Re-save in store1, call store2.save_dataset(), verify store1 sees None
        store1.set_surrogate(sess.session_id, "margin", model)
        assert store2.get_surrogate(sess.session_id, "margin") is not None
        store2.save_dataset(
            session_id=sess.session_id,
            csv_bytes=b"spend,margin\n10,100\n20,200\n",
            csv_filename="test.csv",
            desc_text="desc",
            desc_filename="desc.txt",
            row_count=2,
            column_count=2,
        )
        assert store1.get_surrogate(sess.session_id, "margin") is None, (
            "store1 must see cache evicted after store2.save_dataset"
        )
        assert store2.get_surrogate(sess.session_id, "margin") is None, (
            "store2 must see cache evicted after store2.save_dataset"
        )

        # 4. Create second session, save surrogate, call store2.delete_session()
        sess_b = store1.create_session("Session B")
        store1.set_surrogate(sess_b.session_id, "margin", model)
        assert store2.get_surrogate(sess_b.session_id, "margin") is not None
        store2.delete_session(sess_b.session_id)
        assert store1.get_surrogate(sess_b.session_id, "margin") is None, (
            "store1 must see cache evicted after store2.delete_session"
        )
        assert store2.get_surrogate(sess_b.session_id, "margin") is None, (
            "store2 must see cache evicted after store2.delete_session"
        )

    def test_target_column_strict_matching(self, tmp_path: Path) -> None:
        """Regression test for Finding 2 (reviewer_m3_2):
        Verifies that requesting an uncached target column returns None rather than
        falling back to an arbitrary different metric's surrogate model.
        When target_col is None, fallback to default cached surrogate is preserved.
        """
        store = SessionStore(base_dir=tmp_path)
        sess = store.create_session("Target Column Matching")

        model_a = SurrogateModel(
            feature_names=["feature_x"],
            coefficients=[3.0],
            intercept=15.0,
            r_squared=0.97,
            cov_matrix_inv=[[1.0]],
            mean_vector=[50.0],
            chi2_critical_99=6.63,
            residual_std=1.2,
            lever_bounds={"feature_x": {"min": 0, "max": 100, "p05": 5, "p95": 95, "p01": 2, "p99": 98}},
        )

        # 1. Save surrogate for Metric_A
        store.set_surrogate(sess.session_id, "Metric_A", model_a)

        # 2. Request target_col="Metric_B" -> Must return None (NOT Metric_A's surrogate!)
        assert store.get_surrogate(sess.session_id, "Metric_B") is None, (
            "Requesting uncached target_col must return None to trigger auto-warming"
        )

        # 3. Request target_col=None -> Returns Metric_A's surrogate (default fallback)
        surrogate_none = store.get_surrogate(sess.session_id, None)
        assert surrogate_none is not None
        assert surrogate_none.intercept == 15.0

        # Clean up
        store.invalidate_surrogate_cache(sess.session_id)


# ==============================================================================
# 7. FastAPI Scenario Router Integration & Latency Benchmarks
# ==============================================================================

class TestScenarioRouterEndpoints:
    """Verifies HTTP API endpoints and sub-100ms response time requirement."""

    @pytest.mark.asyncio
    async def test_full_scenario_api_lifecycle_and_latency(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            # 1. Create session
            sess_resp = await client.post("/api/sessions", json={"title": "Scenario API Test"})
            assert sess_resp.status_code == 201
            session_id = sess_resp.json()["session_id"]

            # 2. Upload dataset
            repo_root = Path(__file__).resolve().parent.parent
            csv_path = repo_root / "sample_data" / "electric_usage.csv"
            desc_path = repo_root / "sample_data" / "electric_usage_desc.txt"
            with open(csv_path, "rb") as f_csv, open(desc_path, "rb") as f_desc:
                upload_resp = await client.post(
                    f"/api/sessions/{session_id}/upload",
                    files={
                        "csv_file": ("electric_usage.csv", f_csv, "text/csv"),
                        "desc_file": ("desc.txt", f_desc, "text/plain"),
                    },
                )
                assert upload_resp.status_code == 200

            # 3. Setup scenario (infer roles and fit surrogate)
            setup_resp = await client.post(
                f"/api/sessions/{session_id}/scenario/setup",
                json={"target_col": "kwh_consumed", "lever_cols": ["temperature_f", "occupancy_count"]},
            )
            assert setup_resp.status_code == 200
            setup_data = setup_resp.json()
            assert "levers" in setup_data["roles"]
            assert "surrogate" in setup_data
            assert "r_squared" in setup_data["surrogate"]

            # 4. Predict slider update — Latency Benchmark (< 100ms)
            predict_payload = {
                "target_col": "kwh_consumed",
                "slider_values": {"temperature_f": 72.0, "occupancy_count": 50.0},
            }
            t0 = time.perf_counter()
            pred_resp = await client.post(f"/api/sessions/{session_id}/scenario/predict", json=predict_payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert pred_resp.status_code == 200
            assert elapsed_ms < 100.0, f"API prediction latency {elapsed_ms:.2f}ms exceeded 100ms budget!"
            pred_data = pred_resp.json()
            assert "predicted_value" in pred_data
            assert "is_ood" in pred_data
            assert "zone" in pred_data

            # 5. Reverse Goal-Seeking Recipes
            recipes_resp = await client.post(
                f"/api/sessions/{session_id}/scenario/recipes",
                json={
                    "target_col": "kwh_consumed",
                    "target_goal": 30.0,
                    "current_values": {"temperature_f": 72.0, "occupancy_count": 50.0},
                },
            )
            assert recipes_resp.status_code == 200
            cards = recipes_resp.json()
            assert len(cards) == 3

            # 6. Monte Carlo Forecast
            forecast_resp = await client.post(
                f"/api/sessions/{session_id}/scenario/forecast",
                json={
                    "target_col": "kwh_consumed",
                    "slider_values": {"temperature_f": 72.0, "occupancy_count": 50.0},
                    "target_goal": 30.0,
                },
            )
            assert forecast_resp.status_code == 200
            forecast_data = forecast_resp.json()
            assert "percentiles" in forecast_data
            assert "echarts_whisker_option" in forecast_data

    @pytest.mark.asyncio
    async def test_fastapi_scenario_router_e2e_dataset_upload_invalidation(self) -> None:
        """Regression test for E2E dataset upload cache invalidation (reviewer_m3_2):
        Verifies that re-uploading a new CSV dataset to an active session invalidates
        the cached surrogate across router instances, causing /scenario/predict
        to auto-warm on the new dataset rather than serving stale predictions from the old dataset.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            # 1. Create a fresh session
            sess_resp = await client.post("/api/sessions", json={"title": "E2E Upload Invalidation"})
            assert sess_resp.status_code == 201
            session_id = sess_resp.json()["session_id"]

            try:
                # 2. Upload initial dataset: margin = 10 * spend
                # spend in [10, 20, 30, 40, 50], margin in [100, 200, 300, 400, 500]
                csv1 = (
                    b"spend,price,margin\n"
                    b"10.0,5.0,100.0\n"
                    b"20.0,6.0,200.0\n"
                    b"30.0,7.0,300.0\n"
                    b"40.0,8.0,400.0\n"
                    b"50.0,9.0,500.0\n"
                )
                up1 = await client.post(
                    f"/api/sessions/{session_id}/upload",
                    files={"csv_file": ("dataset_v1.csv", csv1, "text/csv")},
                )
                assert up1.status_code == 200

                # 3. Setup scenario on dataset 1
                setup_resp = await client.post(
                    f"/api/sessions/{session_id}/scenario/setup",
                    json={"target_col": "margin", "lever_cols": ["spend", "price"]},
                )
                assert setup_resp.status_code == 200

                # 4. Predict slider position for spend=20.0, price=6.0 -> expected ~200.0
                pred1_resp = await client.post(
                    f"/api/sessions/{session_id}/scenario/predict",
                    json={"target_col": "margin", "slider_values": {"spend": 20.0, "price": 6.0}},
                )
                assert pred1_resp.status_code == 200
                pred1_val = pred1_resp.json()["predicted_value"]
                assert abs(pred1_val - 200.0) < 5.0, f"Expected initial pred ~200.0, got {pred1_val}"

                # 5. Upload new dataset via /upload: margin = 100 * spend (10x higher values)
                csv2_clean = (
                    b"spend,price,margin\n"
                    b"10.0,5.0,1000.0\n"
                    b"20.0,6.0,2000.0\n"
                    b"30.0,7.0,3000.0\n"
                    b"40.0,8.0,4000.0\n"
                    b"50.0,9.0,5000.0\n"
                )
                up2 = await client.post(
                    f"/api/sessions/{session_id}/upload",
                    files={"csv_file": ("dataset_v2.csv", csv2_clean, "text/csv")},
                )
                assert up2.status_code == 200

                # 6. Immediately call predict without calling setup again.
                # Auto-warming must trigger on dataset 2; must NOT serve the old dataset 1 model.
                pred2_resp = await client.post(
                    f"/api/sessions/{session_id}/scenario/predict",
                    json={"target_col": "margin", "slider_values": {"spend": 20.0, "price": 6.0}},
                )
                assert pred2_resp.status_code == 200
                pred2_val = pred2_resp.json()["predicted_value"]

                # If stale model was served, pred2_val would be ~200.0.
                # With auto-warming on new dataset, pred2_val is ~2000.0.
                assert abs(pred2_val - 2000.0) < 50.0, (
                    f"Expected auto-warmed prediction on new dataset ~2000.0, but got {pred2_val}. "
                    f"Stale surrogate model from previous dataset was served!"
                )
            finally:
                await client.delete(f"/api/sessions/{session_id}")


# ==============================================================================
# 8. Air-Gap & Zero Backend Bloat Static Audit
# ==============================================================================

def test_scenario_studio_airgap_and_zero_bloat() -> None:
    """Verifies that no file in backend/services or backend/routes imports matplotlib, seaborn, or plotly."""
    repo_root = Path(__file__).resolve().parent.parent
    prohibited = {"matplotlib", "seaborn", "plotly"}

    for p in (repo_root / "backend").rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0].lower() not in prohibited, f"Prohibited import {alias.name} in {p}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0].lower() not in prohibited, f"Prohibited import {node.module} in {p}"
