"""Portable statistical helpers with chronological forecast validation."""

from typing import Any
import numpy as np
import pandas as pd


def forecast(series: pd.Series, horizon: int = 12, method: str = "exponential_smoothing", season_length: int | None = None) -> dict[str, Any]:
    """Fit on current data and backtest on a trailing holdout, without leakage."""
    values = pd.to_numeric(series, errors="raise").dropna().astype(float)
    if isinstance(values.index, pd.DatetimeIndex):
        spacing = values.index.to_series().diff().dropna()
        if not values.index.is_monotonic_increasing or not values.index.is_unique or spacing.nunique() != 1:
            raise ValueError("Forecast observations must have an ordered, equally spaced time index")
    if horizon < 1 or horizon > 365:
        raise ValueError("Forecast horizon must be between 1 and 365")
    if len(values) < 10 or not np.isfinite(values).all():
        raise ValueError("Forecasting requires at least ten finite observations")
    if method not in {"exponential_smoothing", "arima", "naive"}:
        raise ValueError("Unsupported saved forecast method")
    if season_length is not None and (season_length < 2 or len(values) < season_length * 3):
        raise ValueError("Seasonal forecasting requires at least three full seasons")

    def fit_predict(training: pd.Series, count: int) -> tuple[np.ndarray, Any]:
        if method == "naive":
            return np.repeat(float(training.iloc[-1]), count), None
        if method == "arima":
            from statsmodels.tsa.arima.model import ARIMA
            model = ARIMA(training.to_numpy(), order=(1, 1, 0)).fit()
            prediction = model.get_forecast(count)
            return np.asarray(prediction.predicted_mean), prediction.conf_int(alpha=0.05).tolist()
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            training.to_numpy(), trend="add", seasonal="add" if season_length else None,
            seasonal_periods=season_length, initialization_method="estimated",
        ).fit(optimized=True)
        return np.asarray(model.forecast(count)), None

    holdout_size = max(2, min(horizon, len(values) // 5))
    training, holdout = values.iloc[:-holdout_size], values.iloc[-holdout_size:]
    backtest, _ = fit_predict(training, holdout_size)
    prediction, intervals = fit_predict(values, horizon)
    return {
        "method": method,
        "forecast": prediction.tolist(),
        "prediction_intervals_95": intervals,
        "backtest_mae": float(np.abs(backtest - holdout.to_numpy()).mean()),
        "baseline_mae": float(np.abs(float(training.iloc[-1]) - holdout.to_numpy()).mean()),
        "training_observations": len(training), "holdout_observations": holdout_size,
        "assumptions": "Ordered, equally spaced observations; future behaviour follows the fitted pattern.",
        "uncertainty": "95% model intervals" if intervals else "This method does not provide calibrated prediction intervals.",
    }
