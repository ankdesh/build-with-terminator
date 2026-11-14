"""Pydantic schemas and dataclasses for What-If & Scenario Studio (Milestone 3).

Defines data contracts for feature role inference, closed-form Ridge surrogate models,
real-time slider simulation, counterfactual recipe cards, and
Monte Carlo weather forecast uncertainty distributions.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class LeverRoleInfo(BaseModel):
    """Metadata, statistics, and operating zones for an individual controllable lever."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    column: str
    min_val: float
    max_val: float
    mean_val: float
    std_val: float
    median_val: float
    p1: float
    p5: float
    p95: float
    p99: float
    step: float
    default_val: float

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class FeatureRoles(BaseModel):
    """Classification of dataset columns into levers, immutable context, and target."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    levers: List[str] = Field(
        ...,
        description="Controllable numeric features eligible for interactive user sliders",
    )
    locked_context: List[str] = Field(
        ...,
        description="Immutable context columns (IDs, timestamps, categoricals) marked with 🔒",
    )
    target_col: str = Field(
        ...,
        description="Primary KPI outcome metric being modeled or optimized",
        alias="target_column",
    )
    lever_bounds: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Statistical bounds per lever: min, max, mean, step, p1, p5, p95, p99",
    )
    baseline_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Historical baseline/median value per lever for slider diamond marker ◆",
    )
    baseline_target: float = Field(
        default=0.0,
        description="Historical baseline/mean value of target KPI",
    )

    @property
    def lever_cols(self) -> List[str]:
        """Backward-compatible alias for levers."""
        return self.levers

    @property
    def immutable_cols(self) -> List[str]:
        """Backward-compatible alias for locked_context."""
        return self.locked_context

    @property
    def lever_specs(self) -> Dict[str, Dict[str, float]]:
        """Backward-compatible alias for lever_bounds."""
        return self.lever_bounds

    def __getitem__(self, item: str) -> Any:
        if item == "target_column":
            return self.target_col
        if item == "lever_cols":
            return self.levers
        if item == "immutable_cols":
            return self.locked_context
        if item == "lever_specs":
            return self.lever_bounds
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "target_column":
            return self.target_col
        if item == "lever_cols":
            return self.levers
        if item == "immutable_cols":
            return self.locked_context
        if item == "lever_specs":
            return self.lever_bounds
        return getattr(self, item, default)


class SurrogateModel(BaseModel):
    """In-memory closed-form Ridge regression surrogate and covariance matrix."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    feature_names: List[str] = Field(
        ...,
        description="Ordered list of controllable lever names used during training",
    )
    coefficients: List[float] = Field(
        ...,
        description="Ridge regression weight coefficients beta_hat",
    )
    intercept: float = Field(
        ...,
        description="Linear intercept term beta_0",
    )
    r_squared: float = Field(
        ...,
        description="Coefficient of determination R^2 in [0.0, 1.0]",
    )
    cov_matrix_inv: List[List[float]] = Field(
        ...,
        description="Inverted regularized covariance matrix (Sigma + eps*I)^-1 for Mahalanobis OOD calculation",
    )
    mean_vector: List[float] = Field(
        ...,
        description="Historical mean vector mu across controllable levers",
    )
    chi2_critical_99: float = Field(
        ...,
        description="99% critical chi-squared threshold chi^2_p(0.99) for p = len(feature_names)",
    )
    residual_std: float = Field(
        ...,
        description="Residual standard error sigma_RMSE for Monte Carlo uncertainty sampling",
    )
    target_col: Optional[str] = Field(
        default=None,
        description="Target outcome column modeled by this surrogate",
    )
    sample_size: int = Field(
        default=0,
        description="Number of observations used during surrogate fitting",
    )
    alpha: float = Field(
        default=1.0,
        description="Ridge L2 regularization weight penalty",
    )
    lever_bounds: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Historical percentiles and min/max bounds per lever",
    )
    baseline_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Historical baseline values per lever",
    )
    baseline_prediction: float = Field(
        default=0.0,
        description="Model prediction at baseline lever values",
    )
    created_at: str = Field(
        default="",
        description="Timestamp of surrogate model creation",
    )

    @property
    def weights(self) -> List[float]:
        """Backward-compatible alias for coefficients."""
        return self.coefficients

    @property
    def lever_cols(self) -> List[str]:
        """Backward-compatible alias for feature_names."""
        return self.feature_names

    @property
    def r2(self) -> float:
        """Backward-compatible alias for r_squared."""
        return self.r_squared

    @property
    def cov_inv(self) -> List[List[float]]:
        """Backward-compatible alias for cov_matrix_inv."""
        return self.cov_matrix_inv

    @property
    def chi2_critical(self) -> float:
        """Backward-compatible alias for chi2_critical_99."""
        return self.chi2_critical_99

    @property
    def mse(self) -> float:
        """Residual mean squared error."""
        return self.residual_std ** 2

    @property
    def percentiles(self) -> Dict[str, Dict[str, float]]:
        """Backward-compatible alias for lever_bounds."""
        return self.lever_bounds

    @property
    def lever_means(self) -> Dict[str, float]:
        """Historical mean per lever name."""
        return {col: self.mean_vector[i] for i, col in enumerate(self.feature_names)}

    @property
    def lever_stds(self) -> Dict[str, float]:
        """Historical standard deviation per lever name."""
        return {col: self.lever_bounds.get(col, {}).get("std", 1.0) for col in self.feature_names}

    def __getitem__(self, item: str) -> Any:
        if item == "weights":
            return self.coefficients
        if item == "lever_cols":
            return self.feature_names
        if item == "r2":
            return self.r_squared
        if item == "cov_inv":
            return self.cov_matrix_inv
        if item == "chi2_critical":
            return self.chi2_critical_99
        if item == "mse":
            return self.mse
        if item == "percentiles":
            return self.lever_bounds
        if item == "lever_means":
            return self.lever_means
        if item == "lever_stds":
            return self.lever_stds
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "weights":
            return self.coefficients
        if item == "lever_cols":
            return self.feature_names
        if item == "r2":
            return self.r_squared
        if item == "cov_inv":
            return self.cov_matrix_inv
        if item == "chi2_critical":
            return self.chi2_critical_99
        if item == "mse":
            return self.mse
        if item == "percentiles":
            return self.lever_bounds
        if item == "lever_means":
            return self.lever_means
        if item == "lever_stds":
            return self.lever_stds
        return getattr(self, item, default)


class SimulationResult(BaseModel):
    """Result of evaluating interactive slider inputs against cached surrogate model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    predicted_value: float = Field(
        ...,
        description="Predicted KPI outcome value from surrogate model dot product",
    )
    delta_from_baseline: float = Field(
        ...,
        description="Absolute change relative to historical baseline outcome (pred - baseline)",
    )
    pct_change: float = Field(
        ...,
        description="Percentage change relative to historical baseline outcome",
    )
    is_ood: bool = Field(
        ...,
        description="True if Mahalanobis distance exceeds chi2 threshold or lever is outside historical bounds",
    )
    mahalanobis_dist: float = Field(
        ...,
        description="Mahalanobis distance D_M from historical multi-lever centroid",
    )
    zone: Literal["green", "amber", "red"] = Field(
        ...,
        description="Overall scenario risk zone: green (safe), amber (stretch), red (uncharted/OOD)",
    )
    confidence_badge: Dict[str, Any] = Field(
        ...,
        description="Plain-English confidence badge dictionary generated by JargonTranslator",
    )
    lever_zones: Dict[str, Literal["green", "amber", "red"]] = Field(
        default_factory=dict,
        description="Per-lever zone classification for rendering 3-color slider tracks",
    )
    reality_check_alert: Optional[str] = Field(
        default=None,
        description="Proactive warning message if scenario operates in out-of-distribution (OOD) space",
    )
    baseline_value: float = Field(
        default=0.0,
        description="Baseline prediction value",
    )
    mahalanobis_critical: float = Field(
        default=0.0,
        description="Critical threshold for Mahalanobis distance sqrt(chi2_crit)",
    )

    @property
    def delta(self) -> float:
        """Backward-compatible alias for delta_from_baseline."""
        return self.delta_from_baseline

    @property
    def delta_pct(self) -> float:
        """Backward-compatible alias for pct_change."""
        return self.pct_change

    @property
    def alert_message(self) -> Optional[str]:
        """Backward-compatible alias for reality_check_alert."""
        return self.reality_check_alert

    def __getitem__(self, item: str) -> Any:
        if item == "delta":
            return self.delta_from_baseline
        if item == "delta_pct":
            return self.pct_change
        if item == "alert_message":
            return self.reality_check_alert
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "delta":
            return self.delta_from_baseline
        if item == "delta_pct":
            return self.pct_change
        if item == "alert_message":
            return self.reality_check_alert
        return getattr(self, item, default)


class RecipeCardChange(BaseModel):
    """An individual lever tweak within a counterfactual recipe card."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    lever: str
    from_value: float = Field(alias="from")
    to_value: float = Field(alias="to")
    delta: float = 0.0
    delta_pct: float = 0.0
    zone: Literal["green", "amber", "red"] = "green"

    def __getitem__(self, item: str) -> Any:
        if item == "from":
            return self.from_value
        if item == "to":
            return self.to_value
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "from":
            return self.from_value
        if item == "to":
            return self.to_value
        return getattr(self, item, default)


class RecipeCard(BaseModel):
    """Counterfactual goal-seeking recommendation card for reverse what-if exploration."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(
        ...,
        description="Unique recipe identifier (e.g. 'recipe_1', 'card_1')",
        alias="recipe_id",
    )
    title: str = Field(
        ...,
        description="Strategy title: 'The Easiest Tweak', 'The Balanced Approach', 'Aggressive Growth'",
    )
    strategy_badge: str = Field(
        default="Recipe",
        description="Strategy badge: 'Single Lever', 'Multi-Lever Balanced', 'Stretch Goal'",
    )
    card_type: Optional[str] = Field(
        default=None,
        description="Strategy identifier type ('sparsity', 'balanced', 'conservative', 'stretch')",
    )
    lever_deltas: Dict[str, float] = Field(
        default_factory=dict,
        description="Recommended delta adjustment per lever relative to current settings",
    )
    lever_targets: Dict[str, float] = Field(
        default_factory=dict,
        description="Recommended target absolute value for each slider",
    )
    predicted_target: float = Field(
        ...,
        description="Predicted KPI outcome value under this recipe's lever adjustments",
        alias="predicted_outcome",
    )
    target_outcome: Optional[float] = Field(
        default=None,
        description="User's original requested target outcome goal",
    )
    feasibility_score: float = Field(
        ...,
        description="Normalized feasibility rating in [0.0, 1.0] (1.0 = easiest/safest within green zone)",
    )
    confidence_badge: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Plain-English confidence badge representing risk and feasibility tier",
    )
    description: Optional[str] = Field(
        default=None,
        description="Plain-English actionable explanation of recommended slider adjustments",
    )
    changes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed list of per-lever changes: [{'lever': str, 'from': float, 'to': float, 'delta_pct': float}]",
    )
    slider_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Exact proposed slider dictionary",
    )

    @property
    def recipe_id(self) -> str:
        """Backward-compatible alias for id."""
        return self.id

    @property
    def predicted_outcome(self) -> float:
        """Backward-compatible alias for predicted_target."""
        return self.predicted_target

    def __getitem__(self, item: str) -> Any:
        if item == "recipe_id":
            return self.id
        if item == "predicted_outcome":
            return self.predicted_target
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "recipe_id":
            return self.id
        if item == "predicted_outcome":
            return self.predicted_target
        return getattr(self, item, default)


class WeatherForecastDistribution(BaseModel):
    """Monte Carlo uncertainty outcome distribution and Apache ECharts whisker visualization."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    percentiles: Dict[str, float] = Field(
        ...,
        description="Percentile outcomes: {'p10': float, 'p25': float, 'p50': float, 'p75': float, 'p90': float}",
    )
    probability_of_goal: Optional[float] = Field(
        default=None,
        description="Probability of achieving goal in [0.0, 1.0]",
    )
    goal_probability_pct: Optional[float] = Field(
        default=None,
        description="Probability of achieving goal formatted as percentage in [0.0, 100.0]",
    )
    expected_outcome: float = Field(
        default=0.0,
        description="Mean expected simulation outcome",
        alias="expected",
    )
    echarts_whisker_option: Dict[str, Any] = Field(
        default_factory=dict,
        description="Valid 3-layer Apache ECharts whisker option tree (Context, Spotlight, Title)",
    )
    p10: Optional[float] = Field(
        default=None,
        description="10th percentile outcome (conservative estimate)",
    )
    p25: Optional[float] = Field(
        default=None,
        description="25th percentile outcome",
    )
    p50: Optional[float] = Field(
        default=None,
        description="50th percentile outcome (median)",
    )
    p75: Optional[float] = Field(
        default=None,
        description="75th percentile outcome",
    )
    p90: Optional[float] = Field(
        default=None,
        description="90th percentile outcome (optimistic estimate)",
    )
    mean: float = Field(
        default=0.0,
        description="Simulation distribution mean",
    )
    std: float = Field(
        default=0.0,
        description="Simulation distribution standard deviation",
    )
    sample_draws: int = Field(
        default=1000,
        description="Number of Monte Carlo simulation draws",
    )
    confidence_badge: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Model confidence badge",
    )
    gauge_color: Optional[str] = Field(
        default=None,
        description="Hex color code for goal probability gauge",
    )

    @property
    def expected(self) -> float:
        """Backward-compatible alias for expected_outcome."""
        return self.expected_outcome

    @property
    def echarts_spec(self) -> Dict[str, Any]:
        """Backward-compatible alias for echarts_whisker_option."""
        return self.echarts_whisker_option

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "expected" in data and "expected_outcome" not in data:
                data["expected_outcome"] = data["expected"]
            elif "expected_outcome" in data and "expected" not in data:
                data["expected"] = data["expected_outcome"]

            if "echarts_spec" in data and "echarts_whisker_option" not in data:
                data["echarts_whisker_option"] = data["echarts_spec"]
            elif "echarts_whisker_option" in data and "echarts_spec" not in data:
                data["echarts_spec"] = data["echarts_whisker_option"]

            # Synchronize individual percentiles with dictionary
            pcts = data.get("percentiles")
            if isinstance(pcts, dict):
                for p_key in ["p10", "p25", "p50", "p75", "p90"]:
                    if p_key in pcts and p_key not in data:
                        data[p_key] = pcts[p_key]
                    elif p_key in data and data[p_key] is not None:
                        pcts[p_key] = data[p_key]

            if "probability_of_goal" in data and data["probability_of_goal"] is not None and "goal_probability_pct" not in data:
                data["goal_probability_pct"] = round(float(data["probability_of_goal"]) * 100.0, 2)
            elif "goal_probability_pct" in data and data["goal_probability_pct"] is not None and "probability_of_goal" not in data:
                data["probability_of_goal"] = float(data["goal_probability_pct"]) / 100.0
        return data

    def __contains__(self, item: str) -> bool:
        if item in self.percentiles:
            return True
        if item in ("expected", "expected_outcome", "probability_of_goal", "goal_probability_pct", "echarts_whisker_option", "echarts_spec", "gauge_color"):
            return True
        return hasattr(self, item)

    def __getitem__(self, item: str) -> Any:
        if item == "expected":
            return self.expected_outcome
        if item == "echarts_spec":
            return self.echarts_whisker_option
        if item in self.percentiles:
            return self.percentiles[item]
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "expected":
            return self.expected_outcome
        if item == "echarts_spec":
            return self.echarts_whisker_option
        if item in self.percentiles:
            return self.percentiles[item]
        return getattr(self, item, default)


# ------------------------------------------------------------------------------
# Request / Response Schemas for API Endpoints
# ------------------------------------------------------------------------------

class ScenarioSetupRequest(BaseModel):
    """Payload for initializing and training scenario surrogate model."""

    target_col: Optional[str] = Field(
        default=None,
        description="Optional target column (auto-inferred if omitted)",
    )
    lever_cols: Optional[List[str]] = Field(
        default=None,
        description="Optional explicit list of controllable lever columns",
    )
    alpha: float = Field(
        default=1.0,
        description="Ridge L2 regularization weight penalty",
    )


class ScenarioSetupResponse(BaseModel):
    """Response returned after inferring roles and caching surrogate model."""

    session_id: str = Field(..., description="Active session ID")
    target_col: str = Field(..., description="Target KPI outcome column")
    roles: FeatureRoles = Field(..., description="Inferred feature roles and lever boundaries")
    r_squared: float = Field(..., description="Surrogate model fit score R^2")
    confidence_badge: Dict[str, Any] = Field(..., description="Plain-English model reliability badge")
    baseline_values: Dict[str, float] = Field(default_factory=dict, description="Baseline lever values for diamond markers")
    baseline_target: float = Field(default=0.0, description="Baseline target KPI value")
    surrogate: Optional[SurrogateModel] = Field(default=None, description="Fitted surrogate model details")
    message: str = Field(default="Surrogate model fitted and cached successfully")


class ScenarioPredictRequest(BaseModel):
    """Payload for evaluating real-time slider updates."""

    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (can be specified in URL path or request body)",
    )
    target_col: Optional[str] = Field(
        default=None,
        description="Target column (uses cached target if omitted)",
    )
    slider_values: Dict[str, float] = Field(
        ...,
        description="Map of lever column names to active user slider positions",
    )


class ScenarioPredictResponse(BaseModel):
    """Response returned from fast slider prediction evaluation."""

    session_id: str
    target_col: str
    predicted_value: float
    delta_from_baseline: float
    pct_change: float
    is_ood: bool
    mahalanobis_dist: float
    zone: Literal["green", "amber", "red"]
    confidence_badge: Dict[str, Any]
    lever_zones: Dict[str, Literal["green", "amber", "red"]] = Field(default_factory=dict)
    reality_check_alert: Optional[str] = None
    simulation: Optional[SimulationResult] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class ScenarioRecipesRequest(BaseModel):
    """Payload for counterfactual goal-seeking solver."""

    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (can be specified in URL path or request body)",
    )
    target_goal: float = Field(
        ...,
        description="User's desired KPI outcome goal value",
    )
    target_col: Optional[str] = Field(
        default=None,
        description="Target column (uses cached target if omitted)",
    )
    current_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Current slider values (defaults to baseline median if omitted)",
    )
    strategy: Optional[Literal["all", "easiest", "balanced", "aggressive"]] = "all"


class ScenarioRecipesResponse(BaseModel):
    """Response returning 3 distinct actionable counterfactual recipe cards."""

    session_id: str
    target_goal: float
    target_col: str
    recipes: List[RecipeCard]


class ScenarioForecastRequest(BaseModel):
    """Payload for Monte Carlo weather forecast uncertainty simulation."""

    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (can be specified in URL path or request body)",
    )
    target_col: Optional[str] = Field(
        default=None,
        description="Target column (uses cached target if omitted)",
    )
    slider_values: Dict[str, float] = Field(
        ...,
        description="Active slider values to simulate around",
    )
    target_goal: Optional[float] = Field(
        default=None,
        description="Optional target goal to evaluate attainment probability",
    )
    n_draws: int = Field(
        default=1000,
        description="Number of Monte Carlo normal distribution draws",
    )


class ScenarioForecastResponse(BaseModel):
    """Response returning weather forecast range bar and goal probability."""

    session_id: str
    target_col: str
    expected: float
    p10: float
    p90: float
    goal_probability_pct: Optional[float] = None
    percentiles: Dict[str, float]
    echarts_whisker_option: Dict[str, Any]
    distribution: Optional[WeatherForecastDistribution] = None
