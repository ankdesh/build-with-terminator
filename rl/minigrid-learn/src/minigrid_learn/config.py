from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EnvironmentConfig:
    id: str
    slug: str
    reward_threshold: float


@dataclass(frozen=True)
class TrainingConfig:
    total_timesteps: int
    learning_rate: float
    n_steps: int
    batch_size: int
    n_epochs: int
    gamma: float
    gae_lambda: float
    clip_range: float
    ent_coef: float
    vf_coef: float
    max_grad_norm: float
    eval_freq: int
    n_eval_episodes: int
    checkpoint_freq: int
    consecutive_threshold_evals: int
    device: str


@dataclass(frozen=True)
class PolicyConfig:
    features_dim: int


@dataclass(frozen=True)
class ProjectConfig:
    artifact_root: Path
    report_root: Path


@dataclass(frozen=True)
class Phase1Config:
    project: ProjectConfig
    training: TrainingConfig
    policy: PolicyConfig
    environments: tuple[EnvironmentConfig, ...]
    seeds: tuple[int, ...]
    source_path: Path

    def environment(self, value: str) -> EnvironmentConfig:
        for environment in self.environments:
            if value in (environment.id, environment.slug):
                return environment
        choices = ", ".join(environment.slug for environment in self.environments)
        raise ValueError(f"Unknown environment {value!r}; choose one of: {choices}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["project"]["artifact_root"] = str(self.project.artifact_root)
        data["project"]["report_root"] = str(self.project.report_root)
        data["source_path"] = str(self.source_path)
        return data


def load_config(path: str | Path = "configs/phase1.toml") -> Phase1Config:
    source_path = Path(path)
    with source_path.open("rb") as handle:
        raw = tomllib.load(handle)

    return Phase1Config(
        project=ProjectConfig(
            artifact_root=Path(raw["project"]["artifact_root"]),
            report_root=Path(raw["project"]["report_root"]),
        ),
        training=TrainingConfig(**raw["training"]),
        policy=PolicyConfig(**raw["policy"]),
        environments=tuple(EnvironmentConfig(**item) for item in raw["environments"]),
        seeds=tuple(raw["experiments"]["seeds"]),
        source_path=source_path,
    )


def save_run_config(
    config: Phase1Config,
    environment: EnvironmentConfig,
    seed: int,
    path: Path,
    overrides: dict[str, Any] | None = None,
) -> None:
    payload = config.to_dict()
    payload["selected_environment"] = asdict(environment)
    payload["selected_seed"] = seed
    payload["overrides"] = overrides or {}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
