"""
Comprehensive unit tests for DominoTimeline (Multi-Metric Changepoint & Lead-Lag Ordering).
Verifies pure NumPy PELT, cascade ordering, cross-correlation lags, synchronized sparklines,
constant metric handling, and tie-breaking.
"""

import numpy as np
import pandas as pd
import pytest

from pipeline_core.statistics import DominoTimeline
from backend.exceptions import ChangepointDetectionError, DiagnosticEngineError, WPSAIBaseException


def test_exception_inheritance():
    """Verifies ChangepointDetectionError inheritance hierarchy."""
    assert issubclass(ChangepointDetectionError, DiagnosticEngineError)
    assert issubclass(ChangepointDetectionError, WPSAIBaseException)
    err = ChangepointDetectionError("PELT error", details="N < 10")
    assert "PELT error" in str(err)
    assert "N < 10" in str(err)


def test_domino_timeline_cascade_ordering():
    """Verifies that DominoTimeline correctly identifies root cause and cascade sequence."""
    rng = np.random.default_rng(42)
    n = 60
    t0_idx = 20

    times = [f"2026-01-01 00:{i:02d}" for i in range(n)]

    # Metric A: breaks first at t0_idx
    ma = np.ones(n) * 10.0 + rng.normal(0, 0.5, n)
    ma[t0_idx:] += 50.0

    # Metric B: breaks at t0_idx + 4
    mb = np.ones(n) * 20.0 + rng.normal(0, 0.5, n)
    mb[t0_idx + 4:] += 80.0

    # Metric C: breaks at t0_idx + 8
    mc = np.ones(n) * 5.0 + rng.normal(0, 0.2, n)
    mc[t0_idx + 8:] += 25.0

    df = pd.DataFrame({
        "timestamp": times,
        "Metric_A": ma,
        "Metric_B": mb,
        "Metric_C": mc,
    })

    timeline = DominoTimeline()
    result = timeline.detect_cascade(df=df, time_col="timestamp", metric_cols=["Metric_A", "Metric_B", "Metric_C"])

    assert isinstance(result, dict)
    assert result["root_cause_metric"] == "Metric_A"
    assert result["t0_timestamp"] == times[t0_idx]

    order = result["cascade_order"]
    metrics_ordered = [item["metric"] for item in order]
    assert metrics_ordered[0] == "Metric_A"
    assert metrics_ordered[1] == "Metric_B"
    assert metrics_ordered[2] == "Metric_C"


def test_domino_timeline_constant_metric_handled():
    """Verifies that flatline constant metrics are handled gracefully and sorted to the bottom."""
    n = 30
    df = pd.DataFrame({
        "time": [f"00:{i:02d}" for i in range(n)],
        "active_metric": np.concatenate([np.ones(15) * 10, np.ones(15) * 50]),
        "constant_metric": [42.0] * n,
    })

    timeline = DominoTimeline()
    result = timeline.detect_cascade(df=df, time_col="time", metric_cols=["active_metric", "constant_metric"])

    assert result["root_cause_metric"] == "active_metric"
    order = result["cascade_order"]
    assert order[-1]["metric"] == "constant_metric"
    assert order[-1]["lag_steps"] is None


def test_domino_timeline_tie_breaking():
    """Verifies that simultaneous changepoints are broken by jump magnitude."""
    n = 30
    m1 = np.ones(n) * 10.0
    m2 = np.ones(n) * 10.0
    # Both break at index 15, but m2 has much larger jump
    m1[15:] = 20.0  # jump = 10
    m2[15:] = 100.0  # jump = 90

    df = pd.DataFrame({
        "time": [f"00:{i:02d}" for i in range(n)],
        "metric_small": m1,
        "metric_large": m2,
    })

    timeline = DominoTimeline()
    result = timeline.detect_cascade(df=df, time_col="time", metric_cols=["metric_small", "metric_large"])

    assert result["root_cause_metric"] == "metric_large"


def test_domino_timeline_echarts_sparklines_spec():
    """Verifies that output ECharts spec includes synchronized sparklines with T=0 reference line."""
    n = 30
    df = pd.DataFrame({
        "time": [f"00:{i:02d}" for i in range(n)],
        "m1": np.concatenate([np.ones(10) * 10, np.ones(20) * 50]),
        "m2": np.concatenate([np.ones(15) * 20, np.ones(15) * 80]),
    })

    timeline = DominoTimeline()
    result = timeline.detect_cascade(df=df, time_col="time", metric_cols=["m1", "m2"])

    spec = result["echarts_spec"]
    option = spec["option"]

    # Multiple grids for synchronized sparklines
    assert len(option["grid"]) == 2
    assert len(option["series"]) == 2

    # markLine present on series
    root_series = option["series"][0]
    assert "markLine" in root_series
    assert root_series["markLine"]["data"][0]["xAxis"] == result["t0_timestamp"]

    # markPoint present on root series
    assert "markPoint" in root_series


def test_domino_timeline_insufficient_data_raises_error():
    """Verifies that fewer than 10 rows raises ChangepointDetectionError."""
    df_short = pd.DataFrame({
        "time": ["01", "02", "03"],
        "metric": [1.0, 2.0, 3.0],
    })
    timeline = DominoTimeline()
    with pytest.raises(ChangepointDetectionError):
        timeline.detect_cascade(df=df_short, time_col="time", metric_cols=["metric"])
