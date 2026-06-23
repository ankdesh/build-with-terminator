from __future__ import annotations

from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy

from minigrid_learn.training import make_vec_env


def evaluate_saved_model(
    model_path: str | Path,
    env_id: str,
    *,
    seed: int = 10_000,
    n_episodes: int = 20,
) -> dict[str, float | int]:
    env = make_vec_env(env_id, seed)
    model = PPO.load(model_path, env=env)
    rewards, lengths = evaluate_policy(
        model,
        env,
        n_eval_episodes=n_episodes,
        deterministic=True,
        return_episode_rewards=True,
        warn=False,
    )
    env.close()
    reward_array = np.asarray(rewards, dtype=float)
    length_array = np.asarray(lengths, dtype=float)
    return {
        "episodes": n_episodes,
        "mean_reward": float(reward_array.mean()),
        "std_reward": float(reward_array.std()),
        "mean_episode_length": float(length_array.mean()),
        "success_rate": float(np.mean(reward_array > 0.0)),
    }
