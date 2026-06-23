from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gymnasium as gym
from minigrid.wrappers import ImgObsWrapper
from stable_baselines3.common.monitor import Monitor

EnvironmentFactory = Callable[[str, int, Path | None], gym.Env]


def make_minigrid_env(
    env_id: str,
    seed: int,
    monitor_path: Path | None = None,
    render_mode: str | None = None,
) -> gym.Env:
    """Create a single image-observation MiniGrid environment.

    The factory boundary is intentionally narrow so later phases can replace it
    with vectorized, recurrent, or curriculum-aware factories.
    """
    env = gym.make(env_id, render_mode=render_mode)
    env = ImgObsWrapper(env)
    if monitor_path is not None:
        monitor_path.parent.mkdir(parents=True, exist_ok=True)
        env = Monitor(env, filename=str(monitor_path), info_keywords=())
    else:
        env = Monitor(env)
    env.reset(seed=seed)
    env.action_space.seed(seed)
    return env
