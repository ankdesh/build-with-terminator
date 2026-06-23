from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.vec_env import VecEnv


def _append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


class RolloutMetricsCallback(BaseCallback):
    """Persist learning diagnostics independently of TensorBoard."""

    def __init__(self, output_path: Path, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.output_path = output_path
        self.started_at = time.monotonic()

    def _on_step(self) -> bool:
        return True

    def _policy_entropy(self) -> float:
        observations = self.model.rollout_buffer.observations
        flat = observations.reshape((-1, *observations.shape[2:]))
        if len(flat) > 2048:
            indices = np.linspace(0, len(flat) - 1, 2048, dtype=int)
            flat = flat[indices]
        obs_tensor = torch.as_tensor(flat, device=self.model.device)
        with torch.no_grad():
            distribution = self.model.policy.get_distribution(obs_tensor)
            entropy = distribution.entropy()
        return float(entropy.mean().cpu().item())

    def _on_rollout_end(self) -> None:
        logger_values = self.model.logger.name_to_value
        episodes = list(self.model.ep_info_buffer)
        policy_entropy = self._policy_entropy()
        self.logger.record("rollout/policy_entropy", policy_entropy)

        row = {
            "timesteps": self.num_timesteps,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 3),
            "episode_reward_mean": (
                float(np.mean([episode["r"] for episode in episodes])) if episodes else np.nan
            ),
            "episode_length_mean": (
                float(np.mean([episode["l"] for episode in episodes])) if episodes else np.nan
            ),
            "policy_entropy": policy_entropy,
            "entropy_loss": logger_values.get("train/entropy_loss", np.nan),
            "policy_gradient_loss": logger_values.get("train/policy_gradient_loss", np.nan),
            "value_loss": logger_values.get("train/value_loss", np.nan),
            "approx_kl": logger_values.get("train/approx_kl", np.nan),
            "clip_fraction": logger_values.get("train/clip_fraction", np.nan),
            "explained_variance": logger_values.get("train/explained_variance", np.nan),
            "learning_rate": logger_values.get("train/learning_rate", np.nan),
        }
        _append_csv(self.output_path, row)


class PeriodicEvaluationCallback(BaseCallback):
    """Evaluate, save the best policy, and stop after a sustained threshold."""

    def __init__(
        self,
        eval_env: VecEnv,
        output_path: Path,
        best_model_dir: Path,
        eval_freq: int,
        n_eval_episodes: int,
        reward_threshold: float,
        required_streak: int,
        verbose: int = 1,
    ) -> None:
        super().__init__(verbose)
        self.eval_env = eval_env
        self.output_path = output_path
        self.best_model_dir = best_model_dir
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.reward_threshold = reward_threshold
        self.required_streak = required_streak
        self.threshold_streak = 0
        self.threshold_reached = False
        self.best_mean_reward = -np.inf
        self.last_mean_reward = np.nan

    def _on_step(self) -> bool:
        if self.n_calls % self.eval_freq != 0:
            return True

        rewards, lengths = evaluate_policy(
            self.model,
            self.eval_env,
            n_eval_episodes=self.n_eval_episodes,
            deterministic=True,
            return_episode_rewards=True,
            warn=False,
        )
        rewards_array = np.asarray(rewards, dtype=float)
        lengths_array = np.asarray(lengths, dtype=float)
        mean_reward = float(rewards_array.mean())
        self.last_mean_reward = mean_reward
        success_rate = float(np.mean(rewards_array > 0.0))

        if mean_reward >= self.reward_threshold:
            self.threshold_streak += 1
        else:
            self.threshold_streak = 0

        row = {
            "timesteps": self.num_timesteps,
            "mean_reward": mean_reward,
            "std_reward": float(rewards_array.std()),
            "mean_episode_length": float(lengths_array.mean()),
            "std_episode_length": float(lengths_array.std()),
            "success_rate": success_rate,
            "reward_threshold": self.reward_threshold,
            "threshold_streak": self.threshold_streak,
            "n_eval_episodes": self.n_eval_episodes,
        }
        _append_csv(self.output_path, row)

        self.logger.record("eval/mean_reward", mean_reward)
        self.logger.record("eval/mean_ep_length", float(lengths_array.mean()))
        self.logger.record("eval/success_rate", success_rate)
        self.logger.record("eval/threshold_streak", self.threshold_streak)

        if mean_reward > self.best_mean_reward:
            self.best_mean_reward = mean_reward
            self.model.save(self.best_model_dir / "best_model")

        if self.verbose:
            print(
                f"Eval at {self.num_timesteps}: reward={mean_reward:.3f} "
                f"success={success_rate:.1%} streak={self.threshold_streak}/{self.required_streak}"
            )

        if self.threshold_streak >= self.required_streak:
            self.threshold_reached = True
            if self.verbose:
                print("Sustained reward threshold reached; stopping training.")
            return False
        return True

    def _on_training_end(self) -> None:
        self.eval_env.close()
