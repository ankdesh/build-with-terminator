from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    root: Path
    checkpoints: Path
    best_model: Path
    tensorboard: Path
    monitor: Path
    evaluations: Path
    metrics: Path
    config: Path
    summary: Path

    @classmethod
    def create(cls, artifact_root: Path, env_slug: str, seed: int) -> RunPaths:
        root = artifact_root / env_slug / f"seed-{seed}"
        paths = cls(
            root=root,
            checkpoints=root / "checkpoints",
            best_model=root / "best_model",
            tensorboard=root / "tensorboard",
            monitor=root / "monitor.csv",
            evaluations=root / "evaluations.csv",
            metrics=root / "run_metrics.csv",
            config=root / "config.json",
            summary=root / "summary.json",
        )
        for directory in (
            paths.root,
            paths.checkpoints,
            paths.best_model,
            paths.tensorboard,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return paths
