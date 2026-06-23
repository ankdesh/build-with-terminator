from pathlib import Path

import pytest

from minigrid_learn.config import load_config


def test_phase1_config_loads() -> None:
    config = load_config()
    assert config.seeds == (0, 1, 2)
    assert len(config.environments) == 2
    assert config.training.total_timesteps == 500_000
    assert config.project.report_root == Path("reports/phase1")


def test_environment_accepts_slug_or_id() -> None:
    config = load_config()
    environment = config.environment("empty-8x8")
    assert config.environment(environment.id) == environment
    with pytest.raises(ValueError, match="Unknown environment"):
        config.environment("missing")
