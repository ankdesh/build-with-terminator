"""Comprehensive integration test suite for ASAP7 BEOL 4-case boundary matrix (PR B-4).

Tests 5 core BEOL rule families across 4 boundary conditions using asap7_curated.lydrc:
  - M1.W.1 (Width 18nm)
  - M2.W.1 (Width 18nm)
  - M1.A.1 (Area 504nm2)
  - M1.S.1 (Spacing 18nm for parallel run > 36nm)
  - V1.W.1 (Width 18nm)
Plus 1 compound interaction testcase.
"""

from pathlib import Path
import pytest

from klayout_drc.config import DRCJobConfig
from klayout_drc.parser import DRCParser
from klayout_drc.profile import DRCProfileManager
from klayout_drc.runner import DRCRunner

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "test_data" / "layouts" / "asap7_beol_v1"


def run_curated_drc(gds_path: Path, tmp_path: Path) -> dict[str, int]:
    """Helper to run asap7_curated.lydrc on a layout and return category violation counts."""
    mgr = DRCProfileManager()
    profile = mgr.get_profile("asap7_curated")
    out_rdb = tmp_path / f"{gds_path.stem}.lyrdb"

    cfg = DRCJobConfig(
        input_gds=gds_path,
        drc_script=profile.deck_path,
        output_lyrdb=out_rdb,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
    )
    runner = DRCRunner(cfg)
    runner.run()

    parser = DRCParser()
    data = parser.parse(out_rdb)
    return {c.name: c.count for c in data.categories if c.count > 0}


# Parameterized test matrix for all 5 rule families
@pytest.mark.parametrize(
    "rule_family,legal_file,legal_bound_file,illegal_bound_file,clearly_illegal_file",
    [
        (
            "M1.W.1",
            "m1_w1_legal.gds",
            "m1_w1_legal_bound.gds",
            "m1_w1_illegal_bound.gds",
            "m1_w1_clearly_illegal.gds",
        ),
        (
            "M2.W.1",
            "m2_w1_legal.gds",
            "m2_w1_legal_bound.gds",
            "m2_w1_illegal_bound.gds",
            "m2_w1_clearly_illegal.gds",
        ),
        (
            "M1.A.1",
            "m1_a1_legal.gds",
            "m1_a1_legal_bound.gds",
            "m1_a1_illegal_bound.gds",
            "m1_a1_clearly_illegal.gds",
        ),
        (
            "M1.S.1",
            "m1_s1_legal.gds",
            "m1_s1_legal_bound.gds",
            "m1_s1_illegal_bound.gds",
            "m1_s1_clearly_illegal.gds",
        ),
        (
            "V1.W.1",
            "v1_w1_legal.gds",
            "v1_w1_legal_bound.gds",
            "v1_w1_illegal_bound.gds",
            "v1_w1_clearly_illegal.gds",
        ),
    ],
)
def test_beol_rule_boundary_matrix(
    rule_family: str,
    legal_file: str,
    legal_bound_file: str,
    illegal_bound_file: str,
    clearly_illegal_file: str,
    tmp_path: Path,
):
    """Verify that legal cases produce 0 violations and illegal cases produce the exact violation."""
    # Case 1: Legal (Wide Margin) -> 0 violations
    res_legal = run_curated_drc(FIXTURES_DIR / legal_file, tmp_path / "c1")
    assert res_legal == {}, f"Expected 0 violations for {legal_file}, got {res_legal}"

    # Case 2: Legal Boundary (Exact Threshold) -> 0 violations
    res_legal_bound = run_curated_drc(FIXTURES_DIR / legal_bound_file, tmp_path / "c2")
    assert res_legal_bound == {}, f"Expected 0 violations for {legal_bound_file}, got {res_legal_bound}"

    # Case 3: Illegal Boundary (-1 Grid Step: -0.25 nm) -> Violation detected
    res_illegal_bound = run_curated_drc(FIXTURES_DIR / illegal_bound_file, tmp_path / "c3")
    assert res_illegal_bound == {rule_family: (2 if rule_family == "V1.W.1" else 1)}, f"Expected {rule_family} violation for {illegal_bound_file}, got {res_illegal_bound}"

    # Case 4: Clearly Illegal (Gross Defect) -> Violation detected
    res_clearly_illegal = run_curated_drc(FIXTURES_DIR / clearly_illegal_file, tmp_path / "c4")
    assert res_clearly_illegal == {rule_family: (2 if rule_family == "V1.W.1" else 1)}, f"Expected {rule_family} violation for {clearly_illegal_file}, got {res_clearly_illegal}"


def test_compound_beol_interaction(tmp_path: Path):
    """Verify compound interaction case simultaneously triggers M1.W.1, M1.S.1, and V1.W.1."""
    compound_gds = FIXTURES_DIR / "compound_beol_interaction.gds"
    results = run_curated_drc(compound_gds, tmp_path)

    assert "M1.W.1" in results, f"Expected M1.W.1 in compound results: {results}"
    assert "M1.S.1" in results, f"Expected M1.S.1 in compound results: {results}"
    assert "V1.W.1" in results, f"Expected V1.W.1 in compound results: {results}"
    assert results["M1.W.1"] > 0
    assert results["M1.S.1"] > 0
    assert results["V1.W.1"] > 0
