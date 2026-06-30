"""
Shared plotting utilities with a consistent modern dark theme.

All experiment notebooks import from here to ensure uniform styling.
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Global style setup
# ---------------------------------------------------------------------------

def setup_style():
    """Apply a modern dark theme with consistent aesthetics."""
    plt.style.use("dark_background")
    sns.set_context("notebook", font_scale=1.1)

    mpl.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor": "#16213e",
        "axes.edgecolor": "#e94560",
        "axes.labelcolor": "#eee",
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.color": "#ccc",
        "ytick.color": "#ccc",
        "text.color": "#eee",
        "grid.color": "#333",
        "grid.alpha": 0.3,
        "legend.facecolor": "#16213e",
        "legend.edgecolor": "#444",
        "figure.figsize": (10, 6),
        "figure.dpi": 100,
        "savefig.dpi": 150,
        "font.family": "sans-serif",
    })


# Color palette
COLORS = {
    "primary": "#e94560",
    "secondary": "#0f3460",
    "accent": "#533483",
    "highlight": "#00d2ff",
    "success": "#00e676",
    "warning": "#ffab40",
    "APPS": "#e94560",
    "CDSS": "#00d2ff",
    "KBSS": "#ffab40",
}

PARTITION_COLORS = [COLORS["APPS"], COLORS["CDSS"], COLORS["KBSS"]]


# ---------------------------------------------------------------------------
# KDE / Distribution plots
# ---------------------------------------------------------------------------

def plot_kde(
    data: pd.Series | np.ndarray,
    title: str = "Kernel Density Estimate",
    xlabel: str = "Value",
    color: str | None = None,
    ax: plt.Axes | None = None,
    log_scale: bool = False,
    label: str | None = None,
) -> plt.Axes:
    """Plot a KDE of the given data."""
    if ax is None:
        fig, ax = plt.subplots()

    clr = color or COLORS["primary"]
    sns.kdeplot(data, ax=ax, color=clr, fill=True, alpha=0.3, linewidth=2, label=label)

    if log_scale:
        ax.set_xscale("log")

    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.grid(True, alpha=0.2)

    if label:
        ax.legend()

    return ax


def plot_distribution_comparison(
    raw: np.ndarray,
    zscore: np.ndarray,
    quantile: np.ndarray,
    partition_name: str = "",
) -> plt.Figure:
    """
    Plot a 3-panel comparison: raw, z-scored, and quantile-transformed distributions.
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        f"Distribution Comparison — {partition_name}",
        fontsize=16, fontweight="bold", color=COLORS["highlight"],
    )

    # Raw
    sns.histplot(raw, bins=50, ax=axes[0], color=COLORS["primary"], alpha=0.7, kde=True)
    axes[0].set_title("Raw Values")
    axes[0].set_xlabel("val_accuracy")

    # Z-score
    sns.histplot(zscore, bins=50, ax=axes[1], color=COLORS["highlight"], alpha=0.7, kde=True)
    axes[1].set_title("Z-Score Standardized")
    axes[1].set_xlabel("z-score")

    # Quantile
    sns.histplot(quantile, bins=50, ax=axes[2], color=COLORS["success"], alpha=0.7, kde=True)
    axes[2].set_title("Quantile Transform (Gaussian)")
    axes[2].set_xlabel("quantile value")

    for ax in axes:
        ax.grid(True, alpha=0.2)

    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# CDF plot
# ---------------------------------------------------------------------------

def plot_cdf(
    data: dict[str, np.ndarray],
    thresholds: list[int] | None = None,
    title: str = "Cumulative Distribution Function",
    xlabel: str = "Token Length",
) -> plt.Figure:
    """
    Plot CDF curves for multiple partitions with optional threshold markers.

    Parameters
    ----------
    data : dict
        {partition_name: array_of_values}
    thresholds : list[int]
        Vertical threshold lines to draw (e.g., [2048, 4096, 8192]).
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    for name, values in data.items():
        sorted_vals = np.sort(values)
        cdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
        color = COLORS.get(name, COLORS["primary"])
        ax.plot(sorted_vals, cdf, label=name, color=color, linewidth=2)

    if thresholds:
        for t in thresholds:
            ax.axvline(x=t, linestyle="--", color=COLORS["warning"], alpha=0.7, linewidth=1.5)
            ax.text(t, 0.02, f" {t}", color=COLORS["warning"], fontsize=10,
                    rotation=90, va="bottom", ha="right")

    ax.set_title(title, fontweight="bold", fontsize=14)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Cumulative Fraction")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.2)
    ax.set_ylim(0, 1.05)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Correlation heatmap
# ---------------------------------------------------------------------------

def plot_correlation_matrix(
    df: pd.DataFrame,
    columns: list[str],
    method: str = "spearman",
    title: str = "Correlation Matrix",
) -> plt.Figure:
    """Plot a styled correlation heatmap."""
    corr = df[columns].corr(method=method)

    fig, ax = plt.subplots(figsize=(8, 7))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)

    cmap = sns.diverging_palette(250, 10, as_cmap=True)
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".3f", cmap=cmap,
        vmin=-1, vmax=1, center=0,
        square=True, linewidths=0.5,
        cbar_kws={"shrink": 0.8},
        ax=ax,
    )
    ax.set_title(f"{title} ({method.title()})", fontweight="bold", fontsize=14)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Scatter with regression
# ---------------------------------------------------------------------------

def plot_scatter_with_regression(
    x: np.ndarray | pd.Series,
    y: np.ndarray | pd.Series,
    xlabel: str = "X",
    ylabel: str = "Y",
    title: str = "Scatter Plot",
    color: str | None = None,
    alpha: float = 0.3,
    sample_size: int = 5000,
) -> plt.Figure:
    """Plot a scatter with a regression line, subsampling for performance."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Subsample for plotting
    x_arr = np.asarray(x)
    y_arr = np.asarray(y)

    if len(x_arr) > sample_size:
        idx = np.random.choice(len(x_arr), sample_size, replace=False)
        x_plot, y_plot = x_arr[idx], y_arr[idx]
    else:
        x_plot, y_plot = x_arr, y_arr

    clr = color or COLORS["highlight"]
    ax.scatter(x_plot, y_plot, alpha=alpha, s=10, color=clr, edgecolors="none")

    # Regression line
    valid = np.isfinite(x_plot) & np.isfinite(y_plot)
    if valid.sum() > 2:
        z = np.polyfit(x_plot[valid], y_plot[valid], 1)
        p = np.poly1d(z)
        x_line = np.linspace(np.nanmin(x_plot), np.nanmax(x_plot), 100)
        ax.plot(x_line, p(x_line), color=COLORS["primary"], linewidth=2, linestyle="--",
                label=f"y = {z[0]:.4f}x + {z[1]:.4f}")
        ax.legend()

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold", fontsize=14)
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Actual vs Predicted
# ---------------------------------------------------------------------------

def plot_actual_vs_predicted(
    y_actual: np.ndarray,
    y_predicted: np.ndarray,
    title: str = "Actual vs Predicted",
    sample_size: int = 5000,
) -> plt.Figure:
    """Plot actual vs predicted with a 45-degree reference line."""
    fig, ax = plt.subplots(figsize=(8, 8))

    # Subsample
    if len(y_actual) > sample_size:
        idx = np.random.choice(len(y_actual), sample_size, replace=False)
        ya, yp = y_actual[idx], y_predicted[idx]
    else:
        ya, yp = y_actual, y_predicted

    ax.scatter(ya, yp, alpha=0.3, s=10, color=COLORS["highlight"], edgecolors="none")

    # 45-degree line
    lims = [
        min(np.nanmin(ya), np.nanmin(yp)),
        max(np.nanmax(ya), np.nanmax(yp)),
    ]
    ax.plot(lims, lims, color=COLORS["primary"], linewidth=2, linestyle="--",
            label="Perfect prediction", alpha=0.8)

    ax.set_xlabel("Actual", fontsize=12)
    ax.set_ylabel("Predicted", fontsize=12)
    ax.set_title(title, fontweight="bold", fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.2)
    ax.set_aspect("equal")
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Feature importance
# ---------------------------------------------------------------------------

def plot_feature_importance(
    importance: np.ndarray,
    feature_names: list[str],
    top_n: int = 20,
    title: str = "Feature Importance",
) -> plt.Figure:
    """Plot a horizontal bar chart of top-N feature importances."""
    idx = np.argsort(importance)[-top_n:]
    fig, ax = plt.subplots(figsize=(10, max(6, top_n * 0.35)))

    y_pos = np.arange(len(idx))
    ax.barh(y_pos, importance[idx], color=COLORS["highlight"], alpha=0.8, edgecolor=COLORS["primary"])
    ax.set_yticks(y_pos)
    ax.set_yticklabels([feature_names[i] for i in idx], fontsize=9)
    ax.set_xlabel("Importance")
    ax.set_title(title, fontweight="bold", fontsize=14)
    ax.grid(True, axis="x", alpha=0.2)
    plt.tight_layout()
    return fig
