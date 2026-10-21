"""Integration tests for authentic ASAP7 profiles and deck parameter binding (PR B-1).

Validates that:
1. DRCProfileManager provides legacy_mini, asap7_curated, and asap7_public_full.
2. Authentic ASAP7 profiles use correct layer maps (V0=18/0, M1=19/0, M2=20/0, V1=21/0).
3. Deck parameter adapters (in_gds/report_file) correctly pass to KLayout.
4. Headless KLayout runs against both asap7_curated.lydrc and asap7.lydrc to generate valid .lyrdb files.
"""

from pathlib import Path
import pya
import pytest

from klayout_drc.config import (
    ASAP7_LAYER_M1,
    ASAP7_LAYER_V0,
    ASAP7_LAYER_M2,
    ASAP7_LAYER_V1,
    DRCJobConfig,
)
from klayout_drc.profile import DRCProfileManager
from klayout_drc.runner import DRCRunner
from klayout_drc.parser import DRCParser


def create_asap7_smoke_gds(output_path: Path, dbu_um: float = 0.00025) -> None:
    """Create a minimal ASAP7 GDS layout on layer M1 (19/0) with deliberate narrow width violation."""
    layout = pya.Layout()
    layout.dbu = dbu_um
    top_cell = layout.create_cell("TOP")

    # M1 is layer 19, datatype 0 in authentic ASAP7
    layer_m1 = layout.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])

    # Insert a 10 nm wide M1 rectangle (10 nm < 18 nm threshold)
    # Physical coordinates: x in [0, 0.010] um, y in [0, 0.100] um
    x1 = int(round(0.0 / dbu_um))
    y1 = int(round(0.0 / dbu_um))
    x2 = int(round(0.010 / dbu_um))
    y2 = int(round(0.100 / dbu_um))

    box = pya.Box(x1, y1, x2, y2)
    top_cell.shapes(layer_m1).insert(box)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_path))


def test_asap7_profiles_registered():
    """Verify that all three expected profiles are registered and valid."""
    mgr = DRCProfileManager()
    profiles = mgr.list_profiles()

    assert "legacy_mini" in profiles
    assert "asap7_curated" in profiles
    assert "asap7_public_full" in profiles

    legacy = mgr.get_profile("legacy_mini")
    assert legacy.param_in_gds == "input"
    assert legacy.param_report == "report"
    assert legacy.layers["M1"] == (18, 0)
    assert legacy.layers["V1"] == (19, 0)
    legacy.validate()

    curated = mgr.get_profile("asap7_curated")
    assert curated.param_in_gds == "in_gds"
    assert curated.param_report == "report_file"
    assert curated.layers["V0"] == ASAP7_LAYER_V0
    assert curated.layers["M1"] == ASAP7_LAYER_M1
    assert curated.layers["M2"] == ASAP7_LAYER_M2
    assert curated.layers["V1"] == ASAP7_LAYER_V1
    assert curated.dbu_um == 0.00025
    curated.validate()

    public_full = mgr.get_profile("asap7_public_full")
    assert public_full.param_in_gds == "in_gds"
    assert public_full.param_report == "report_file"
    assert public_full.layers["V0"] == ASAP7_LAYER_V0
    assert public_full.layers["M1"] == ASAP7_LAYER_M1
    assert public_full.layers["M2"] == ASAP7_LAYER_M2
    assert public_full.layers["V1"] == ASAP7_LAYER_V1
    assert public_full.dbu_um == 0.00025
    public_full.validate()


def test_asap7_curated_deck_execution(tmp_path: Path):
    """Verify that asap7_curated.lydrc executes via DRCRunner and detects M1.W.1."""
    smoke_gds = tmp_path / "smoke_asap7.gds"
    create_asap7_smoke_gds(smoke_gds, dbu_um=0.00025)

    mgr = DRCProfileManager()
    profile = mgr.get_profile("asap7_curated")

    out_lyrdb = tmp_path / "curated_smoke.lyrdb"
    job_cfg = DRCJobConfig(
        input_gds=smoke_gds,
        drc_script=profile.deck_path,
        output_lyrdb=out_lyrdb,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
    )

    runner = DRCRunner(job_cfg)
    generated_lyrdb = runner.run()

    assert generated_lyrdb.exists()
    assert generated_lyrdb.stat().st_size > 0

    # Parse with DRCParser and verify M1.W.1 is detected
    parser = DRCParser()
    summary = parser.parse(generated_lyrdb)
    assert summary.total_violations > 0
    categories = [cat.name for cat in summary.categories]
    assert "M1.W.1" in categories


def test_asap7_public_full_deck_execution(tmp_path: Path):
    """Verify that the full pinned asap7.lydrc executes via DRCRunner on smoke layout."""
    smoke_gds = tmp_path / "smoke_asap7_full.gds"
    create_asap7_smoke_gds(smoke_gds, dbu_um=0.00025)

    mgr = DRCProfileManager()
    profile = mgr.get_profile("asap7_public_full")

    out_lyrdb = tmp_path / "full_smoke.lyrdb"
    job_cfg = DRCJobConfig(
        input_gds=smoke_gds,
        drc_script=profile.deck_path,
        output_lyrdb=out_lyrdb,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
    )

    runner = DRCRunner(job_cfg)
    generated_lyrdb = runner.run()

    assert generated_lyrdb.exists()
    assert generated_lyrdb.stat().st_size > 0

    parser = DRCParser()
    summary = parser.parse(generated_lyrdb)
    assert summary.total_violations > 0
    categories = [cat.name for cat in summary.categories]
    assert "M1.W.1" in categories
