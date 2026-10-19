"""Integration tests for the KLayout DRC pipeline."""

from pathlib import Path
import pytest

from klayout_drc.config import (
    DEFAULT_LAYOUTS_DIR,
    DEFAULT_RULES_DIR,
    DRCConfigurationError,
)
from klayout_drc.cli import run_pipeline
from klayout_drc.fixer import DRCFixer


@pytest.fixture
def sample_gds_path() -> Path:
    """Path to the test layout with intentional violations."""
    return DEFAULT_LAYOUTS_DIR / "asap7_test.gds"


@pytest.fixture
def sample_drc_path() -> Path:
    """Path to the ASAP7 mini DRC rule deck."""
    return DEFAULT_RULES_DIR / "asap7_mini.drc"


def test_drc_pipeline_violations_detected(tmp_path: Path, sample_gds_path: Path, sample_drc_path: Path) -> None:
    """Test that DRC execution correctly identifies the 8 intentional violations."""
    out_lyrdb = tmp_path / "violations.lyrdb"
    out_text = tmp_path / "report.txt"

    result = run_pipeline(
        input_gds=sample_gds_path,
        drc_script=sample_drc_path,
        output_lyrdb=out_lyrdb,
        text_report_path=out_text,
    )

    assert result["status"] == "success"
    assert result["total_violations"] == 8
    assert result["rule_summary"] == {
        "M1_W": 1,
        "M1_S": 1,
        "V1_M1_ENC": 6,
    }
    assert out_lyrdb.exists()
    assert out_text.exists()
    assert "Rule: M1_W - M1 minimum width is 18nm" in result["textual_report"]
    assert "Rule: M1_S - M1 minimum spacing is 18nm" in result["textual_report"]
    assert "Rule: V1_M1_ENC - V1 minimum enclosure by M1 is 9nm" in result["textual_report"]


def test_drc_pipeline_and_fixer_zero_violations(
    tmp_path: Path, sample_gds_path: Path, sample_drc_path: Path
) -> None:
    """Test that fixing the layout programmatically reduces violations to zero."""
    fixed_gds = tmp_path / "fixed_asap7.gds"
    fixer = DRCFixer(input_gds=sample_gds_path, output_gds=fixed_gds)
    fixer.fix()
    assert fixed_gds.exists()

    out_lyrdb = tmp_path / "fixed_violations.lyrdb"
    out_text = tmp_path / "fixed_report.txt"

    result = run_pipeline(
        input_gds=fixed_gds,
        drc_script=sample_drc_path,
        output_lyrdb=out_lyrdb,
        text_report_path=out_text,
    )

    assert result["status"] == "success"
    assert result["total_violations"] == 0
    assert result["rule_summary"] == {}
    assert "No DRC violations found" in result["textual_report"]


def test_drc_pipeline_missing_gds_fails_early(tmp_path: Path, sample_drc_path: Path) -> None:
    """Test that missing GDS file raises DRCConfigurationError early."""
    missing_gds = tmp_path / "non_existent.gds"
    out_lyrdb = tmp_path / "report.lyrdb"

    with pytest.raises(DRCConfigurationError, match="Input GDS file does not exist"):
        run_pipeline(
            input_gds=missing_gds,
            drc_script=sample_drc_path,
            output_lyrdb=out_lyrdb,
        )
