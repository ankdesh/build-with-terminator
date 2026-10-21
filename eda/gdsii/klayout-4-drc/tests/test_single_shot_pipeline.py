"""Integration tests for the single-shot Fix -> Apply Patch -> Report pipeline."""

import os
from pathlib import Path
import pytest

from klayout_drc.config import (
    DEFAULT_LAYOUTS_DIR,
    DEFAULT_RULES_DIR,
)
from klayout_drc.run_manifest import RunSpec
from klayout_drc.single_shot import SingleShotOrchestrator
from klayout_drc.run_reporter import (
    VERDICT_SUCCESS_GEOMETRY_ONLY,
    VERDICT_NO_CHANGE,
    VERDICT_PARTIAL,
)

FIXTURES_DIR = DEFAULT_LAYOUTS_DIR / "legacy_mini_v2"
KNOWN_GOOD_SCRIPT = Path(__file__).resolve().parent / "fixtures" / "known_good_mini_fix.py"
MINI_DECK = DEFAULT_RULES_DIR / "asap7_mini.drc"
SAMPLE_GDS = DEFAULT_LAYOUTS_DIR / "asap7_test.gds"


def test_single_shot_injected_known_good_script(tmp_path: Path) -> None:
    """Test A1.1: Single-shot evaluation using injected known-good script fixes all 8 violations."""
    spec = RunSpec(
        case_name="test_a1_1_injected_script",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=KNOWN_GOOD_SCRIPT,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_SUCCESS_GEOMETRY_ONLY
    assert summary.validation_level == "geometry_only"
    assert summary.total_before == 8
    assert summary.total_after == 0
    assert summary.violations_after == {}
    assert summary.execution_result.status == "success"
    assert summary.validation_result is not None
    assert summary.validation_result.is_valid is True

    # Assert all 10 standard artifacts exist in run directory
    paths = orchestrator.paths
    assert paths.run_dir.exists()
    assert paths.input_gds.exists()
    assert paths.before_lyrdb.exists()
    assert paths.candidate_script.exists()
    assert paths.candidate_stdout.exists()
    assert paths.candidate_stderr.exists()
    assert paths.patched_gds.exists()
    assert paths.after_lyrdb.exists()
    assert paths.layout_diff_json.exists()
    assert paths.results_json.exists()
    assert paths.report_md.exists()


def test_single_shot_heuristic_baseline(tmp_path: Path) -> None:
    """Test A1.2: Deterministic heuristic baseline heals all violations."""
    spec = RunSpec(
        case_name="test_a1_2_heuristic",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="heuristic",
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_SUCCESS_GEOMETRY_ONLY
    assert summary.total_before == 8
    assert summary.total_after == 0
    assert summary.execution_result.status == "success"
    assert summary.validation_result is not None
    assert summary.validation_result.is_valid is True


def test_single_shot_agent_live_or_blocked(tmp_path: Path) -> None:
    """Test A1.3: Real LLM agent execution via DSH (or truthful model_error if no key)."""
    spec = RunSpec(
        case_name="test_a1_3_agent",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="agent",
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    has_key = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
    if has_key:
        # Live LLM execution must run and record truthful status and diagnostics
        assert summary.verdict in (
            VERDICT_SUCCESS_GEOMETRY_ONLY,
            VERDICT_PARTIAL,
            "invalid_patch",
        )
        assert summary.execution_result.status in ("success", "nonzero_exit")
        assert orchestrator.paths.results_json.exists()
        assert orchestrator.paths.report_md.exists()
    else:
        # Without credentials, pipeline must record model_error without silent fallback
        assert summary.verdict == "model_error"
        assert summary.execution_result.status == "model_error"


def test_single_shot_clean_layout_no_change(tmp_path: Path) -> None:
    """Test A-OK-1: Clean layout requires no changes and yields no_change."""
    clean_gds = FIXTURES_DIR / "a_ok_1_clean.gds"
    spec = RunSpec(
        case_name="test_a_ok_1",
        input_gds=clean_gds,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="heuristic",
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.total_before == 0
    assert summary.total_after == 0
    assert summary.verdict in (VERDICT_SUCCESS_GEOMETRY_ONLY, VERDICT_NO_CHANGE)


def test_single_shot_isolated_fixtures(tmp_path: Path) -> None:
    """Test isolated Phase A fixtures A-W-1, A-S-1, A-E-1 with heuristic repair."""
    cases = [
        ("A-W-1", FIXTURES_DIR / "a_w_1_min_width.gds", "M1_W"),
        ("A-S-1", FIXTURES_DIR / "a_s_1_min_spacing.gds", "M1_S"),
        ("A-E-1", FIXTURES_DIR / "a_e_1_via_enclosure.gds", "V1_M1_ENC"),
    ]

    for name, gds_path, rule_key in cases:
        spec = RunSpec(
            case_name=f"test_{name.lower().replace('-', '_')}",
            input_gds=gds_path,
            drc_script=MINI_DECK,
            profile_name="legacy_mini",
            candidate_mode="heuristic",
            output_root=tmp_path,
        )
        orchestrator = SingleShotOrchestrator(spec)
        summary = orchestrator.run()

        assert rule_key in summary.violations_before
        assert summary.total_after == 0
        assert summary.verdict == VERDICT_SUCCESS_GEOMETRY_ONLY
