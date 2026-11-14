"""Portable statistical helpers with chronological forecast validation."""

from typing import Any
import numpy as np
import pandas as pd


def forecast(
    series: pd.Series,
    horizon: int = 12,
    method: str = "exponential_smoothing",
    season_length: int | None = None,
) -> dict[str, Any]:
    """Fit on current data and backtest on a trailing holdout, without leakage."""
    values = pd.to_numeric(series, errors="raise").dropna().astype(float)
    if len(values) == 0:
        raise ValueError("Forecasting requires at least ten finite observations")
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

    holdout_size = max(2, min(horizon, len(values) // 5))
    training, holdout = values.iloc[:-holdout_size], values.iloc[-holdout_size:]

    is_constant = bool(np.var(values.to_numpy()) < 1e-12)

    def fit_predict(train_series: pd.Series, count: int) -> tuple[np.ndarray, Any]:
        if is_constant or method == "naive":
            return np.repeat(float(train_series.iloc[-1]), count), None
        if method == "arima":
            from statsmodels.tsa.arima.model import ARIMA
            model = ARIMA(train_series.to_numpy(), order=(1, 1, 0)).fit()
            pred = model.get_forecast(count)
            return np.asarray(pred.predicted_mean), pred.conf_int(alpha=0.05).tolist()
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            model = ExponentialSmoothing(
                train_series.to_numpy(),
                trend="add",
                seasonal="add" if season_length else None,
                seasonal_periods=season_length,
                initialization_method="estimated",
            ).fit(optimized=True)
            return np.asarray(model.forecast(count)), None
        except Exception:
            # Fallback to linear trend or naive if Holt-Winters numerical convergence fails
            x = np.arange(len(train_series), dtype=float)
            y = train_series.to_numpy(dtype=float)
            if np.var(x) > 1e-12:
                slope, intercept = np.polyfit(x, y, 1)
                future_x = np.arange(len(train_series), len(train_series) + count, dtype=float)
                return slope * future_x + intercept, None
            return np.repeat(float(train_series.iloc[-1]), count), None

    backtest, _ = fit_predict(training, holdout_size)
    prediction, intervals = fit_predict(values, horizon)

    # Compute prediction intervals (p10 / p90)
    residuals = backtest - holdout.to_numpy()
    res_std = float(np.std(residuals)) if len(residuals) > 0 else 0.0
    if is_constant:
        p10 = prediction.tolist()
        p90 = prediction.tolist()
    elif intervals:
        p10 = [float(iv[0]) for iv in intervals]
        p90 = [float(iv[1]) for iv in intervals]
    else:
        p10 = [float(val - 1.28 * res_std) for val in prediction]
        p90 = [float(val + 1.28 * res_std) for val in prediction]

    # Future timestamps
    if isinstance(values.index, pd.DatetimeIndex) and len(values.index) >= 2:
        step = values.index[1] - values.index[0]
        start_date = values.index[-1] + step
        future_idx = pd.date_range(start=start_date, periods=horizon, freq=step)
        timestamps = [d.strftime("%Y-%m-%d") for d in future_idx]
    else:
        timestamps = [f"Step +{i + 1}" for i in range(horizon)]

    pred_list = prediction.tolist()

    return {
        "method": method,
        "horizon": horizon,
        "mean": pred_list,
        "forecast": pred_list,
        "p10": p10,
        "p90": p90,
        "timestamps": timestamps,
        "prediction_intervals_95": intervals,
        "backtest_mae": float(np.abs(backtest - holdout.to_numpy()).mean()),
        "baseline_mae": float(np.abs(float(training.iloc[-1]) - holdout.to_numpy()).mean()),
        "training_observations": len(training),
        "holdout_observations": holdout_size,
        "assumptions": "Ordered, equally spaced observations; future behaviour follows the fitted pattern.",
        "uncertainty": "95% model intervals" if intervals else "This method does not provide calibrated prediction intervals.",
    }
