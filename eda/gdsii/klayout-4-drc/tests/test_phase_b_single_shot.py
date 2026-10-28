"""Integration tests for Phase B single-shot pipeline on authentic ASAP7 layouts."""

import os
from pathlib import Path
import pytest

from klayout_drc.config import DEFAULT_RULES_DIR
from klayout_drc.profile import DRCProfileManager
from klayout_drc.run_manifest import RunSpec
from klayout_drc.run_reporter import VERDICT_SUCCESS_GEOMETRY_ONLY
from klayout_drc.single_shot import SingleShotOrchestrator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "test_data" / "layouts" / "asap7_beol_v1"
CURATED_DECK = DEFAULT_RULES_DIR / "asap7_curated.lydrc"


def test_phase_b_single_shot_known_script(tmp_path: Path):
    """Test SingleShotOrchestrator on m1_w1_illegal_bound.gds with a deterministic repair script."""
    input_gds = FIXTURES_DIR / "m1_w1_illegal_bound.gds"
    fix_script = tmp_path / "fix_m1_width.py"
    fix_script.write_text(
        "import sys, pya\n"
        "layout = pya.Layout()\n"
        "layout.read(sys.argv[1])\n"
        "top = layout.top_cell()\n"
        "layer_m1 = layout.layer(19, 0)\n"
        "reg = pya.Region(top.shapes(layer_m1))\n"
        "reg = reg.sized(1)\n"  # Size by 1 DBU (0.25 nm per side) -> 17.75 + 0.5 = 18.25 nm >= 18 nm
        "top.shapes(layer_m1).clear()\n"
        "top.shapes(layer_m1).insert(reg)\n"
        "layout.write(sys.argv[2])\n",
        encoding="utf-8",
    )

    spec = RunSpec(
        case_name="test_phase_b_script",
        input_gds=input_gds,
        drc_script=CURATED_DECK,
        profile_name="asap7_curated",
        candidate_mode="script_file",
        candidate_script=fix_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_SUCCESS_GEOMETRY_ONLY
    assert summary.total_before == 1
    assert summary.total_after == 0
    assert "M1.W.1" in summary.violations_before
    assert summary.diff_report is not None
    assert (19, 0) in summary.diff_report.modified_layers

    # Ensure artifacts exist
    assert orchestrator.paths.results_json.exists()
    assert orchestrator.paths.report_md.exists()
    assert orchestrator.paths.run_manifest_json.exists()


def test_phase_b_single_shot_agent_live_or_blocked(tmp_path: Path):
    """Run live agent evaluation on ASAP7 boundary fixture if OPENAI_API_KEY is available."""
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
    if not os.environ.get("KLAYOUT_DRC_RUN_LIVE_TESTS"):
        pytest.skip("Live tests require KLAYOUT_DRC_RUN_LIVE_TESTS=1")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not configured; skipping live agent call.")

    input_gds = FIXTURES_DIR / "m1_w1_illegal_bound.gds"
    spec = RunSpec(
        case_name="test_phase_b_agent",
        input_gds=input_gds,
        drc_script=CURATED_DECK,
        profile_name="asap7_curated",
        candidate_mode="agent",
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.execution_result.status not in ("model_error", "blocked")
    assert (orchestrator.paths.run_dir / "model_response.json").exists()
    assert (orchestrator.paths.run_dir / "generation_manifest.json").exists()
    assert orchestrator.paths.results_json.exists()
    assert orchestrator.paths.report_md.exists()
