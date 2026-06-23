from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from minigrid_learn.config import Phase1Config

PLOT_FILES = (
    "episodic_reward.png",
    "episode_length.png",
    "evaluation_reward.png",
    "success_rate.png",
    "policy_entropy.png",
    "reward_vs_episode_length.png",
    "convergence_comparison.png",
    "final_performance_by_seed.png",
    "training_diagnostics.png",
    "sample_efficiency.png",
)


def _load_runs(config: Phase1Config) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    run_frames: list[pd.DataFrame] = []
    eval_frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    for environment in config.environments:
        for seed in config.seeds:
            root = config.project.artifact_root / environment.slug / f"seed-{seed}"
            labels = {
                "environment": environment.slug,
                "environment_id": environment.id,
                "seed": seed,
            }
            metrics_path = root / "run_metrics.csv"
            evaluations_path = root / "evaluations.csv"
            summary_path = root / "summary.json"
            if metrics_path.exists():
                frame = pd.read_csv(metrics_path)
                for key, value in labels.items():
                    frame[key] = value
                run_frames.append(frame)
            if evaluations_path.exists():
                frame = pd.read_csv(evaluations_path)
                for key, value in labels.items():
                    frame[key] = value
                eval_frames.append(frame)
            if summary_path.exists():
                summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))

    return (
        pd.concat(run_frames, ignore_index=True) if run_frames else pd.DataFrame(),
        pd.concat(eval_frames, ignore_index=True) if eval_frames else pd.DataFrame(),
        summaries,
    )


def _smooth(frame: pd.DataFrame, column: str, window: int = 5) -> pd.Series:
    return frame.groupby(["environment", "seed"], sort=False)[column].transform(
        lambda values: values.rolling(window, min_periods=1).mean()
    )


def _line_plot(
    data: pd.DataFrame,
    y: str,
    title: str,
    ylabel: str,
    output: Path,
    *,
    smooth: bool = True,
) -> None:
    plt.figure(figsize=(10, 6))
    plot_data = data.copy()
    plot_y = y
    if smooth:
        plot_y = f"{y}_smoothed"
        plot_data[plot_y] = _smooth(plot_data, y)
    sns.lineplot(
        data=plot_data,
        x="timesteps",
        y=plot_y,
        hue="environment",
        units="seed",
        estimator=None,
        alpha=0.28,
        linewidth=1,
        legend=False,
    )
    sns.lineplot(
        data=plot_data,
        x="timesteps",
        y=plot_y,
        hue="environment",
        estimator="mean",
        errorbar=("ci", 95),
        linewidth=2.5,
    )
    plt.title(title)
    plt.xlabel("Environment steps")
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(output, dpi=160)
    plt.close()


def _placeholder(path: Path, title: str) -> None:
    plt.figure(figsize=(10, 6))
    plt.text(
        0.5,
        0.5,
        "No completed experiment data yet",
        ha="center",
        va="center",
        fontsize=16,
    )
    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def _create_plots(
    run_data: pd.DataFrame, eval_data: pd.DataFrame, summaries: list[dict[str, Any]], plot_dir: Path
) -> None:
    sns.set_theme(style="whitegrid", context="talk")
    plot_dir.mkdir(parents=True, exist_ok=True)

    standard_lines = [
        (
            run_data,
            "episode_reward_mean",
            "Training episodic reward",
            "Mean reward",
            "episodic_reward.png",
        ),
        (
            run_data,
            "episode_length_mean",
            "Training episode length",
            "Mean episode length",
            "episode_length.png",
        ),
        (
            eval_data,
            "mean_reward",
            "Deterministic evaluation reward",
            "Mean reward",
            "evaluation_reward.png",
        ),
        (eval_data, "success_rate", "Evaluation success rate", "Success rate", "success_rate.png"),
        (run_data, "policy_entropy", "Policy entropy", "Entropy", "policy_entropy.png"),
    ]
    for data, y, title, ylabel, filename in standard_lines:
        if not data.empty and y in data and data[y].notna().any():
            _line_plot(data.dropna(subset=[y]), y, title, ylabel, plot_dir / filename)
        else:
            _placeholder(plot_dir / filename, title)

    path = plot_dir / "reward_vs_episode_length.png"
    if (
        not run_data.empty
        and run_data[["episode_reward_mean", "episode_length_mean"]].notna().all(axis=1).any()
    ):
        plt.figure(figsize=(10, 6))
        sns.scatterplot(
            data=run_data,
            x="episode_length_mean",
            y="episode_reward_mean",
            hue="environment",
            style="seed",
            alpha=0.7,
        )
        plt.title("Reward versus episode length")
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
    else:
        _placeholder(path, "Reward versus episode length")

    summary_frame = pd.DataFrame(summaries)
    path = plot_dir / "convergence_comparison.png"
    if not summary_frame.empty:
        plt.figure(figsize=(10, 6))
        sns.barplot(
            data=summary_frame,
            x="environment_slug",
            y="timesteps",
            hue="status",
            errorbar=None,
        )
        sns.stripplot(
            data=summary_frame,
            x="environment_slug",
            y="timesteps",
            color="black",
            size=7,
        )
        plt.title("Steps consumed and stopping outcome")
        plt.xlabel("Environment")
        plt.ylabel("Environment steps")
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
    else:
        _placeholder(path, "Steps consumed and stopping outcome")

    path = plot_dir / "final_performance_by_seed.png"
    if not eval_data.empty:
        final = (
            eval_data.sort_values("timesteps")
            .groupby(["environment", "seed"], as_index=False)
            .tail(1)
        )
        plt.figure(figsize=(10, 6))
        sns.barplot(
            data=final,
            x="seed",
            y="mean_reward",
            hue="environment",
            errorbar=None,
        )
        plt.title("Final evaluation reward by seed")
        plt.ylabel("Mean evaluation reward")
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
    else:
        _placeholder(path, "Final evaluation reward by seed")

    path = plot_dir / "training_diagnostics.png"
    diagnostic_columns = [
        ("policy_gradient_loss", "Policy loss"),
        ("value_loss", "Value loss"),
        ("approx_kl", "Approximate KL"),
        ("clip_fraction", "Clip fraction"),
        ("explained_variance", "Explained variance"),
        ("entropy_loss", "Entropy loss"),
    ]
    if not run_data.empty and any(
        run_data.get(column, pd.Series(dtype=float)).notna().any()
        for column, _ in diagnostic_columns
    ):
        figure, axes = plt.subplots(2, 3, figsize=(18, 10))
        for axis, (column, title) in zip(axes.flat, diagnostic_columns, strict=True):
            if column in run_data:
                sns.lineplot(
                    data=run_data.dropna(subset=[column]),
                    x="timesteps",
                    y=column,
                    hue="environment",
                    estimator="mean",
                    errorbar=None,
                    ax=axis,
                    legend=False,
                )
            axis.set_title(title)
            axis.set_xlabel("Steps")
        figure.suptitle("PPO optimization diagnostics")
        figure.tight_layout()
        figure.savefig(path, dpi=160)
        plt.close(figure)
    else:
        _placeholder(path, "PPO optimization diagnostics")

    path = plot_dir / "sample_efficiency.png"
    if not eval_data.empty:
        efficiency_rows = []
        for (environment, seed), frame in eval_data.groupby(["environment", "seed"]):
            ordered = frame.sort_values("timesteps")
            auc = float(np.trapezoid(ordered["mean_reward"], ordered["timesteps"]))
            max_steps = float(ordered["timesteps"].max())
            efficiency_rows.append(
                {
                    "environment": environment,
                    "seed": seed,
                    "normalized_reward_auc": auc / max_steps if max_steps else 0.0,
                }
            )
        efficiency = pd.DataFrame(efficiency_rows)
        plt.figure(figsize=(10, 6))
        sns.barplot(
            data=efficiency,
            x="environment",
            y="normalized_reward_auc",
            hue="seed",
            errorbar=None,
        )
        plt.title("Sample efficiency (normalized reward AUC)")
        plt.ylabel("Area under reward curve / total steps")
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
    else:
        _placeholder(path, "Sample efficiency")


def _summary_table(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return "_No completed full experiment runs were found._"
    rows = [
        "| Environment | Seed | Status | Steps | Best reward | Final reward | Time |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for item in sorted(summaries, key=lambda value: (value["environment_slug"], value["seed"])):
        best = item["best_mean_reward"]
        final = item["final_mean_reward"]
        rows.append(
            f"| `{item['environment_id']}` | {item['seed']} | {item['status']} | "
            f"{item['timesteps']:,} | {best if best is not None else 'n/a'} | "
            f"{final if final is not None else 'n/a'} | {item['elapsed_seconds'] / 60:.1f} min |"
        )
    return "\n".join(rows)


def generate_report(config: Phase1Config) -> Path:
    report_root = config.project.report_root
    plot_dir = report_root / "plots"
    data_dir = report_root / "data"
    report_root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    run_data, eval_data, summaries = _load_runs(config)
    run_data.to_csv(data_dir / "run_metrics.csv", index=False)
    eval_data.to_csv(data_dir / "evaluation_metrics.csv", index=False)
    summary_payload = {
        "generated_from": str(config.project.artifact_root),
        "completed_runs": len(summaries),
        "expected_runs": len(config.environments) * len(config.seeds),
        "runs": summaries,
    }
    (data_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8"
    )
    _create_plots(run_data, eval_data, summaries, plot_dir)

    report = f"""# Phase 1: Interactive MiniGrid PPO Baselines

This report compares PPO on `MiniGrid-Empty-8x8-v0` and
`MiniGrid-Dynamic-Obstacles-8x8-v0`. It is generated from saved CSV/JSON metrics,
so the report can be rebuilt without retraining.

## Experiment status

{_summary_table(summaries)}

`threshold_reached` means the configured mean evaluation reward was met for three
consecutive evaluations. `maximum_steps_reached` means the bounded 500,000-step
run completed without that sustained result; it is not labeled as convergence.

## Learning curves

![Training episodic reward](plots/episodic_reward.png)

Higher reward indicates progress toward the goal. Seed traces are faint and the
aggregate curve includes a 95% confidence interval, exposing both learning speed
and run-to-run variability.

![Training episode length](plots/episode_length.png)

Successful policies usually shorten paths. In Dynamic Obstacles, longer or noisy
episodes can also reflect collision avoidance rather than simple inefficiency.

![Deterministic evaluation reward](plots/evaluation_reward.png)

Periodic deterministic evaluation separates policy quality from exploration noise.

![Evaluation success rate](plots/success_rate.png)

Success is an episode with positive MiniGrid reward. Compare this with reward:
two agents may both succeed while one reaches the goal by a shorter route.

![Policy entropy](plots/policy_entropy.png)

Entropy measures action uncertainty. A gradual decline often accompanies learning;
an early collapse while reward remains flat can indicate premature convergence.

## Behavioral and convergence comparisons

![Reward versus episode length](plots/reward_vs_episode_length.png)

This relationship helps distinguish efficient solutions (high reward, short episode)
from wandering or obstacle-induced delays.

![Steps and stopping outcome](plots/convergence_comparison.png)

Bars show training steps consumed, while color records why each run stopped.

![Final performance by seed](plots/final_performance_by_seed.png)

Seed-level final reward reveals whether a result is robust or driven by one lucky run.

![Sample efficiency](plots/sample_efficiency.png)

Normalized area under the evaluation-reward curve rewards agents that learn early,
not only agents with a strong final checkpoint.

## PPO optimization diagnostics

![PPO diagnostics](plots/training_diagnostics.png)

Approximate KL and clip fraction show update size; policy and value loss show the
optimization objectives; explained variance indicates how well the critic predicts
returns; entropy loss reflects exploration pressure. These are diagnostics, not
scores—interpret them alongside reward and success.

## Setup and reproducibility

- Python is managed by `uv` in `.venv`; dependencies are locked in `uv.lock`.
- `ImgObsWrapper` removes mission text and exposes the 7×7×3 symbolic image.
- SB3 transposes images to channel-first format, and `MiniGridCNN` extracts 128 features.
- Each environment uses seeds 0, 1, and 2; evaluation uses `seed + 10000`.
- Evaluation runs every 10,000 steps for 20 deterministic episodes.
- TensorBoard logs, checkpoints, and models live under `{config.project.artifact_root}`.
- Aggregated source data for these figures is in [`data/`](data/).

## Commands

```bash
uv sync
uv run minigrid-learn smoke
uv run minigrid-learn train --all
uv run minigrid-learn report
uv run tensorboard --logdir {config.project.artifact_root}
```

To re-evaluate a model:

```bash
uv run minigrid-learn evaluate \\
  --env empty-8x8 \\
  --model {config.project.artifact_root}/empty-8x8/seed-0/best_model/best_model.zip
```
"""
    report_path = report_root / "phase1_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path
