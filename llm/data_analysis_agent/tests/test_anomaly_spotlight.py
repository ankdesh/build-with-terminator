"""
Comprehensive unit tests for AnomalySpotlight (Subgroup Slice Isolation).
Verifies beam search, Welch's t-test, contribution metrics, 3-layer ECharts spec,
and robust boundary condition handling.
"""

import math
import numpy as np
import pandas as pd
import pytest

from pipeline_core.statistics import AnomalySpotlight
from backend.exceptions import SubgroupSliceError, DiagnosticEngineError, WPSAIBaseException


def test_exception_inheritance():
    """Verifies SubgroupSliceError inheritance hierarchy."""
    assert issubclass(SubgroupSliceError, DiagnosticEngineError)
    assert issubclass(SubgroupSliceError, WPSAIBaseException)
    err = SubgroupSliceError("Slice error", details="Zero variance")
    assert "Slice error" in str(err)
    assert "Zero variance" in str(err)


def test_anomaly_spotlight_known_synthetic_cohort():
    """Verifies that AnomalySpotlight isolates a known injected anomalous subgroup."""
    rng = np.random.default_rng(42)
    n = 600

    warehouses = ["North", "South", "East", "West"]
    carriers = ["Express", "Standard", "Economy"]

    wh_col = rng.choice(warehouses, size=n)
    cr_col = rng.choice(carriers, size=n)
    rev = rng.normal(100.0, 5.0, size=n)

    # Incur significant drop in North + Express
    culprit_mask = (wh_col == "North") & (cr_col == "Express")
    rev[culprit_mask] = rng.normal(30.0, 3.0, size=int(np.sum(culprit_mask)))

    df = pd.DataFrame({
        "Warehouse": wh_col,
        "Carrier": cr_col,
        "Revenue": rev,
    })

    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Revenue", baseline_val=100.0, max_depth=2, beam_width=5)

    assert isinstance(result, dict)
    assert "culprits" in result
    culprits = result["culprits"]
    assert len(culprits) >= 1

    top = culprits[0]
    preds = top["predicates"]
    # Either both or at least one of the true culprits should be identified
    assert ("Warehouse" in preds and preds["Warehouse"] == "North") or ("Carrier" in preds and preds["Carrier"] == "Express")
    assert top["slice_mean"] < 60.0
    assert top["rest_mean"] > 90.0
    assert top["ratio_vs_normal"] < 0.6
    assert top["pct_drop_explained"] > 0.0
    assert top["p_value"] < 0.01
    assert top["confidence_badge"]["level"] in ["high", "moderate"]


def test_anomaly_spotlight_three_layer_echarts_rule():
    """Verifies that the ECharts option tree strictly adheres to the 3-Layer Rule."""
    df = pd.DataFrame({
        "Region": ["North"] * 50 + ["South"] * 50,
        "Latency": [150.0] * 50 + [40.0] * 50,
    })

    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Latency", baseline_val=40.0)

    spec = result["echarts_spec"]
    option = spec["option"]

    # Layer 3: Plain-English Title
    assert "title" in option
    title = option["title"]
    assert "text" in title
    assert "Dropped" in title["text"] or "Spiked" in title["text"]
    assert "p=" not in title["text"] and "Welch" not in title["text"] and "t-statistic" not in title["text"]

    # Layer 2: Spotlight Colors (#ef4444 for culprit vs #94a3b8 for rest)
    series = option["series"][0]
    data = series["data"]
    colors = [item["itemStyle"]["color"].lower() for item in data]
    assert "#ef4444" in colors
    assert "#94a3b8" in colors

    # Layer 1: Context markLine
    assert "markLine" in series
    mark_line_data = series["markLine"]["data"]
    assert len(mark_line_data) >= 1
    assert mark_line_data[0]["xAxis"] == 40.0


def test_anomaly_spotlight_zero_variance_handling():
    """Verifies that zero-variance metric returns empty culprits list gracefully."""
    df = pd.DataFrame({
        "Category": ["A", "B", "C", "A", "B"] * 5,
        "Value": [50.0] * 25,
    })
    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Value")
    assert result["culprits"] == []
    assert "No Anomalous Subgroup" in result["echarts_spec"]["title"]["text"]


def test_anomaly_spotlight_high_cardinality_uuid_exclusion():
    """Verifies that UUID and ID columns with high cardinality are excluded."""
    n = 200
    df = pd.DataFrame({
        "User_UUID": [f"uuid_{i:05d}" for i in range(n)],
        "Group": ["A"] * 100 + ["B"] * 100,
        "Score": [10.0] * 100 + [90.0] * 100,
    })
    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Score")
    for culprit in result["culprits"]:
        assert "User_UUID" not in culprit["predicates"]


def test_anomaly_spotlight_min_support_exclusion():
    """Verifies that slices below min_support are excluded."""
    cats = ["Normal"] * 98 + ["Tiny"] * 2
    vals = [100.0] * 98 + [5.0] * 2
    df = pd.DataFrame({"Category": cats, "Value": vals})

    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Value", min_support=5)
    for culprit in result["culprits"]:
        assert culprit["predicates"].get("Category") != "Tiny"


def test_anomaly_spotlight_invalid_inputs_raise_error():
    """Verifies that invalid metric column or non-dataframe input raises SubgroupSliceError."""
    spotlight = AnomalySpotlight()
    with pytest.raises(SubgroupSliceError):
        spotlight.isolate_slices(df="not a dataframe", metric_col="Revenue")  # type: ignore[arg-type]

    df = pd.DataFrame({"A": [1, 2, 3]})
    with pytest.raises(SubgroupSliceError):
        spotlight.isolate_slices(df=df, metric_col="NonExistent")


def test_anomaly_spotlight_default_baseline_none_drop_pct_nonzero():
    """Regression Guard: Verifies that when baseline_val is None, pct_drop_explained is strictly > 0 for known drop."""
    df = pd.DataFrame({
        "Segment": ["Bad"] * 40 + ["Normal"] * 160,
        "Conversion": [0.10] * 40 + [0.90] * 160,
    })
    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Conversion", baseline_val=None)

    assert len(result["culprits"]) >= 1
    top = result["culprits"][0]
    assert top["predicates"] == {"Segment": "Bad"}
    # The drop percentage explained must reflect the true contribution, not collapse to 0.0%
    assert top["pct_drop_explained"] > 50.0
    assert "(0.0% drop explained)" not in result["summary"]


def test_anomaly_spotlight_negative_values_headline_not_inverted():
    """Regression Guard: Verifies that drops in negative metrics are reported as 'Dropped', not 'Spiked'."""
    df = pd.DataFrame({
        "Segment": ["LossMaker"] * 50 + ["Normal"] * 50,
        "Net_Profit": [-100.0] * 50 + [-10.0] * 50,
    })
    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Net_Profit", baseline_val=-10.0)

    assert len(result["culprits"]) >= 1
    top = result["culprits"][0]
    assert top["predicates"] == {"Segment": "LossMaker"}
    title_text = result["echarts_spec"]["title"]["text"]
    # Net profit dropped from -10 to -100, so headline must say 'Dropped', never 'Spiked'
    assert "Dropped" in title_text
    assert "Spiked" not in title_text


def test_anomaly_spotlight_column_exclusion_id_suffix_vs_valid_words():
    """Regression Guard: Verifies that columns ending with '_id' are excluded, but valid business words like 'Paid' are kept."""
    n = 100
    df = pd.DataFrame({
        "customer_id": [f"c_{i}" for i in range(n)],
        "account_id": [f"acc_{i}" for i in range(n)],
        "Paid": ["Yes"] * 50 + ["No"] * 50,
        "Churn": [0.05] * 50 + [0.80] * 50,
    })
    spotlight = AnomalySpotlight()
    result = spotlight.isolate_slices(df=df, metric_col="Churn")

    assert len(result["culprits"]) >= 1
    for culprit in result["culprits"]:
        preds = culprit["predicates"]
        assert "customer_id" not in preds
        assert "account_id" not in preds
    # The valid column 'Paid' should be discovered
    top_preds = result["culprits"][0]["predicates"]
    assert "Paid" in top_preds

