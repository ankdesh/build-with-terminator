from minigrid_learn.artifacts import RunPaths


def test_run_artifact_layout(tmp_path) -> None:
    paths = RunPaths.create(tmp_path, "empty-8x8", 2)
    assert paths.root == tmp_path / "empty-8x8" / "seed-2"
    assert paths.checkpoints.is_dir()
    assert paths.best_model.is_dir()
    assert paths.tensorboard.is_dir()
