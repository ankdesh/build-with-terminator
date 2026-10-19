"""Integration tests for the KLayout DRC pipeline and context processors."""

from pathlib import Path
import pytest

from klayout_drc.config import (
    DEFAULT_LAYOUTS_DIR,
    DEFAULT_RULES_DIR,
    DEFAULT_KNOWLEDGE_DIR,
    DRCConfigurationError,
)
from klayout_drc.cli import (
    run_pipeline,
    execute_run_drc,
    execute_violation_context,
    execute_drc_context,
    execute_gds_context,
    execute_load_knowledge,
    execute_save_script,
)
from klayout_drc.fixer import DRCFixer
from klayout_drc.parser import DRCParser
from klayout_drc.drc_context import DRCContextProcessor
from klayout_drc.gds_context import GDSContextProcessor
from klayout_drc.knowledge_loader import KnowledgeLoader


@pytest.fixture
def sample_gds_path() -> Path:
    """Path to the test layout with intentional violations."""
    return DEFAULT_LAYOUTS_DIR / "asap7_test.gds"


@pytest.fixture
def sample_drc_path() -> Path:
    """Path to the ASAP7 mini DRC rule deck."""
    return DEFAULT_RULES_DIR / "asap7_mini.drc"


def test_drc_pipeline_violations_detected(
    tmp_path: Path, sample_gds_path: Path, sample_drc_path: Path
) -> None:
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


def test_drc_context_processor(sample_drc_path: Path) -> None:
    """Test that DRCContextProcessor extracts rule definitions and thresholds for violated rules."""
    processor = DRCContextProcessor(sample_drc_path)
    violated = ["M1_W", "M1_S", "V1_M1_ENC"]
    rules = processor.extract_rules_for_violations(violated)

    assert "M1_W" in rules
    assert "M1_S" in rules
    assert "V1_M1_ENC" in rules

    assert rules["M1_W"].threshold_um == 0.018
    assert rules["M1_S"].threshold_um == 0.018
    assert "M1 minimum width is 18nm" in rules["M1_W"].code_block

    formatted = processor.format_as_text(violated)
    assert "=== DRC Rules Context ===" in formatted
    assert "--- Rule: M1_W ---" in formatted
    assert "--- Rule: V1_M1_ENC ---" in formatted


def test_gds_context_processor(tmp_path: Path, sample_gds_path: Path, sample_drc_path: Path) -> None:
    """Test that GDSContextProcessor extracts windowed layout geometry around violation coordinates."""
    out_lyrdb = tmp_path / "test_violations.lyrdb"
    execute_run_drc(sample_gds_path, sample_drc_path, out_lyrdb)

    parser = DRCParser()
    data = parser.parse(out_lyrdb)

    gds_proc = GDSContextProcessor(sample_gds_path, halo_um=0.1)
    windows = gds_proc.extract_windows_for_report(data, max_windows_per_rule=2)

    assert len(windows) > 0
    # Check that shapes were detected on layer 18/0 or 19/0
    all_layers = {poly.layer for win in windows for poly in win.polygons}
    assert 18 in all_layers or 19 in all_layers

    text = gds_proc.format_as_text(data)
    assert "=== GDS Layout Context (Violation Neighborhood Windows) ===" in text
    assert "Window Halo Margin: 100.0 nm" in text


def test_knowledge_loader() -> None:
    """Test that KnowledgeLoader loads all markdown knowledge files."""
    loader = KnowledgeLoader(DEFAULT_KNOWLEDGE_DIR)
    docs = loader.load_documents()

    assert len(docs) >= 3
    doc_files = [d.filename for d in docs]
    assert "asap7_rules_guide.md" in doc_files
    assert "geometric_fix_techniques.md" in doc_files
    assert "klayout_api_patterns.md" in doc_files

    formatted = loader.format_as_text()
    assert "=== Domain Knowledge Base ===" in formatted
    assert "ASAP7 Process Design Kit" in formatted


def test_cli_granular_execution_modes(
    tmp_path: Path, sample_gds_path: Path, sample_drc_path: Path
) -> None:
    """Test all fine-grained execution modes matching the flow nodes."""
    out_lyrdb = tmp_path / "granular.lyrdb"
    out_text = tmp_path / "granular.txt"
    out_script = tmp_path / "test_fix.py"

    # Node 1: run-drc
    r1 = execute_run_drc(sample_gds_path, sample_drc_path, out_lyrdb)
    assert r1["status"] == "success"
    assert r1["total_violations"] == 8

    # Node 2: violation-ctx
    r2 = execute_violation_context(out_lyrdb, out_text)
    assert r2["status"] == "success"
    assert "violations_text" in r2
    assert out_text.exists()

    # Node 3: drc-ctx
    r3 = execute_drc_context(sample_drc_path, out_lyrdb)
    assert r3["status"] == "success"
    assert "drc_rules_text" in r3

    # Node 4: gds-ctx
    r4 = execute_gds_context(sample_gds_path, out_lyrdb, halo_um=0.1)
    assert r4["status"] == "success"
    assert "gds_sections_text" in r4

    # Node 5: load-knowledge
    r5 = execute_load_knowledge(DEFAULT_KNOWLEDGE_DIR)
    assert r5["status"] == "success"
    assert "knowledge_text" in r5

    # Node 7: save-script
    sample_code = "# Sample repair script\nprint('hello')\n"
    r7 = execute_save_script(sample_code, out_script)
    assert r7["status"] == "success"
    assert out_script.exists()
    assert out_script.read_text() == sample_code


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
