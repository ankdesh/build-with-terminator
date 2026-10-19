"""Backward-compatible wrapper for run_drc."""
from pathlib import Path
from klayout_drc.cli import run_pipeline

if __name__ == "__main__":
    in_gds = Path("test_data/layouts/asap7_test.gds")
    rule_deck = Path("test_data/rules/asap7_mini.drc")
    report_db = Path("reports/drc_violations.lyrdb")
    if not in_gds.exists():
        in_gds = Path("asap7_test.gds")
        rule_deck = Path("asap7_mini.drc")
    result = run_pipeline(
        input_gds=in_gds,
        drc_script=rule_deck,
        output_lyrdb=report_db,
    )
    print(result["textual_report"])
