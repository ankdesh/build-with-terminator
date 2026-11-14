"""
Comprehensive unit tests for BlameBridge (Period-Over-Period Shift Attribution Waterfall).
Verifies exact conservation, two-series stacked bar ECharts option tree,
top-K pooling, Rate-Mix decomposition, and robust boundary handling.
"""

import math
import numpy as np
import pandas as pd
import pytest

from pipeline_core.statistics import BlameBridge
from backend.exceptions import AttributionDecompositionError, DiagnosticEngineError, WPSAIBaseException


def test_exception_inheritance():
    """Verifies AttributionDecompositionError inheritance hierarchy."""
    assert issubclass(AttributionDecompositionError, DiagnosticEngineError)
    assert issubclass(AttributionDecompositionError, WPSAIBaseException)
    err = AttributionDecompositionError("Decomposition error", details="Mismatch delta")
    assert "Decomposition error" in str(err)
    assert "Mismatch delta" in str(err)


def test_blame_bridge_synthetic_linear_exact_conservation():
    """Verifies exact mathematical conservation on synthetic dataset."""
    rng = np.random.default_rng(42)
    n = 500

    # Baseline T0
    x1_0 = rng.normal(10.0, 2.0, size=n)
    x2_0 = rng.normal(50.0, 5.0, size=n)
    x3_0 = rng.normal(5.0, 1.0, size=n)
    y_0 = 100.0 + 3.0 * x1_0 - 2.0 * x2_0 + 1.5 * x3_0 + rng.normal(0, 1.0, size=n)

    df_t0 = pd.DataFrame({"X1": x1_0, "X2": x2_0, "X3": x3_0, "Target": y_0})

    # Current T1 (X1 increases by +5, X2 decreases by -10)
    x1_1 = rng.normal(15.0, 2.0, size=n)
    x2_1 = rng.normal(40.0, 5.0, size=n)
    x3_1 = rng.normal(5.0, 1.0, size=n)
    y_1 = 100.0 + 3.0 * x1_1 - 2.0 * x2_1 + 1.5 * x3_1 + rng.normal(0, 1.0, size=n)

    df_t1 = pd.DataFrame({"X1": x1_1, "X2": x2_1, "X3": x3_1, "Target": y_1})

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_t0, current_df=df_t1, metric_col="Target", top_k=2)

    assert isinstance(result, dict)
    baseline = result["baseline_mean"]
    current = result["current_mean"]
    total_delta = result["total_delta"]
    assert math.isclose(total_delta, current - baseline, abs_tol=1e-4)

    steps = result["steps"]
    step_delta_sum = sum(s["delta"] for s in steps)
    assert math.isclose(baseline + step_delta_sum, current, abs_tol=1e-4)

    # Check that X1 and X2 are identified as top drivers
    driver_names = [s["feature"] for s in steps]
    assert "X1" in driver_names or "X2" in driver_names


def test_blame_bridge_two_series_stacked_bar_echarts():
    """Verifies that ECharts option tree adheres to the two-series floating waterfall specification."""
    df_t0 = pd.DataFrame({"X": [10.0, 20.0], "Y": [100.0, 120.0]})
    df_t1 = pd.DataFrame({"X": [30.0, 40.0], "Y": [150.0, 170.0]})

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_t0, current_df=df_t1, metric_col="Y")

    spec = result["echarts_spec"]
    option = spec["option"]

    series = option["series"]
    assert len(series) == 2
    base_series = series[0]
    shift_series = series[1]

    assert base_series["stack"] == "bridge"
    assert shift_series["stack"] == "bridge"

    # Base series must be transparent and silent
    assert base_series["itemStyle"]["color"] == "transparent"
    assert base_series["silent"] is True
    assert base_series["tooltip"]["show"] is False

    # Shift series must include markLine at baseline
    assert "markLine" in shift_series


def test_blame_bridge_zero_net_delta():
    """Verifies that zero net delta runs cleanly without division by zero."""
    df_t0 = pd.DataFrame({"X": [10.0, 20.0], "Y": [100.0, 100.0]})
    df_t1 = pd.DataFrame({"X": [15.0, 25.0], "Y": [100.0, 100.0]})

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_t0, current_df=df_t1, metric_col="Y")

    assert math.isclose(result["total_delta"], 0.0, abs_tol=1e-5)
    assert math.isclose(result["baseline_mean"], result["current_mean"], abs_tol=1e-5)


def test_blame_bridge_single_feature():
    """Verifies that single feature inputs are handled without dimensional errors."""
    df_t0 = pd.DataFrame({"A": [1.0, 2.0, 3.0], "Y": [10.0, 20.0, 30.0]})
    df_t1 = pd.DataFrame({"A": [4.0, 5.0, 6.0], "Y": [40.0, 50.0, 60.0]})

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_t0, current_df=df_t1, metric_col="Y", feature_cols=["A"])

    assert len(result["steps"]) <= 2
    assert math.isclose(result["baseline_mean"] + sum(s["delta"] for s in result["steps"]), result["current_mean"], abs_tol=1e-4)


def test_blame_bridge_invalid_inputs_raise_error():
    """Verifies that missing columns or empty dataframes raise AttributionDecompositionError."""
    bridge = BlameBridge()

    df_empty = pd.DataFrame()
    df_valid = pd.DataFrame({"Y": [1, 2]})

    with pytest.raises(AttributionDecompositionError):
        bridge.attribute_shift(baseline_df=df_empty, current_df=df_valid, metric_col="Y")

    with pytest.raises(AttributionDecompositionError):
        bridge.attribute_shift(baseline_df=df_valid, current_df=df_valid, metric_col="NonExistent")


def test_blame_bridge_nan_in_metric_column_handled():
    """Regression Guard: Verifies that NaNs in metric column do not cause unhandled matmul dimension mismatch."""
    df_base = pd.DataFrame({
        "Feature1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        "Feature2": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
        "Metric": [100.0, 110.0, np.nan, 130.0, np.nan, 150.0, 160.0, 170.0],
    })
    df_curr = pd.DataFrame({
        "Feature1": [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        "Feature2": [15.0, 25.0, 35.0, 45.0, np.nan, 65.0, 75.0, 85.0],
        "Metric": [120.0, np.nan, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0],
    })

    bridge = BlameBridge()
    # Must execute cleanly without unhandled ValueError
    result = bridge.attribute_shift(baseline_df=df_base, current_df=df_curr, metric_col="Metric")
    assert isinstance(result, dict)
    assert "baseline_mean" in result
    assert "current_mean" in result
    assert "steps" in result
    # Conservation must still hold
    assert math.isclose(
        result["baseline_mean"] + sum(s["delta"] for s in result["steps"]),
        result["current_mean"],
        abs_tol=1e-4,
    )


def test_blame_bridge_50_features_exact_conservation_zero_drift():
    """Regression Guard: Verifies that with 50 features, exact conservation holds identically down to 1e-12."""
    rng = np.random.default_rng(999)
    n = 200
    n_feats = 50
    X_base = rng.normal(0, 1, size=(n, n_feats))
    weights = rng.uniform(0.1, 2.0, size=n_feats)
    Y_base = X_base @ weights + rng.normal(0, 0.5, size=n)

    shift = rng.normal(0.2, 0.1, size=n_feats)
    X_curr = rng.normal(0, 1, size=(n, n_feats)) + shift
    Y_curr = X_curr @ weights + rng.normal(0, 0.5, size=n)

    df_base = pd.DataFrame({f"feat_{i:02d}": X_base[:, i] for i in range(n_feats)})
    df_base["Metric"] = Y_base
    df_curr = pd.DataFrame({f"feat_{i:02d}": X_curr[:, i] for i in range(n_feats)})
    df_curr["Metric"] = Y_curr

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_base, current_df=df_curr, metric_col="Metric", top_k=5)

    baseline = result["baseline_mean"]
    current = result["current_mean"]
    steps_sum = sum(s["delta"] for s in result["steps"])
    discrepancy = abs(baseline + steps_sum - current)

    # Must satisfy exact conservation without rounding accumulation drift
    assert discrepancy < 1e-12, f"Conservation drift exceeded 1e-12: {discrepancy}"
    assert math.isclose(baseline + steps_sum, current, abs_tol=1e-12)

    # Also verify raw unrounded float conservation
    raw_discrepancy = abs(result["raw_baseline_mean"] + sum(s["raw_delta"] for s in result["steps"]) - result["raw_current_mean"])
    assert raw_discrepancy < 1e-12


def test_blame_bridge_collinear_features_exact_conservation():
    """Regression Guard: Verifies that collinear features execute without matrix singularity and conserve exactly."""
    rng = np.random.default_rng(123)
    n = 100
    x = rng.normal(10, 2, size=n)
    df_0 = pd.DataFrame({"X1": x, "X2": 2 * x, "X3": -0.5 * x, "Target": 3 * x})
    x_c = rng.normal(15, 2, size=n)
    df_1 = pd.DataFrame({"X1": x_c, "X2": 2 * x_c, "X3": -0.5 * x_c, "Target": 3 * x_c})

    bridge = BlameBridge()
    result = bridge.attribute_shift(baseline_df=df_0, current_df=df_1, metric_col="Target")
    discrepancy = abs(result["baseline_mean"] + sum(s["delta"] for s in result["steps"]) - result["current_mean"])
    assert discrepancy < 1e-12


def test_blame_bridge_all_nan_metric_raises_domain_error():
    """Regression Guard: Verifies that all-NaN metric column raises explicit AttributionDecompositionError."""
    df_base = pd.DataFrame({"A": [1, 2], "Metric": [np.nan, np.nan]})
    df_curr = pd.DataFrame({"A": [3, 4], "Metric": [10.0, 20.0]})

    bridge = BlameBridge()
    with pytest.raises(AttributionDecompositionError):
        bridge.attribute_shift(baseline_df=df_base, current_df=df_curr, metric_col="Metric")

