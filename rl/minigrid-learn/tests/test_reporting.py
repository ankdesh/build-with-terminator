from dataclasses import replace

from minigrid_learn.config import ProjectConfig, load_config
from minigrid_learn.reporting import PLOT_FILES, generate_report


def test_report_generation_and_portable_image_links(tmp_path) -> None:
    config = load_config()
    config = replace(
        config,
        project=ProjectConfig(
            artifact_root=tmp_path / "artifacts",
            report_root=tmp_path / "reports",
        ),
    )
    report_path = generate_report(config)
    markdown = report_path.read_text(encoding="utf-8")
    for filename in PLOT_FILES:
        assert f"](plots/{filename})" in markdown
        assert (config.project.report_root / "plots" / filename).is_file()
    assert (config.project.report_root / "data" / "run_metrics.csv").is_file()
    assert (config.project.report_root / "data" / "evaluation_metrics.csv").is_file()
    assert (config.project.report_root / "data" / "summary.json").is_file()
