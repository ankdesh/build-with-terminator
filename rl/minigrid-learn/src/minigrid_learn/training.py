from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecTransposeImage

from minigrid_learn.artifacts import RunPaths
from minigrid_learn.callbacks import PeriodicEvaluationCallback, RolloutMetricsCallback
from minigrid_learn.config import (
    EnvironmentConfig,
    Phase1Config,
    TrainingConfig,
    save_run_config,
)
from minigrid_learn.envs import make_minigrid_env
from minigrid_learn.policy import MiniGridCNN


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_vec_env(env_id: str, seed: int, monitor_path: Path | None = None):
    vec_env = DummyVecEnv([lambda: make_minigrid_env(env_id, seed=seed, monitor_path=monitor_path)])
    return VecTransposeImage(vec_env)


def _with_overrides(training: TrainingConfig, overrides: dict[str, Any]) -> TrainingConfig:
    accepted = {key: value for key, value in overrides.items() if value is not None}
    return replace(training, **accepted)


def train_run(
    config: Phase1Config,
    environment: EnvironmentConfig,
    seed: int,
    *,
    total_timesteps: int | None = None,
    smoke: bool = False,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if total_timesteps is not None:
        overrides["total_timesteps"] = total_timesteps
    if smoke:
        smoke_steps = total_timesteps or 512
        overrides.update(
            total_timesteps=smoke_steps,
            n_steps=min(128, smoke_steps),
            batch_size=min(64, smoke_steps),
            n_epochs=2,
            eval_freq=max(128, smoke_steps // 2),
            n_eval_episodes=2,
            checkpoint_freq=max(128, smoke_steps),
            consecutive_threshold_evals=100,
        )
    training = _with_overrides(config.training, overrides)

    artifact_root = (
        config.project.artifact_root / "smoke" if smoke else config.project.artifact_root
    )
    paths = RunPaths.create(artifact_root, environment.slug, seed)
    for csv_path in (paths.metrics, paths.evaluations):
        if csv_path.exists():
            csv_path.unlink()
    save_run_config(config, environment, seed, paths.config, overrides)
    set_global_seed(seed)

    train_env = make_vec_env(environment.id, seed, paths.monitor)
    eval_env = make_vec_env(environment.id, seed + 10_000)
    policy_kwargs = {
        "features_extractor_class": MiniGridCNN,
        "features_extractor_kwargs": {"features_dim": config.policy.features_dim},
        "normalize_images": True,
    }
    model = PPO(
        "CnnPolicy",
        train_env,
        learning_rate=training.learning_rate,
        n_steps=training.n_steps,
        batch_size=training.batch_size,
        n_epochs=training.n_epochs,
        gamma=training.gamma,
        gae_lambda=training.gae_lambda,
        clip_range=training.clip_range,
        ent_coef=training.ent_coef,
        vf_coef=training.vf_coef,
        max_grad_norm=training.max_grad_norm,
        policy_kwargs=policy_kwargs,
        tensorboard_log=str(paths.tensorboard),
        seed=seed,
        device=training.device,
        verbose=1,
    )

    metrics_callback = RolloutMetricsCallback(paths.metrics)
    evaluation_callback = PeriodicEvaluationCallback(
        eval_env=eval_env,
        output_path=paths.evaluations,
        best_model_dir=paths.best_model,
        eval_freq=training.eval_freq,
        n_eval_episodes=training.n_eval_episodes,
        reward_threshold=environment.reward_threshold,
        required_streak=training.consecutive_threshold_evals,
    )
    checkpoint_callback = CheckpointCallback(
        save_freq=training.checkpoint_freq,
        save_path=str(paths.checkpoints),
        name_prefix="ppo",
    )

    started_at = time.monotonic()
    model.learn(
        total_timesteps=training.total_timesteps,
        callback=CallbackList([metrics_callback, evaluation_callback, checkpoint_callback]),
        tb_log_name=f"{environment.slug}_seed-{seed}",
        progress_bar=False,
    )
    elapsed_seconds = time.monotonic() - started_at
    model.save(paths.root / "final_model")
    actual_timesteps = model.num_timesteps
    train_env.close()

    status = (
        "threshold_reached" if evaluation_callback.threshold_reached else "maximum_steps_reached"
    )
    if smoke:
        status = "smoke_completed"
    summary = {
        "environment_id": environment.id,
        "environment_slug": environment.slug,
        "seed": seed,
        "status": status,
        "timesteps": actual_timesteps,
        "configured_max_timesteps": training.total_timesteps,
        "elapsed_seconds": elapsed_seconds,
        "best_mean_reward": (
            evaluation_callback.best_mean_reward
            if np.isfinite(evaluation_callback.best_mean_reward)
            else None
        ),
        "final_mean_reward": (
            evaluation_callback.last_mean_reward
            if np.isfinite(evaluation_callback.last_mean_reward)
            else None
        ),
        "reward_threshold": environment.reward_threshold,
        "threshold_streak": evaluation_callback.threshold_streak,
        "device": str(model.device),
        "training": asdict(training),
        "artifacts": {
            "root": str(paths.root),
            "best_model": str(paths.best_model / "best_model.zip"),
            "final_model": str(paths.root / "final_model.zip"),
            "tensorboard": str(paths.tensorboard),
            "metrics": str(paths.metrics),
            "evaluations": str(paths.evaluations),
        },
    }
    paths.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def train_all(
    config: Phase1Config,
    *,
    total_timesteps: int | None = None,
    smoke: bool = False,
) -> list[dict[str, Any]]:
    return [
        train_run(
            config,
            environment,
            seed,
            total_timesteps=total_timesteps,
            smoke=smoke,
        )
        for environment in config.environments
        for seed in config.seeds
    ]
