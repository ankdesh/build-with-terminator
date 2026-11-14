"""FastAPI router for Interactive Scenario 'What-If' Studio (Milestone 3).

Exposes high-speed, sub-second endpoints for scenario initialization,
closed-form Ridge surrogate simulation, counterfactual goal-seeking recipes,
and Monte Carlo weather forecast uncertainty distributions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast
from fastapi import APIRouter, HTTPException, status
import pandas as pd

from backend.exceptions import (
    DatasetNotLoadedError,
    ScenarioSimulationError,
    SessionNotFoundError,
    SurrogateModelError,
)
from backend.models.whatif import (
    RecipeCard,
    ScenarioForecastRequest,
    ScenarioForecastResponse,
    ScenarioPredictRequest,
    ScenarioPredictResponse,
    ScenarioRecipesRequest,
    ScenarioSetupRequest,
    ScenarioSetupResponse,
    SimulationResult,
    SurrogateModel,
    WeatherForecastDistribution,
)
from backend.services.jargon_translator import JargonTranslator
from backend.services.session_store import SessionStore
from backend.services.whatif_service import WhatIfService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["Scenario Studio"])
session_store = SessionStore()
whatif_service = WhatIfService()


@router.post(
    "/{session_id}/scenario/setup",
    response_model=ScenarioSetupResponse,
    summary="Initialize scenario studio and train surrogate model",
)
async def setup_scenario(
    session_id: str,
    payload: Optional[ScenarioSetupRequest] = None,
) -> ScenarioSetupResponse:
    """Classifies dataset columns into levers/locks, fits a closed-form

    Ridge surrogate model with covariance matrix, and caches it in SessionStore.
    """
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    try:
        csv_path = session_store.get_csv_path(session_id)
    except SessionNotFoundError:
        raise DatasetNotLoadedError(session_id)

    if not csv_path.exists():
        raise DatasetNotLoadedError(session_id)

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ScenarioSimulationError(
            "Dataset is empty.",
            "Cannot train scenario surrogate model on an empty dataset.",
        )

    target_col = payload.target_col if payload else None
    lever_cols = payload.lever_cols if payload else None
    alpha = payload.alpha if payload else 1.0

    roles = whatif_service.infer_roles(df=df, target_col=target_col)
    effective_levers = lever_cols or roles.levers

    if not effective_levers:
        raise ScenarioSimulationError(
            "No controllable numeric levers found for scenario modeling.",
            "Dataset must contain continuous numeric columns that vary across observations.",
        )

    surrogate: SurrogateModel = whatif_service.fit_surrogate(
        df=df,
        target_col=roles.target_col,
        lever_cols=effective_levers,
        alpha=alpha,
    )
    session_store.save_surrogate(session_id, roles.target_col, surrogate)

    conf_badge = JargonTranslator.get_confidence_badge(
        r_squared=surrogate.r_squared,
        sample_size=len(df),
        is_ood=False,
    )

    return ScenarioSetupResponse(
        session_id=session_id,
        target_col=roles.target_col,
        roles=roles,
        r_squared=surrogate.r_squared,
        confidence_badge=conf_badge,
        baseline_values=roles.baseline_values,
        baseline_target=roles.baseline_target,
        surrogate=surrogate,
        message="Surrogate model fitted and cached successfully",
    )


@router.post(
    "/{session_id}/scenario/predict",
    response_model=ScenarioPredictResponse,
    summary="Evaluate instant slider predictions with OOD guardrails",
)
async def predict_scenario(
    session_id: str,
    payload: ScenarioPredictRequest,
) -> ScenarioPredictResponse:
    """Evaluates user slider positions in <1ms using cached surrogate model,

    calculates Mahalanobis distance against chi2 critical threshold,
    and returns 3-zone track classifications and proactive reality check alert.
    """
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    target_col = payload.target_col
    surrogate = session_store.get_surrogate(session_id, target_col)

    if surrogate is None:
        # Auto-warm cache if dataset file exists
        try:
            csv_path = session_store.get_csv_path(session_id)
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                roles = whatif_service.infer_roles(df=df, target_col=target_col)
                surrogate = whatif_service.fit_surrogate(
                    df=df,
                    target_col=roles.target_col,
                    lever_cols=roles.levers,
                )
                session_store.save_surrogate(session_id, roles.target_col, surrogate)
        except Exception as err:
            logger.warning("Auto-warming surrogate failed: %s", err)

    if surrogate is None:
        raise SurrogateModelError(
            f"No cached surrogate model found for session '{session_id}'.",
            "Call /api/sessions/{session_id}/scenario/setup first to initialize model.",
        )

    sim: SimulationResult = whatif_service.predict(surrogate, payload.slider_values)
    effective_target = target_col or getattr(surrogate, "target_col", None) or "target"

    return ScenarioPredictResponse(
        session_id=session_id,
        target_col=effective_target,
        predicted_value=sim.predicted_value,
        delta_from_baseline=sim.delta_from_baseline,
        pct_change=sim.pct_change,
        is_ood=sim.is_ood,
        mahalanobis_dist=sim.mahalanobis_dist,
        zone=sim.zone,
        confidence_badge=sim.confidence_badge,
        lever_zones=sim.lever_zones,
        reality_check_alert=sim.reality_check_alert,
        simulation=sim,
    )


@router.post(
    "/{session_id}/scenario/recipes",
    response_model=List[RecipeCard],
    summary="Compute 3 distinct counterfactual recipe cards to hit target goal",
)
async def get_scenario_recipes(
    session_id: str,
    payload: ScenarioRecipesRequest,
) -> List[RecipeCard]:
    """Executes counterfactual goal-seeking optimization to generate 3 actionable

    recipe cards: (1) Easiest Single Tweak, (2) Balanced Multi-Lever, (3) Aggressive Growth.
    """
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    target_col = payload.target_col
    surrogate = session_store.get_surrogate(session_id, target_col)

    if surrogate is None:
        # Auto-warm cache if dataset exists
        try:
            csv_path = session_store.get_csv_path(session_id)
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                roles = whatif_service.infer_roles(df=df, target_col=target_col)
                surrogate = whatif_service.fit_surrogate(
                    df=df,
                    target_col=roles.target_col,
                    lever_cols=roles.levers,
                )
                session_store.save_surrogate(session_id, roles.target_col, surrogate)
        except Exception as err:
            logger.warning("Auto-warming surrogate in recipes failed: %s", err)

    if surrogate is None:
        raise SurrogateModelError(
            f"No cached surrogate model found for session '{session_id}'.",
            "Call /api/sessions/{session_id}/scenario/setup first to initialize model.",
        )

    current_vals = payload.current_values or {}
    recipes = whatif_service.solve_recipes(
        surrogate=surrogate,
        target_goal=payload.target_goal,
        current_values=current_vals,
    )
    return recipes


@router.post(
    "/{session_id}/scenario/forecast",
    response_model=ScenarioForecastResponse,
    summary="Run Monte Carlo simulation for weather forecast whisker and goal probability",
)
@router.post(
    "/{session_id}/scenario/weather",
    response_model=ScenarioForecastResponse,
    include_in_schema=False,
)
async def forecast_scenario(
    session_id: str,
    payload: ScenarioForecastRequest,
) -> ScenarioForecastResponse:
    """Runs 1,000 Monte Carlo draws incorporating surrogate residual variance

    to produce a 10th-90th percentile weather forecast range bar and goal probability gauge.
    """
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    target_col = payload.target_col
    surrogate = session_store.get_surrogate(session_id, target_col)

    if surrogate is None:
        # Auto-warm cache if dataset exists
        try:
            csv_path = session_store.get_csv_path(session_id)
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                roles = whatif_service.infer_roles(df=df, target_col=target_col)
                surrogate = whatif_service.fit_surrogate(
                    df=df,
                    target_col=roles.target_col,
                    lever_cols=roles.levers,
                )
                session_store.save_surrogate(session_id, roles.target_col, surrogate)
        except Exception as err:
            logger.warning("Auto-warming surrogate in forecast failed: %s", err)

    if surrogate is None:
        raise SurrogateModelError(
            f"No cached surrogate model found for session '{session_id}'.",
            "Call /api/sessions/{session_id}/scenario/setup first to initialize model.",
        )

    dist_result = whatif_service.simulate_weather_distribution(
        surrogate=surrogate,
        slider_values=payload.slider_values,
        target_goal=payload.target_goal,
        n_draws=payload.n_draws,
    )

    if isinstance(dist_result, dict):
        dist = WeatherForecastDistribution.model_validate(dist_result)
    else:
        dist = cast(WeatherForecastDistribution, dist_result)

    effective_target = target_col or getattr(surrogate, "target_col", None) or "target"
    return ScenarioForecastResponse(
        session_id=session_id,
        target_col=effective_target,
        expected=dist.expected_outcome,
        p10=float(dist.percentiles.get("p10", dist.expected_outcome)),
        p90=float(dist.percentiles.get("p90", dist.expected_outcome)),
        goal_probability_pct=dist.goal_probability_pct,
        percentiles=dist.percentiles,
        echarts_whisker_option=dist.echarts_whisker_option,
        distribution=dist,
    )
