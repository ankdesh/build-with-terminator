"""Negative tests and failure matrix for layout repair patches.

Verifies that the single-shot pipeline fails explicitly and early for:
- Syntax errors in candidate script
- Non-zero process exit codes / runtime exceptions
- Execution timeouts
- Missing or empty output GDS files
- Destructive layout edits (deleting all geometry)
- No-op scripts that resolve nothing
- Invalid/corrupt DRC deck specifications
"""

from pathlib import Path
import pytest

from klayout_drc.config import DEFAULT_LAYOUTS_DIR, DEFAULT_RULES_DIR
from klayout_drc.repair_executor import RepairExecutor
from klayout_drc.run_manifest import RunSpec
from klayout_drc.run_reporter import (
    VERDICT_INVALID_PATCH,
    VERDICT_TIMEOUT,
    VERDICT_NO_CHANGE,
    VERDICT_DRC_ERROR,
)
from klayout_drc.single_shot import SingleShotOrchestrator

SAMPLE_GDS = DEFAULT_LAYOUTS_DIR / "asap7_test.gds"
MINI_DECK = DEFAULT_RULES_DIR / "asap7_mini.drc"


def test_syntax_error_rejected(tmp_path: Path) -> None:
    """Test that a candidate script with syntax errors is rejected with invalid_patch."""
    bad_script = tmp_path / "bad_syntax.py"
    bad_script.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

    spec = RunSpec(
        case_name="test_syntax_error",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=bad_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_INVALID_PATCH
    assert summary.execution_result.status == "syntax_error"
    assert "SyntaxError" in (summary.execution_result.error_message or "")


def test_runtime_error_rejected(tmp_path: Path) -> None:
    """Test that a candidate script that crashes with an exception is recorded as invalid_patch."""
    crash_script = tmp_path / "crash.py"
    crash_script.write_text("raise RuntimeError('Intentional crash in repair script')\n", encoding="utf-8")

    spec = RunSpec(
        case_name="test_runtime_error",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=crash_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_INVALID_PATCH
    assert summary.execution_result.status == "nonzero_exit"
    assert summary.execution_result.exit_code != 0


def test_timeout_rejected(tmp_path: Path) -> None:
    """Test that candidate script exceeding timeout limit is killed and recorded as timeout."""
    loop_script = tmp_path / "loop.py"
    loop_script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")

    executor = RepairExecutor(
        candidate_script=loop_script,
        input_gds=SAMPLE_GDS,
        output_gds=tmp_path / "patched.gds",
        timeout_seconds=1,
    )
    result = executor.execute()

    assert result.status == "timeout"
    assert "timeout" in (result.error_message or "").lower()


def test_missing_output_gds_rejected(tmp_path: Path) -> None:
    """Test that script exiting code 0 without creating output GDS is rejected as invalid_patch."""
    no_output_script = tmp_path / "no_output.py"
    no_output_script.write_text("print('Finished without creating output GDS')\n", encoding="utf-8")

    spec = RunSpec(
        case_name="test_missing_output",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=no_output_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_INVALID_PATCH
    assert summary.execution_result.status == "missing_output"


def test_delete_all_geometry_rejected(tmp_path: Path) -> None:
    """Test that a malicious/buggy script that wipes all shapes to pass DRC is rejected by validator."""
    wipe_script = tmp_path / "delete_all.py"
    wipe_script.write_text(
        "import sys\n"
        "import klayout.db as db\n"
        "def fix_layout(in_gds, out_gds):\n"
        "    layout = db.Layout()\n"
        "    layout.read(in_gds)\n"
        "    top = layout.top_cell()\n"
        "    for idx in layout.layer_indexes():\n"
        "        top.shapes(idx).clear()\n"
        "    layout.write(out_gds)\n"
        "if __name__ == '__main__':\n"
        "    fix_layout(sys.argv[1], sys.argv[2])\n",
        encoding="utf-8",
    )

    spec = RunSpec(
        case_name="test_delete_all",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=wipe_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_INVALID_PATCH
    assert summary.validation_result is not None
    assert summary.validation_result.is_valid is False
    assert any("0 shapes" in viol for viol in summary.validation_result.violations)


def test_noop_patch_recorded_as_no_change(tmp_path: Path) -> None:
    """Test that a no-op script copying input to output is recorded as no_change."""
    noop_script = tmp_path / "noop.py"
    noop_script.write_text(
        "import sys, shutil\n"
        "shutil.copy2(sys.argv[1], sys.argv[2])\n",
        encoding="utf-8",
    )

    spec = RunSpec(
        case_name="test_noop",
        input_gds=SAMPLE_GDS,
        drc_script=MINI_DECK,
        profile_name="legacy_mini",
        candidate_mode="script_file",
        candidate_script=noop_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_NO_CHANGE
    assert summary.total_before == 8
    assert summary.total_after == 8
    assert summary.execution_result.status == "success"


def test_feol_edit_rejected_by_scope(tmp_path: Path) -> None:
    """Test that modifying an unallowed FEOL layer (Gate 7/0) is rejected as invalid_patch."""
    feol_script = tmp_path / "feol_edit.py"
    feol_script.write_text(
        "import sys, pya\n"
        "layout = pya.Layout()\n"
        "layout.read(sys.argv[1])\n"
        "top = layout.top_cell()\n"
        "gate_layer = layout.layer(7, 0)\n"  # Gate FEOL layer
        "top.shapes(gate_layer).insert(pya.Box(0, 0, 100, 100))\n"
        "layout.write(sys.argv[2])\n",
        encoding="utf-8",
    )

    spec = RunSpec(
        case_name="test_feol_edit",
        input_gds=SAMPLE_GDS,
        drc_script=DEFAULT_RULES_DIR / "asap7_curated.lydrc",
        profile_name="asap7_curated",
        candidate_mode="script_file",
        candidate_script=feol_script,
        output_root=tmp_path,
    )
    orchestrator = SingleShotOrchestrator(spec)
    summary = orchestrator.run()

    assert summary.verdict == VERDICT_INVALID_PATCH
    assert summary.validation_result is not None
    assert summary.validation_result.is_valid is False
    assert any("Edit scope violation" in viol for viol in summary.validation_result.violations)
