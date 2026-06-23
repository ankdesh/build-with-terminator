from pathlib import Path

from minigrid_learn.evaluation import evaluate_saved_model


def test_evaluation_api_is_exposed() -> None:
    assert callable(evaluate_saved_model)
    assert Path("unused.zip").suffix == ".zip"
