"""Comprehensive unit tests for JargonTranslator, ConfidenceBadge, and 3-Layer Visual Grammar."""

import pytest
import pandas as pd
import numpy as np

from backend.models.chat import ConfidenceBadge, ExecutionResult, FollowUpChip, ChartSpec, TableData
from backend.services.jargon_translator import (
    JargonTranslator,
    COLOR_CORAL_RED,
    COLOR_MUTED_SLATE,
    COLOR_DASHED_LINE,
    JARGON_TOOLTIP_DICTIONARY,
)


class TestConfidenceBadgeAndFollowUpChipModels:
    """Tests Pydantic models for confidence badges and follow-up chips."""

    def test_confidence_badge_model_instantiation(self) -> None:
        badge = ConfidenceBadge(
            level="high",
            icon="🟢",
            title="High Confidence Finding",
            subtitle="Based on 100 observations",
            metric_source="p_value",
            raw_value=0.002,
        )
        assert badge.level == "high"
        assert badge.icon == "🟢"
        assert badge.title == "High Confidence Finding"
        assert badge.metric_source == "p_value"
        assert badge.raw_value == 0.002
        assert badge["level"] == "high"
        assert badge.get("title") == "High Confidence Finding"

    def test_confidence_badge_auto_populate_from_badge_string(self) -> None:
        badge = ConfidenceBadge.model_validate({
            "level": "high",
            "badge": "🟢 High Forecast Reliability",
        })
        assert badge.icon == "🟢"
        assert "High Forecast Reliability" in badge.title
        assert badge.level == "high"

    def test_confidence_badge_level_alias_normalization(self) -> None:
        badge = ConfidenceBadge.model_validate({
            "level": "uncharted_territory",
            "icon": "🔴",
            "title": "Uncharted Territory",
        })
        assert badge.level == "uncharted"

    def test_followup_chip_model_instantiation(self) -> None:
        chip = FollowUpChip(
            id="chip_anomaly_group",
            label="[🔍 Show me which customer group caused this]",
            prompt="Identify which subgroup caused the drop in revenue.",
            action_type="drilldown",
        )
        assert chip.id == "chip_anomaly_group"
        assert chip.action_type == "drilldown"
        assert chip["label"] == "[🔍 Show me which customer group caused this]"
        assert chip.get("action_type") == "drilldown"

    def test_execution_result_schema_extensions(self) -> None:
        res = ExecutionResult(success=True)
        assert hasattr(res, "confidence_badges")
        assert res.confidence_badges == []
        assert hasattr(res, "follow_up_chips")
        assert res.follow_up_chips == []
        assert hasattr(res, "diagnostic_summary")
        assert res.diagnostic_summary is None


class TestJargonTranslatorConfidenceBadges:
    """Tests statistical metric translation into ConfidenceBadges."""

    def test_p_value_high_confidence(self) -> None:
        badge = JargonTranslator.get_confidence_badge(p_value=0.002, sample_size=100)
        assert badge["level"] == "high"
        assert badge["icon"] == "🟢"
        assert "High Confidence Finding" in badge["title"]

    def test_p_value_exact_edges(self) -> None:
        # p = 0.0099 (< 0.01) -> high
        b_high = JargonTranslator.get_confidence_badge(p_value=0.0099, sample_size=50)
        assert b_high["level"] == "high"

        # p = 0.0101 (>= 0.01) -> moderate
        b_mod = JargonTranslator.get_confidence_badge(p_value=0.0101, sample_size=50)
        assert b_mod["level"] == "moderate"

    def test_sample_size_small_overrides_p_value(self) -> None:
        # N = 14 (< 15) must trigger warning even if p = 0.001
        badge = JargonTranslator.get_confidence_badge(p_value=0.001, sample_size=14)
        assert badge["level"] == "warning"
        assert badge["icon"] == "🟡"
        assert "Low Sample Warning" in badge["title"]

    def test_p_value_warning_threshold(self) -> None:
        # p >= 0.05 -> warning
        badge = JargonTranslator.get_confidence_badge(p_value=0.08, sample_size=50)
        assert badge["level"] == "warning"
        assert badge["icon"] == "🟡"

    def test_r_squared_thresholds(self) -> None:
        # R^2 = 0.88 -> high
        b_high = JargonTranslator.get_confidence_badge(r_squared=0.88, is_ood=False)
        assert b_high["level"] == "high"
        assert b_high["icon"] == "🟢"

        # R^2 = 0.801 -> high
        b_edge_high = JargonTranslator.get_confidence_badge(r_squared=0.801)
        assert b_edge_high["level"] == "high"

        # R^2 = 0.799 -> moderate
        b_edge_mod = JargonTranslator.get_confidence_badge(r_squared=0.799)
        assert b_edge_mod["level"] == "moderate"
        assert b_edge_mod["icon"] == "🟡"

        # R^2 = 0.35 -> uncharted / low
        b_low = JargonTranslator.get_confidence_badge(r_squared=0.35)
        assert b_low["level"] == "uncharted"
        assert b_low["icon"] == "🔴"

    def test_out_of_distribution_and_mahalanobis(self) -> None:
        # is_ood = True overrides any model fit
        b_ood = JargonTranslator.get_confidence_badge(r_squared=0.95, is_ood=True)
        assert b_ood["level"] == "uncharted"
        assert b_ood["icon"] == "🔴"

        # Mahalanobis distance > critical threshold
        b_dm = JargonTranslator.get_confidence_badge(mahalanobis_dist=12.5, critical_threshold=3.0)
        assert b_dm["level"] == "uncharted"
        assert b_dm["icon"] == "🔴"

    def test_kurtosis_fat_tail_warning(self) -> None:
        # Kurtosis > 3.0 -> warning
        b_kurt_high = JargonTranslator.get_confidence_badge(kurtosis=4.5)
        assert b_kurt_high["level"] == "warning"
        assert "High Volatility" in b_kurt_high["title"]

        # Kurtosis <= 3.0 -> normal
        b_kurt_norm = JargonTranslator.get_confidence_badge(kurtosis=1.8)
        assert b_kurt_norm["level"] == "high"
        assert "Normal Volatility" in b_kurt_norm["title"]

    def test_heteroskedasticity_warning(self) -> None:
        # Breusch-Pagan p < 0.05 -> expanding uncertainty
        b_het = JargonTranslator.get_confidence_badge(heteroskedasticity_p=0.01)
        assert b_het["level"] == "warning"
        assert "Uncertainty Expands" in b_het["title"]

        # Breusch-Pagan p >= 0.05 -> uniform uncertainty
        b_homo = JargonTranslator.get_confidence_badge(heteroskedasticity_p=0.25)
        assert b_homo["level"] == "high"
        assert "Uniform Uncertainty" in b_homo["title"]

    def test_positional_arguments_compatibility(self) -> None:
        b_pos_p = JargonTranslator.get_confidence_badge("p_value", 0.002, 100)
        assert b_pos_p["level"] == "high"

        b_pos_r2 = JargonTranslator.get_confidence_badge("r_squared", 0.85, 100)
        assert b_pos_r2["level"] == "high"

        b_pos_dm = JargonTranslator.get_confidence_badge("mahalanobis", 15.0, 100, is_ood=True)
        assert b_pos_dm["level"] == "uncharted"


class TestJargonGlossaryAndSanitization:
    """Tests plain-English vocabulary and formula stripping."""

    def test_glossary_dictionary_completeness(self) -> None:
        glossary = JargonTranslator.get_glossary()
        assert len(glossary) >= 22
        assert "p-value" in glossary
        assert "r-squared" in glossary
        assert "mahalanobis distance" in glossary
        assert "kurtosis" in glossary
        assert "heteroskedasticity" in glossary
        assert "out-of-distribution" in glossary
        assert "oaxaca-blinder" in glossary
        assert "pelt" in glossary
        assert "lead-lag" in glossary
        assert "ridge regression" in glossary
        assert "counterfactual" in glossary

    def test_explain_term(self) -> None:
        exp = JargonTranslator.explain_term("p-value")
        assert exp is not None
        assert "Statistical reliability score" in exp

        exp_upper = JargonTranslator.explain_term("KURTOSIS")
        assert exp_upper is not None
        assert "outlier risks" in exp_upper

    def test_extract_terms(self) -> None:
        text = "We ran Oaxaca-Blinder decomposition, detected a PELT changepoint, and checked Mahalanobis distance."
        found = JargonTranslator.extract_terms(text)
        assert "oaxaca-blinder" in found
        assert "pelt" in found
        assert "changepoint" in found
        assert "mahalanobis" in found

    def test_translate_jargon(self) -> None:
        raw_text = "The regression model achieved strong r-squared with low p-value."
        translated = JargonTranslator.translate_jargon(raw_text)
        assert "forecast reliability" in translated
        assert "statistical reliability" in translated
        assert "Plain-English Guide" in translated

    def test_sanitize_plain_english_formulas(self) -> None:
        raw_title = "Revenue Drop Analysis (R²=0.88, p < 0.01)"
        cleaned = JargonTranslator.sanitize_plain_english(raw_title)
        assert "R²=0.88" not in cleaned
        assert "p < 0.01" not in cleaned
        assert "88% variance explained" in cleaned
        assert "statistically reliable" in cleaned

        raw_dm = "Cluster Drift (D_M = 15.2)"
        cleaned_dm = JargonTranslator.sanitize_plain_english(raw_dm)
        assert "D_M = 15.2" not in cleaned_dm


class TestThreeLayerVisualRule:
    """Tests enforcement of the 3-Layer Visual Hierarchy rule on ECharts options."""

    def test_enforce_three_layer_rule_basic(self) -> None:
        raw_option = {
            "series": [{"type": "bar", "data": [10, 50, 20]}]
        }
        styled = JargonTranslator.enforce_three_layer_rule(
            raw_option,
            baseline_val=20.0,
            title="Revenue Comparison (R²=0.90)",
            subtitle="Comparing against baseline (p < 0.01)",
        )
        # Layer 3: Title sanitized
        assert "R²=0.90" not in styled["title"]["text"]
        assert "90% variance explained" in styled["title"]["text"]
        assert "p < 0.01" not in styled["title"]["subtext"]

        # Layer 1: Context Layer markLine
        series_0 = styled["series"][0]
        assert "markLine" in series_0
        assert series_0["markLine"]["lineStyle"]["color"] == COLOR_DASHED_LINE

        # Layer 2: Spotlight Layer colors
        data = series_0["data"]
        colors = [d["itemStyle"]["color"] for d in data if isinstance(d, dict) and "itemStyle" in d]
        assert COLOR_CORAL_RED in colors
        assert COLOR_MUTED_SLATE in colors

    def test_enforce_three_layer_rule_horizontal_bar(self) -> None:
        raw_option = {
            "yAxis": {"type": "category", "data": ["East", "West", "North"]},
            "xAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [100, 25, 80]}],
        }
        styled = JargonTranslator.enforce_three_layer_rule(raw_option, baseline_val=70.0)
        mark_data = styled["series"][0]["markLine"]["data"]
        # In horizontal charts, markLine targets xAxis
        assert "xAxis" in mark_data[0]
        assert mark_data[0]["xAxis"] == 70.0

    def test_enforce_three_layer_rule_none_baseline_infer_mean(self) -> None:
        raw_option = {
            "series": [{"type": "bar", "data": [10, 20, 30]}]
        }
        styled = JargonTranslator.enforce_three_layer_rule(raw_option, baseline_val=None)
        assert "markLine" in styled["series"][0]
        mark_data = styled["series"][0]["markLine"]["data"]
        # Inferred baseline mean = 20.0
        assert mark_data[0]["yAxis"] == 20.0

    def test_enforce_three_layer_rule_preserves_custom_series_options(self) -> None:
        raw_option = {
            "tooltip": {"trigger": "item"},
            "animation": False,
            "series": [
                {
                    "type": "line",
                    "data": [1, 2, 3],
                    "smooth": True,
                    "symbolSize": 8,
                }
            ],
        }
        styled = JargonTranslator.enforce_three_layer_rule(raw_option, baseline_val=2.0, title="Headline")
        assert styled["tooltip"]["trigger"] == "item"
        assert styled["animation"] is False
        assert styled["series"][0]["smooth"] is True
        assert styled["series"][0]["symbolSize"] == 8


class TestFollowUpChipsAndEnrichment:
    """Tests contextual follow-up chips and execution result enrichment."""

    def test_generate_followup_chips_mandatory_labels(self) -> None:
        chips = JargonTranslator.generate_followup_chips(
            context_type="anomaly",
            findings={"metric": "Revenue"},
            user_query="Why did revenue drop this quarter?",
        )
        labels = [c.label for c in chips]
        assert "[🔍 Show me which customer group caused this]" in labels
        assert "[🎛️ Simulate how to recover this drop]" in labels
        assert "[🎯 3 recipes to fix top red bar]" in labels

    def test_enrich_execution_result(self) -> None:
        exec_res = ExecutionResult(
            success=True,
            plan="Analyze revenue drop",
            explanation="Calculated metrics",
            code="result = df.mean()",
            stdout="Analysis output: p_value = 0.003, sample_size = 120, r_squared = 0.85",
            chart=ChartSpec(
                title="Revenue Analysis (R²=0.85)",
                description="Raw chart (p < 0.01)",
                option={"series": [{"type": "bar", "data": [10, 40]}]},
            ),
        )
        enriched = JargonTranslator.enrich_execution_result(exec_res, user_query="Why did revenue drop?")

        # Badges attached
        assert len(enriched.confidence_badges) >= 1
        top_badge = enriched.confidence_badges[0]
        assert top_badge.level == "high"
        assert top_badge.icon == "🟢"

        # Chips attached
        assert len(enriched.follow_up_chips) >= 3
        labels = [c.label for c in enriched.follow_up_chips]
        assert "[🔍 Show me which customer group caused this]" in labels
        assert "[🎛️ Simulate how to recover this drop]" in labels
        assert "[🎯 3 recipes to fix top red bar]" in labels

        # 3-layer rule applied to chart
        assert enriched.chart is not None
        assert "R²=0.85" not in enriched.chart.title
        assert "p < 0.01" not in (enriched.chart.description or "")
        assert "markLine" in enriched.chart.option["series"][0]

        # Diagnostic summary populated
        assert enriched.diagnostic_summary is not None
        assert enriched.diagnostic_summary.get("p_value") == 0.003
        assert enriched.diagnostic_summary.get("sample_size") == 120
        assert enriched.diagnostic_summary.get("r_squared") == 0.85


class TestMilestone2RegressionGuards:
    """Regression guards verifying fixes for Challenger M2 adversarial vulnerabilities."""

    def test_enforce_three_layer_rule_series_data_none_no_crash(self) -> None:
        """Requirement 1.1: enforce_three_layer_rule does not crash when series data is None."""
        option = {"series": [{"type": "bar", "data": None}]}
        styled = JargonTranslator.enforce_three_layer_rule(option)
        assert isinstance(styled, dict), "Result must be a dictionary"
        assert "title" in styled, "Styled option must include Layer 3 title"
        assert styled["title"]["text"] == "Diagnostic Analysis"
        assert "series" in styled
        assert len(styled["series"]) >= 1
        assert styled["series"][0]["type"] == "bar"

    def test_enforce_three_layer_rule_malformed_option_and_series_safe_fallback(self) -> None:
        """Requirement 1.2: Safe fallback and no crash when option is None, or series contains None or string elements."""
        # 1. option is None
        styled_none = JargonTranslator.enforce_three_layer_rule(None)
        assert isinstance(styled_none, dict)
        assert styled_none["title"]["text"] == "Diagnostic Analysis"
        assert len(styled_none["series"]) >= 1
        assert styled_none["series"][0]["type"] == "bar"

        # 2. series contains [None]
        styled_none_elem = JargonTranslator.enforce_three_layer_rule({"series": [None]})  # type: ignore[list-item]
        assert isinstance(styled_none_elem, dict)
        assert len(styled_none_elem["series"]) >= 1
        assert isinstance(styled_none_elem["series"][0], dict)
        assert styled_none_elem["series"][0]["type"] == "bar"

        # 3. series contains string elements ["str"]
        styled_str_elem = JargonTranslator.enforce_three_layer_rule({"series": ["str"]})  # type: ignore[list-item]
        assert isinstance(styled_str_elem, dict)
        assert len(styled_str_elem["series"]) >= 1
        assert isinstance(styled_str_elem["series"][0], dict)
        assert styled_str_elem["series"][0]["type"] == "bar"

    def test_enforce_three_layer_rule_scatter_preserves_2d_coordinates(self) -> None:
        """Requirement 1.3: Scatter series with 2D coordinate lists [[x, y], ...] preserves coordinate vectors."""
        option = {
            "xAxis": {"type": "value"},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "type": "scatter",
                    "data": [[10.0, 20.0], [30.0, 40.0]],
                }
            ],
        }
        styled = JargonTranslator.enforce_three_layer_rule(option)
        assert "series" in styled
        series_0 = styled["series"][0]
        assert series_0["type"] == "scatter"
        data = series_0["data"]
        assert len(data) == 2, f"Expected 2 data points, got {len(data)}"

        # Validate coordinate pair preservation
        expected_coords = [[10.0, 20.0], [30.0, 40.0]]
        for idx, expected in enumerate(expected_coords):
            item = data[idx]
            coord = item["value"] if isinstance(item, dict) else item
            assert coord == expected, f"Coordinate pair at index {idx} corrupted! Expected {expected}, got {coord}"

        # Validate Layer 2 Spotlight styling
        item_styles = [d.get("itemStyle", {}) for d in data if isinstance(d, dict)]
        colors = [s.get("color") for s in item_styles if "color" in s]
        assert COLOR_CORAL_RED in colors, "Culprit coordinate must be colored coral red"
        assert COLOR_MUTED_SLATE in colors, "Context coordinate must be colored muted slate"

    def test_enforce_three_layer_rule_title_none_defaults_safely(self) -> None:
        """Requirement 1.4: title: None emits default title and never literal string 'None'."""
        option = {
            "title": None,
            "series": [{"type": "bar", "data": [10, 20]}],
        }
        styled = JargonTranslator.enforce_three_layer_rule(option)
        assert "title" in styled
        assert isinstance(styled["title"], dict)
        title_text = styled["title"].get("text")
        assert title_text != "None", "Title text was emitted as literal string 'None'!"
        assert title_text == "Diagnostic Analysis"
        assert styled["title"].get("subtext") != "None"

    def test_confidence_badge_invalid_and_out_of_bounds_p_values(self) -> None:
        """Requirement 1.5: p = -0.05, p = NaN, and p = 1.5 are classified as warning, never high or moderate."""
        test_cases = [
            (-0.05, "Negative p-value"),
            (float("nan"), "NaN p-value"),
            (1.5, "Out-of-bounds p-value > 1.0"),
        ]
        for p_val, desc in test_cases:
            badge = JargonTranslator.get_confidence_badge(p_value=p_val, sample_size=50)
            assert badge["level"] == "warning", (
                f"{desc} (p={p_val}) was misclassified as level='{badge['level']}'! "
                f"Expected 'warning', got title='{badge.get('title')}'"
            )
            assert badge["icon"] == "🟡", (
                f"{desc} (p={p_val}) expected icon '🟡', got '{badge.get('icon')}'"
            )
            assert badge["level"] not in ("high", "moderate"), (
                f"{desc} (p={p_val}) must never be classified as high or moderate confidence!"
            )
            # Verify Pydantic schema compliance
            validated = ConfidenceBadge.model_validate(badge)
            assert validated.level == "warning"

    def test_translation_null_safety(self) -> None:
        """Requirement 1.6: translate_jargon(None) and explain_term(None) return safely without AttributeError."""
        # 1. translate_jargon(None)
        res_trans = JargonTranslator.translate_jargon(None)
        assert res_trans in ("", None), f"Expected empty string or None, got {res_trans!r}"

        # 2. explain_term(None)
        res_exp = JargonTranslator.explain_term(None)
        assert res_exp is None, f"Expected None, got {res_exp!r}"

        # 3. extract_terms(None)
        res_extract = JargonTranslator.extract_terms(None)
        assert res_extract == {}, f"Expected empty dict, got {res_extract!r}"

        # 4. sanitize_plain_english(None)
        res_sanitize = JargonTranslator.sanitize_plain_english(None)
        assert res_sanitize == "", f"Expected empty string, got {res_sanitize!r}"
