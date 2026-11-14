"""Deterministic Jargon-to-Visual Translator and 3-Layer Visual Hierarchy Enforcer.

Converts raw statistical metrics into human-friendly confidence badges,
annotates technical terms with plain-English explanations, enforces semantic
chart styling according to the 3-Layer Chart Rule, and emits contextual
follow-up action chips.
"""

from copy import deepcopy
import math
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import numpy as np
import pandas as pd

from backend.models.chat import ConfidenceBadge, ExecutionResult, FollowUpChip

# Hoisted Semantic Color Palette
COLOR_MUTED_SLATE = "#94a3b8"       # Historical baseline / normal context
COLOR_CORAL_RED = "#ef4444"         # Anomalies / negative drivers / culprits / OOD
COLOR_EMERALD_GREEN = "#10b981"     # Positive drivers / healthy targets / high confidence
COLOR_ELECTRIC_BLUE = "#3b82f6"     # Simulation "what-if" / current period pillar
COLOR_CAUTION_AMBER = "#f59e0b"     # Caution / low sample / stretch scenario
COLOR_DASHED_LINE = "#64748b"       # Reference line for baseline normal

# Hoisted Statistical Threshold Constants
P_VALUE_HIGH_THRESHOLD = 0.01
P_VALUE_WARNING_THRESHOLD = 0.05
SAMPLE_SIZE_HIGH_THRESHOLD = 30
SAMPLE_SIZE_MIN_THRESHOLD = 15
R2_HIGH_THRESHOLD = 0.80
R2_LOW_THRESHOLD = 0.50
KURTOSIS_HIGH_THRESHOLD = 3.0
HETEROSKEDASTICITY_P_THRESHOLD = 0.05
DEFAULT_MAHALANOBIS_CRITICAL = 3.0

# 22+ Technical Terms Dictionary
JARGON_TOOLTIP_DICTIONARY: Dict[str, str] = {
    "p-value": "Statistical reliability score (lower means less likely to be a random coincidence; p < 0.01 indicates strong confidence).",
    "p_value": "Statistical reliability score (lower means less likely to be a random coincidence).",
    "r-squared": "Percentage of historical variation explained by the model (higher means more reliable projections).",
    "r2": "Percentage of historical variation explained by the model.",
    "mahalanobis distance": "Multi-variable distance measuring whether multiple settings make sense together in historical context.",
    "mahalanobis": "Multi-variable distance checking whether a combination of slider settings has ever operated together historically.",
    "kurtosis": "Indicator of sudden extreme spikes and fat-tailed outlier risks compared to standard bell curves.",
    "heteroskedasticity": "Changing uncertainty where prediction error spreads wider as volume increases.",
    "out-of-distribution": "Settings or data points operating outside any previously observed real-world experience.",
    "ood": "Out-of-Distribution: Operating in uncharted territory beyond historical operating ranges.",
    "oaxaca-blinder": "Decomposition technique isolating exact positive and negative drivers of a period-over-period metric shift.",
    "pelt": "Pruned Exact Linear Time algorithm detecting the exact timestamp where a metric structurally changed.",
    "lead-lag": "Time delay analysis identifying which metric moved first (root cause) and which followed later.",
    "changepoint": "The critical timestamp where a metric deviated from its established baseline pattern.",
    "ridge regression": "A stabilized estimation model that prevents erratic swings when multiple levers correlate with each other.",
    "monte carlo": "Simulating thousands of potential futures to measure realistic outcome ranges rather than false single-point certainty.",
    "counterfactual": "Reverse simulation finding the practical adjustments required to reach a desired target goal.",
    "standard deviation": "The typical spread or fluctuation of numbers around their historical average.",
    "variance": "The mathematical measurement of how widely dispersed observations are.",
    "percentile": "Ranking position showing what percentage of historical data points fall below this value.",
    "z-score": "The number of standard deviations a specific observation lies away from the historical average.",
    "welch's t-test": "Statistical comparison test determining whether two groups have meaningfully different averages despite unequal sizes.",
    "breusch-pagan": "Statistical test assessing whether prediction uncertainty expands at different scale volumes.",
    "covariance": "Measurement of how two variables fluctuate together over time.",
    "autocorrelation": "Correlation of a metric with its own previous values over time.",
    "homoskedasticity": "Constant prediction error spread across all operating ranges.",
}


class JargonTranslator:
    """Primary translation service for statistical jargon, confidence badges,

    follow-up action chips, and 3-layer ECharts visual grammar.
    """

    @staticmethod
    def sanitize_plain_english(text: Optional[str]) -> str:
        """Removes raw mathematical formulas, LaTeX, and technical tokens from display text."""
        if not text:
            return ""

        # Replace R^2 / R² / R2 formulas
        def _replace_r2(m: re.Match[str]) -> str:
            val = float(m.group(1))
            pct = round(val * 100)
            return f"{pct}% variance explained"

        cleaned = re.sub(r"\(?[Rr][\^²2]?\s*=\s*([0-9.]+)\)?", _replace_r2, text)

        # Replace p-values
        cleaned = re.sub(r"\(?p\s*<\s*0\.0[0-9]+\)?", "statistically reliable", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\(?p\s*=\s*[0-9.]+\)?", "statistically tested", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"p-value\s*=\s*[0-9.]+", "significance confirmed", cleaned, flags=re.IGNORECASE)

        # Replace Mahalanobis distance
        cleaned = re.sub(r"\(?D_M\s*=\s*[0-9.]+\)?", "operating distance", cleaned)
        cleaned = re.sub(r"Mahalanobis\s*(?:distance)?\s*=\s*[0-9.]+", "boundary distance", cleaned, flags=re.IGNORECASE)

        # Clean stray empty parens or double spaces
        cleaned = re.sub(r"\(\s*\)", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def get_confidence_badge(
        metric_name: Optional[str] = None,
        value: Optional[float] = None,
        sample_size: Optional[int] = None,
        is_ood: bool = False,
        p_value: Optional[float] = None,
        r_squared: Optional[float] = None,
        mahalanobis_dist: Optional[float] = None,
        critical_threshold: Optional[float] = None,
        kurtosis: Optional[float] = None,
        heteroskedasticity_p: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Translates statistical metrics into a standardized ConfidenceBadge dictionary.

        Supports keyword reflection (p_value, sample_size, r_squared, is_ood)
        and positional arguments.
        """
        # Resolve positional metric inputs
        m_lower = str(metric_name).lower() if metric_name is not None else ""
        eff_p = p_value if p_value is not None else (value if m_lower in ["p_value", "p_val", "pvalue", "p"] else None)
        eff_n = sample_size
        eff_r2 = r_squared if r_squared is not None else (value if m_lower in ["r_squared", "r2", "r_2"] else None)
        eff_dm = mahalanobis_dist if mahalanobis_dist is not None else (value if m_lower in ["mahalanobis", "mahalanobis_dist", "d_m"] else None)
        eff_kurt = kurtosis if kurtosis is not None else (value if m_lower in ["kurtosis"] else None)
        eff_het = heteroskedasticity_p if heteroskedasticity_p is not None else (value if m_lower in ["heteroskedasticity", "breusch_pagan", "bp_p"] else None)

        # 1. Out-of-Distribution (OOD) or Mahalanobis Distance Check
        crit = critical_threshold or DEFAULT_MAHALANOBIS_CRITICAL
        if is_ood or (eff_dm is not None and eff_dm > crit):
            return {
                "level": "uncharted",
                "icon": "🔴",
                "badge": "🔴 Uncharted Territory / Low Reliability",
                "title": "Uncharted Territory",
                "subtitle": "This specific combination of settings has never been operated together.",
                "metric_source": "ood_detector" if is_ood else "mahalanobis_distance",
                "raw_value": float(eff_dm if eff_dm is not None else (value if value is not None else 1.0)),
                "tooltip": "Operating outside historical experience; projection is a rough estimate.",
            }

        # 2. Sample size precedence (N < 15 triggers warning even with small p-value)
        if eff_n is not None and eff_n < SAMPLE_SIZE_MIN_THRESHOLD:
            small_n = eff_n
            return {
                "level": "warning",
                "icon": "🟡",
                "badge": "🟡 Low Sample Warning",
                "title": "Low Sample Warning",
                "subtitle": f"Only {small_n} observations in this group — treat with caution.",
                "metric_source": "p_value" if eff_p is not None else "sample_size",
                "raw_value": float(eff_p if eff_p is not None else small_n),
                "tooltip": f"Only {small_n} observations — small sample sizes can produce misleading spikes.",
            }

        # 3. P-Value thresholds (Welch's t-test / Anomaly Spotlight)
        if eff_p is not None:
            raw_p = float(eff_p)
            p_n_obs: Optional[int] = eff_n
            n_str = str(p_n_obs) if p_n_obs is not None else "sample"

            # Check for undefined (NaN) p-value
            if math.isnan(raw_p):
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 Low Sample Warning",
                    "title": "Low Sample Warning",
                    "subtitle": f"Statistical significance is undefined (NaN) for {n_str} observations — cannot determine reliability.",
                    "metric_source": "p_value",
                    "raw_value": raw_p,
                    "tooltip": "Statistical significance is undefined (NaN) — cannot determine reliability.",
                }

            # Enforce valid probability domain [0.0, 1.0]
            if raw_p < 0.0 or raw_p > 1.0:
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 Low Sample Warning",
                    "title": "Low Sample Warning",
                    "subtitle": f"Invalid p-value ({raw_p}) for {n_str} observations — statistical test may be corrupt or invalid.",
                    "metric_source": "p_value",
                    "raw_value": raw_p,
                    "tooltip": "P-value must fall strictly within probability domain [0.0, 1.0].",
                }

            if raw_p >= P_VALUE_WARNING_THRESHOLD:
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 Low Sample Warning",
                    "title": "Low Sample Warning",
                    "subtitle": f"Based on {n_str} observations (p = {raw_p:.3f} >= 0.05) — treat with caution.",
                    "metric_source": "p_value",
                    "raw_value": raw_p,
                    "tooltip": "Observed variation could be due to random chance (p >= 0.05).",
                }
            if raw_p < P_VALUE_HIGH_THRESHOLD and (p_n_obs is None or p_n_obs >= SAMPLE_SIZE_HIGH_THRESHOLD):
                hist_str = str(p_n_obs) if p_n_obs is not None else "historical"
                return {
                    "level": "high",
                    "icon": "🟢",
                    "badge": "🟢 High Confidence Finding",
                    "title": "High Confidence Finding",
                    "subtitle": f"Based on {hist_str} observations — statistically reliable, not a random fluke.",
                    "metric_source": "p_value",
                    "raw_value": raw_p,
                    "tooltip": f"Based on {n_str} observations — statistically reliable (p < 0.01).",
                }
            # Moderate range: p < 0.05 with N >= 15
            return {
                "level": "moderate",
                "icon": "🟢",
                "badge": "🟢 Moderate Confidence Finding",
                "title": "Moderate Confidence Finding",
                "subtitle": f"Based on {n_str} observations (p = {raw_p:.3f} < 0.05).",
                "metric_source": "p_value",
                "raw_value": raw_p,
                "tooltip": "Moderate confidence finding; directionally indicative.",
            }

        # 4. Model Fit (R-Squared / Surrogate Model / Attribution Bridge)
        if eff_r2 is not None:
            raw_r2 = float(eff_r2)
            if raw_r2 < R2_LOW_THRESHOLD:
                return {
                    "level": "uncharted",
                    "icon": "🔴",
                    "badge": "🔴 Uncharted Territory / Low Reliability",
                    "title": "Low Forecast Reliability",
                    "subtitle": f"Model explains only {raw_r2 * 100:.0f}% of variance; projection is a rough estimate.",
                    "metric_source": "r_squared",
                    "raw_value": raw_r2,
                    "tooltip": "Weak historical relationship; treat projections with caution.",
                }
            if raw_r2 >= R2_HIGH_THRESHOLD:
                return {
                    "level": "high",
                    "icon": "🟢",
                    "badge": "🟢 High Forecast Reliability",
                    "title": "High Forecast Reliability",
                    "subtitle": f"Model explains {raw_r2 * 100:.0f}% of historical variance within proven operating range.",
                    "metric_source": "r_squared",
                    "raw_value": raw_r2,
                    "tooltip": "High forecast reliability; model captures over 80% of historical dynamics.",
                }
            return {
                "level": "moderate",
                "icon": "🟡",
                "badge": "🟡 Moderate Forecast Reliability",
                "title": "Moderate Forecast Reliability",
                "subtitle": f"Moderate correlation ({raw_r2 * 100:.0f}% variance explained); use as a directional estimate.",
                "metric_source": "r_squared",
                "raw_value": raw_r2,
                "tooltip": "Moderate forecast reliability; useful for directional guidance.",
            }

        # 5. Kurtosis (Volatility / Fat-Tails)
        if eff_kurt is not None:
            raw_kurt = float(eff_kurt)
            if raw_kurt > KURTOSIS_HIGH_THRESHOLD:
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 High Volatility / Outlier Risk",
                    "title": "High Volatility / Outlier Risk",
                    "subtitle": "Data exhibits sudden spikes more frequently than normal (fat-tailed distribution).",
                    "metric_source": "kurtosis",
                    "raw_value": raw_kurt,
                    "tooltip": "Data exhibits sudden spikes more frequently than normal.",
                }
            return {
                "level": "high",
                "icon": "🟢",
                "badge": "🟢 Normal Volatility",
                "title": "Normal Volatility",
                "subtitle": "Outlier frequencies fall within standard historical bounds.",
                "metric_source": "kurtosis",
                "raw_value": raw_kurt,
                "tooltip": "Standard distribution without excessive tail risk.",
            }

        # 6. Heteroskedasticity (Breusch-Pagan)
        if eff_het is not None:
            raw_het = float(eff_het)
            if raw_het < HETEROSKEDASTICITY_P_THRESHOLD:
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 Uncertainty Expands at Higher Volumes",
                    "title": "Uncertainty Expands at Higher Volumes",
                    "subtitle": "Prediction spread widens significantly as volume increases.",
                    "metric_source": "heteroskedasticity",
                    "raw_value": raw_het,
                    "tooltip": "Uncertainty is not constant; error bands expand at higher ranges.",
                }
            return {
                "level": "high",
                "icon": "🟢",
                "badge": "🟢 Uniform Uncertainty",
                "title": "Uniform Uncertainty",
                "subtitle": "Prediction spread remains consistent across all operating ranges.",
                "metric_source": "heteroskedasticity",
                "raw_value": raw_het,
                "tooltip": "Prediction uncertainty is constant across historical ranges.",
            }

        # 7. Sample size fallback
        if eff_n is not None:
            n_obs = eff_n
            if n_obs < SAMPLE_SIZE_MIN_THRESHOLD:
                return {
                    "level": "warning",
                    "icon": "🟡",
                    "badge": "🟡 Low Sample Warning",
                    "title": "Low Sample Warning",
                    "subtitle": f"Only {n_obs} observations in this group — treat with caution.",
                    "metric_source": "sample_size",
                    "raw_value": float(n_obs),
                    "tooltip": f"Only {n_obs} observations — treat with caution.",
                }
            return {
                "level": "high",
                "icon": "🟢",
                "badge": "🟢 Sufficient Sample Size",
                "title": "Sufficient Sample Size",
                "subtitle": f"Based on {n_obs} observations.",
                "metric_source": "sample_size",
                "raw_value": float(n_obs),
                "tooltip": "Sample size is adequate for reliable descriptive insights.",
            }

        # Neutral fallback
        return {
            "level": "moderate",
            "icon": "🟢",
            "badge": "🟢 Standard Confidence",
            "title": "Standard Confidence",
            "subtitle": "Evaluated with standard analytical assumptions.",
            "metric_source": metric_name or "general",
            "raw_value": float(value if value is not None else 1.0),
            "tooltip": "Standard confidence assessment.",
        }

    # Backward compatibility alias
    translate_confidence = get_confidence_badge

    @staticmethod
    def explain_term(term: Optional[str]) -> Optional[str]:
        """Returns the plain-English tooltip definition for a statistical term."""
        if not term or not term.strip():
            return None
        norm = term.strip().lower()
        return JARGON_TOOLTIP_DICTIONARY.get(norm)

    @classmethod
    def get_glossary(cls) -> Dict[str, str]:
        """Returns the full technical terms dictionary."""
        return dict(JARGON_TOOLTIP_DICTIONARY)

    @classmethod
    def extract_terms(cls, text: Optional[str]) -> Dict[str, str]:
        """Finds all technical terms present in the text and returns their plain-English definitions."""
        if not text:
            return {}
        found: Dict[str, str] = {}
        lower_text = text.lower()
        for term, explanation in JARGON_TOOLTIP_DICTIONARY.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, lower_text):
                found[term] = explanation
        return found

    @classmethod
    def translate_jargon(cls, text: Optional[str]) -> str:
        """Replaces technical terms with plain-English tooltips / explanations based on the 22-term dictionary."""
        if text is None:
            return ""
        detected = cls.extract_terms(text)
        if not detected:
            return text

        # Replace technical terms with plain-English business friendly equivalents
        result = text
        for term in detected:
            sub = "statistical reliability" if "p-value" in term or "p_value" in term else (
                "forecast reliability" if "r2" in term or "r-squared" in term else (
                    "boundary distance" if "mahalanobis" in term else (
                        "outlier volatility" if "kurtosis" in term else (
                            "structural change point" if "changepoint" in term or "pelt" in term else term
                        )
                    )
                )
            )
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            result = pattern.sub(sub, result)

        # Append plain-English tooltip glossary footnote
        items = [f"**{t.title()}**: {exp}" for t, exp in detected.items()]
        footnote = "\n\n💡 **Plain-English Guide**:\n- " + "\n- ".join(items)
        return result + footnote

    @classmethod
    def translate(
        cls,
        text: Optional[str],
        mode: Literal["annotate", "replace", "glossary"] = "annotate"
    ) -> str:
        """Converts or annotates text containing technical jargon into plain English."""
        if text is None:
            return ""
        detected = cls.extract_terms(text)
        if not detected:
            return text

        if mode == "glossary":
            lines = ["\n\n**Plain-English Guide**:"]
            for term, exp in detected.items():
                lines.append(f"- **{term.title()}**: {exp}")
            return text + "\n".join(lines)

        if mode == "annotate":
            items = [f"**{t.title()}** ({exp})" for t, exp in detected.items()]
            return f"{text}\n\n💡 *Plain-English Guide:* " + " • ".join(items)

        # mode == "replace"
        result = text
        for term in detected:
            sub = "statistical reliability" if "p-value" in term or "p_value" in term else (
                "forecast fit" if "r2" in term or "r-squared" in term else term
            )
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            result = pattern.sub(sub, result)
        return result

    @classmethod
    def enforce_three_layer_rule(
        cls,
        option: Optional[Dict[str, Any]] = None,
        baseline_val: Optional[float] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        culprit_indices: Optional[List[int]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Enforces the 3-Layer Visual Hierarchy rule on an Apache ECharts option tree:

        - Layer 1 (Context): Reference markLine / markArea indicating baseline normal.
        - Layer 2 (Spotlight): High-contrast coral red (#ef4444) for culprits, muted slate (#94a3b8) for context.
        - Layer 3 (Plain-English): Informative headline and subtitle stripped of formula jargon.
        Preserves custom series options, tooltips, and animations non-destructively.
        """
        if not isinstance(option, dict):
            styled: Dict[str, Any] = {}
        else:
            styled = deepcopy(option)

        # Ensure valid series list exists and contains only dicts
        raw_series = styled.get("series")
        if isinstance(raw_series, list):
            valid_series = [s for s in raw_series if isinstance(s, dict)]
        else:
            valid_series = []

        if not valid_series:
            valid_series = [{"type": "bar", "data": []}]

        styled["series"] = valid_series
        primary_series = styled["series"][0]

        # ----------------------------------------------------------------------
        # Layer 3: Plain-English Title & Subtitle (Sanitized)
        # ----------------------------------------------------------------------
        raw_title = styled.get("title")
        if isinstance(raw_title, dict):
            existing_title = dict(raw_title)
        elif isinstance(raw_title, str) and raw_title.strip() and raw_title.strip().lower() != "none":
            existing_title = {"text": raw_title.strip()}
        else:
            existing_title = {}

        if title is not None and str(title).strip().lower() != "none":
            raw_title_text = str(title)
        elif existing_title.get("text") is not None and str(existing_title.get("text")).strip().lower() != "none":
            raw_title_text = str(existing_title["text"])
        else:
            raw_title_text = "Diagnostic Analysis"

        if subtitle is not None and str(subtitle).strip().lower() != "none":
            raw_subtext = str(subtitle)
        elif existing_title.get("subtext") is not None and str(existing_title.get("subtext")).strip().lower() != "none":
            raw_subtext = str(existing_title["subtext"])
        elif subtitle == "" or existing_title.get("subtext") == "":
            raw_subtext = ""
        else:
            raw_subtext = "Baseline comparison"

        clean_title_text = cls.sanitize_plain_english(raw_title_text)
        if not clean_title_text or clean_title_text.strip().lower() == "none":
            clean_title_text = "Diagnostic Analysis"

        clean_subtext = cls.sanitize_plain_english(raw_subtext) if raw_subtext else ""
        if clean_subtext.strip().lower() == "none":
            clean_subtext = ""

        styled["title"] = {
            **existing_title,
            "text": clean_title_text,
            "subtext": clean_subtext,
            "left": existing_title.get("left", "left"),
            "textStyle": {
                "fontSize": 14,
                "fontWeight": 600,
                "color": "#0f172a",
                **existing_title.get("textStyle", {}),
            },
            "subtextStyle": {
                "fontSize": 11,
                "color": "#64748b",
                **existing_title.get("subtextStyle", {}),
            },
        }

        # ----------------------------------------------------------------------
        # Layer 1: Context Layer (markLine / markArea Reference)
        # ----------------------------------------------------------------------
        has_context_layer = any(
            isinstance(s, dict) and (("markLine" in s and s["markLine"]) or ("markArea" in s and s["markArea"]))
            for s in styled["series"]
        )

        effective_baseline = baseline_val

        # If baseline_val is None and no context layer exists, infer mean from data
        if effective_baseline is None and not has_context_layer:
            data_pts = primary_series.get("data") or []
            extracted_vals = []
            if isinstance(data_pts, list):
                for d in data_pts:
                    if isinstance(d, (int, float)):
                        extracted_vals.append(float(d))
                    elif isinstance(d, (list, tuple)) and d:
                        val_num = d[1] if len(d) > 1 else d[0]
                        if isinstance(val_num, (int, float)):
                            extracted_vals.append(float(val_num))
                    elif isinstance(d, dict) and "value" in d:
                        v = d["value"]
                        if isinstance(v, (int, float)):
                            extracted_vals.append(float(v))
                        elif isinstance(v, (list, tuple)) and v:
                            val_num = v[1] if len(v) > 1 else v[0]
                            if isinstance(val_num, (int, float)):
                                extracted_vals.append(float(val_num))
            if extracted_vals:
                effective_baseline = float(np.mean(extracted_vals))

        if not has_context_layer:
            # Determine orientation: horizontal bar charts have category yAxis
            is_horizontal = False
            y_axis = styled.get("yAxis")
            if isinstance(y_axis, dict) and y_axis.get("type") == "category":
                is_horizontal = True
            elif isinstance(y_axis, list) and y_axis and isinstance(y_axis[0], dict) and y_axis[0].get("type") == "category":
                is_horizontal = True

            if effective_baseline is not None:
                b_rounded = round(float(effective_baseline), 2)
                lbl = kwargs.get("baseline_label", f"Baseline: {b_rounded}")
                mark_entry: Dict[str, Any] = {"xAxis": b_rounded} if is_horizontal else {"yAxis": b_rounded}
                mark_entry["label"] = {
                    "formatter": lbl,
                    "position": "end",
                    "color": COLOR_DASHED_LINE,
                    "fontSize": 11,
                }
                primary_series["markLine"] = {
                    "silent": True,
                    "symbol": "none",
                    "lineStyle": {
                        "type": "dashed",
                        "color": COLOR_DASHED_LINE,
                        "width": 2,
                    },
                    "data": [mark_entry],
                }
            else:
                # Add default average reference line
                primary_series["markLine"] = {
                    "silent": True,
                    "symbol": "none",
                    "lineStyle": {
                        "type": "dashed",
                        "color": COLOR_DASHED_LINE,
                        "width": 2,
                    },
                    "data": [{"type": "average", "name": "Baseline Average"}],
                }

        # ----------------------------------------------------------------------
        # Layer 2: Spotlight Layer (Semantic Palette Enforcement)
        # ----------------------------------------------------------------------
        has_semantic_palette = False
        for s in styled["series"]:
            if not isinstance(s, dict):
                continue
            s_col = str(s.get("color", "")).lower()
            if COLOR_CORAL_RED.lower() in s_col or COLOR_MUTED_SLATE.lower() in s_col:
                has_semantic_palette = True
                break
            if "lineStyle" in s and isinstance(s["lineStyle"], dict):
                ls_c = str(s["lineStyle"].get("color", "")).lower()
                if COLOR_CORAL_RED.lower() in ls_c or COLOR_MUTED_SLATE.lower() in ls_c:
                    has_semantic_palette = True
                    break
            if "markLine" in s and isinstance(s["markLine"], dict):
                ml_c = str(s["markLine"].get("lineStyle", {}).get("color", "")).lower()
                if COLOR_CORAL_RED.lower() in ml_c or COLOR_MUTED_SLATE.lower() in ml_c:
                    has_semantic_palette = True
                    break
            for d in (s.get("data") or []):
                if isinstance(d, dict) and "itemStyle" in d:
                    dc = str(d["itemStyle"].get("color", "")).lower()
                    if COLOR_CORAL_RED.lower() in dc or COLOR_MUTED_SLATE.lower() in dc:
                        has_semantic_palette = True
                        break
            if has_semantic_palette:
                break

        # If series lacks spotlight styling, color the elements
        primary_data = primary_series.get("data")
        if not has_semantic_palette and isinstance(primary_data, list) and len(primary_data) > 0:
            vals: List[float] = []
            for item in primary_data:
                if isinstance(item, (int, float)):
                    vals.append(float(item))
                elif isinstance(item, (list, tuple)) and item:
                    val_num = item[1] if len(item) > 1 else item[0]
                    vals.append(float(val_num) if isinstance(val_num, (int, float)) else 0.0)
                elif isinstance(item, dict) and "value" in item:
                    iv = item["value"]
                    if isinstance(iv, (int, float)):
                        vals.append(float(iv))
                    elif isinstance(iv, (list, tuple)) and iv:
                        val_num = iv[1] if len(iv) > 1 else iv[0]
                        vals.append(float(val_num) if isinstance(val_num, (int, float)) else 0.0)
                    else:
                        vals.append(0.0)
                else:
                    vals.append(0.0)

            c_indices = set(culprit_indices) if culprit_indices is not None else set()
            if not c_indices and vals:
                # Choose point with maximum absolute divergence from baseline
                ref = effective_baseline if effective_baseline is not None else float(np.mean(vals))
                divergences = [abs(v - ref) for v in vals]
                max_idx = int(np.argmax(divergences))
                c_indices.add(max_idx)

            styled_data = []
            s_type = primary_series.get("type", "bar")
            is_bar = s_type == "bar"

            for idx, raw_item in enumerate(primary_data):
                val = vals[idx]
                color = COLOR_CORAL_RED if idx in c_indices else COLOR_MUTED_SLATE
                if isinstance(raw_item, dict):
                    item_copy = dict(raw_item)
                    item_style = dict(item_copy.get("itemStyle") or {})
                    if "color" not in item_style:
                        item_style["color"] = color
                        if is_bar:
                            item_style.setdefault("borderRadius", [4, 4, 0, 0])
                        item_copy["itemStyle"] = item_style
                    styled_data.append(item_copy)
                elif isinstance(raw_item, (list, tuple)):
                    styled_entry: Dict[str, Any] = {
                        "value": list(raw_item),
                        "itemStyle": {"color": color},
                    }
                    if is_bar:
                        styled_entry["itemStyle"]["borderRadius"] = [4, 4, 0, 0]
                    styled_data.append(styled_entry)
                else:
                    styled_entry = {
                        "value": val,
                        "itemStyle": {"color": color},
                    }
                    if is_bar:
                        styled_entry["itemStyle"]["borderRadius"] = [4, 4, 0, 0]
                    styled_data.append(styled_entry)
            primary_series["data"] = styled_data

        return styled

    # Backward compatibility alias
    enforce_3_layer_rule = enforce_three_layer_rule

    @classmethod
    def generate_followup_chips(
        cls,
        context_type: str = "anomaly",
        findings: Optional[Dict[str, Any]] = None,
        user_query: str = "",
        exec_result: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[FollowUpChip]:
        """Generates contextual next-step action chips for the chat UI."""
        findings = findings or {}
        metric = findings.get("metric") or findings.get("target_col") or "metric"
        chips: List[FollowUpChip] = []

        # Determine context signals from query or execution artifacts
        query_lower = user_query.lower()
        is_drop = any(w in query_lower for w in ["drop", "decline", "fell", "decrease", "loss", "down", "why did", "culprit", "anomaly", "abnormal"])
        has_culprit_bar = False
        if exec_result and getattr(exec_result, "chart", None) and exec_result.chart and exec_result.chart.option:
            opt = exec_result.chart.option
            for s in (opt.get("series") or []):
                if isinstance(s, dict):
                    for d in (s.get("data") or []):
                        if isinstance(d, dict) and COLOR_CORAL_RED.lower() in str(d.get("itemStyle", {}).get("color", "")).lower():
                            has_culprit_bar = True
                            break

        if context_type == "anomaly" or is_drop or has_culprit_bar:
            chips.extend([
                FollowUpChip(
                    id="chip_anomaly_group",
                    label="[🔍 Show me which customer group caused this]",
                    prompt=f"Identify which specific subgroup or customer segment caused the drop in {metric}.",
                    action_type="drilldown",
                ),
                FollowUpChip(
                    id="chip_anomaly_simulate",
                    label="[🎛️ Simulate how to recover this drop]",
                    prompt=f"Simulate what-if lever adjustments to recover the deficit in {metric}.",
                    action_type="simulate",
                ),
                FollowUpChip(
                    id="chip_anomaly_recipes",
                    label="[🎯 3 recipes to fix top red bar]",
                    prompt=f"Generate 3 counterfactual recipe cards to reverse the impact of the primary negative driver on {metric}.",
                    action_type="recipes",
                ),
            ])
        elif context_type == "attribution":
            chips.extend([
                FollowUpChip(
                    id="chip_attribution_recipes",
                    label="[🎯 3 recipes to fix top red bar]",
                    prompt=f"Generate 3 counterfactual recipe cards to reverse the impact of the primary negative driver on {metric}.",
                    action_type="recipes",
                ),
                FollowUpChip(
                    id="chip_attribution_drilldown",
                    label="[🔍 Drill deeper into top driver]",
                    prompt=f"Break down the primary negative driver of {metric} into granular sub-segments.",
                    action_type="drilldown",
                ),
                FollowUpChip(
                    id="chip_attribution_simulate",
                    label="[🎛️ Simulate how to recover this drop]",
                    prompt=f"Simulate recovering {metric} to its baseline level using controllable levers.",
                    action_type="simulate",
                ),
            ])
        elif context_type == "cascade":
            chips.extend([
                FollowUpChip(
                    id="chip_cascade_t0",
                    label="[⏱️ Zoom in on T=0 root cause]",
                    prompt="Analyze granular metric telemetry around T=0 to isolate the initial failure trigger.",
                    action_type="drilldown",
                ),
                FollowUpChip(
                    id="chip_cascade_simulate",
                    label="[🎛️ Simulate cascade prevention]",
                    prompt="Simulate buffer adjustments to prevent upstream bottlenecks from cascading downstream.",
                    action_type="simulate",
                ),
                FollowUpChip(
                    id="chip_cascade_recipes",
                    label="[🎯 3 recipes to fix top red bar]",
                    prompt="Generate 3 counterfactual recipes to prevent cascade failure.",
                    action_type="recipes",
                ),
            ])
        else:
            # General fallback chips
            chips.extend([
                FollowUpChip(
                    id="chip_generic_drilldown",
                    label="[🔍 Show me which customer group caused this]",
                    prompt=f"Isolate anomalous subgroups and key drivers impacting {metric}.",
                    action_type="drilldown",
                ),
                FollowUpChip(
                    id="chip_generic_simulate",
                    label="[🎛️ Simulate how to recover this drop]",
                    prompt=f"Open Scenario Studio to simulate adjusting controllable levers for {metric}.",
                    action_type="simulate",
                ),
                FollowUpChip(
                    id="chip_generic_recipes",
                    label="[🎯 3 recipes to fix top red bar]",
                    prompt=f"Generate 3 counterfactual recipe cards to optimize {metric}.",
                    action_type="recipes",
                ),
            ])

        return chips

    @classmethod
    def enrich_execution_result(
        cls,
        exec_result: ExecutionResult,
        user_query: str = "",
        df: Optional[pd.DataFrame] = None,
    ) -> ExecutionResult:
        """Enforces 3-layer rule on chart, extracts metrics, attaches confidence badges and chips."""
        # 1. Enforce 3-Layer Chart Rule if chart is present
        if exec_result.chart and exec_result.chart.option:
            exec_result.chart.option = cls.enforce_three_layer_rule(
                option=exec_result.chart.option,
                title=exec_result.chart.title,
                subtitle=exec_result.chart.description,
            )
            # Update chart title & description to plain English
            if "title" in exec_result.chart.option and isinstance(exec_result.chart.option["title"], dict):
                t_obj = exec_result.chart.option["title"]
                if t_obj.get("text"):
                    exec_result.chart.title = str(t_obj["text"])
                if t_obj.get("subtext"):
                    exec_result.chart.description = str(t_obj["subtext"])

        # 2. Extract metrics from stdout, table, or dataframe
        extracted_p: Optional[float] = None
        extracted_n: Optional[int] = None
        extracted_r2: Optional[float] = None
        extracted_dm: Optional[float] = None
        extracted_ood: bool = False
        extracted_kurt: Optional[float] = None
        extracted_het: Optional[float] = None

        if exec_result.stdout:
            stdout_text = exec_result.stdout

            p_match = re.search(r"(?:p[-_ ]?val(?:ue)?|p)\s*[:=]\s*([0-9.]+(?:e-?[0-9]+)?)", stdout_text, re.IGNORECASE)
            if p_match:
                try:
                    extracted_p = float(p_match.group(1))
                except ValueError:
                    pass

            n_match = re.search(r"(?:sample[-_ ]?size|sample|n|records|obs|observations)\s*[:=]\s*([0-9]+)", stdout_text, re.IGNORECASE)
            if n_match:
                try:
                    extracted_n = int(n_match.group(1))
                except ValueError:
                    pass

            r2_match = re.search(r"(?:r[-_ ]?squared|r2|r\^2)\s*[:=]\s*([0-9.]+)", stdout_text, re.IGNORECASE)
            if r2_match:
                try:
                    extracted_r2 = float(r2_match.group(1))
                except ValueError:
                    pass

            dm_match = re.search(r"(?:mahalanobis(?:[-_ ]?dist(?:ance)?)?|d_m)\s*[:=]\s*([0-9.]+)", stdout_text, re.IGNORECASE)
            if dm_match:
                try:
                    extracted_dm = float(dm_match.group(1))
                except ValueError:
                    pass

            ood_match = re.search(r"(?:is[-_ ]?ood|ood)\s*[:=]\s*(true|false)", stdout_text, re.IGNORECASE)
            if ood_match:
                extracted_ood = ood_match.group(1).lower() == "true"

            kurt_match = re.search(r"(?:kurtosis)\s*[:=]\s*([0-9.]+)", stdout_text, re.IGNORECASE)
            if kurt_match:
                try:
                    extracted_kurt = float(kurt_match.group(1))
                except ValueError:
                    pass

            het_match = re.search(r"(?:breusch[-_ ]?pagan|heteroskedasticity|bp[-_ ]?p)\s*[:=]\s*([0-9.]+)", stdout_text, re.IGNORECASE)
            if het_match:
                try:
                    extracted_het = float(het_match.group(1))
                except ValueError:
                    pass

        # Fallback sample size from table or dataframe
        if extracted_n is None:
            if exec_result.table and exec_result.table.total_rows > 0:
                extracted_n = exec_result.table.total_rows
            elif df is not None and len(df) > 0:
                extracted_n = len(df)

        badge_dict = cls.get_confidence_badge(
            sample_size=extracted_n,
            is_ood=extracted_ood,
            p_value=extracted_p,
            r_squared=extracted_r2,
            mahalanobis_dist=extracted_dm,
            kurtosis=extracted_kurt,
            heteroskedasticity_p=extracted_het,
        )

        badge_model = ConfidenceBadge.model_validate(badge_dict)
        exec_result.confidence_badges = [badge_model]

        # 3. Generate FollowUpChips
        chips = cls.generate_followup_chips(
            context_type="anomaly" if extracted_ood or (extracted_p is not None and extracted_p < 0.05) else "general",
            findings={"metric": "metric", "p_value": extracted_p, "sample_size": extracted_n},
            user_query=user_query,
            exec_result=exec_result,
        )
        exec_result.follow_up_chips = chips

        # 4. Attach diagnostic summary if metrics were found
        diag: Dict[str, Any] = {}
        if extracted_p is not None:
            diag["p_value"] = extracted_p
        if extracted_n is not None:
            diag["sample_size"] = extracted_n
        if extracted_r2 is not None:
            diag["r_squared"] = extracted_r2
        if extracted_dm is not None:
            diag["mahalanobis_dist"] = extracted_dm
        if extracted_ood:
            diag["is_ood"] = True
        if extracted_kurt is not None:
            diag["kurtosis"] = extracted_kurt
        if extracted_het is not None:
            diag["heteroskedasticity_p"] = extracted_het

        if diag:
            exec_result.diagnostic_summary = diag

        return exec_result
