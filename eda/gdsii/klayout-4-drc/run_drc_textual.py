"""Backward-compatible wrapper for run_drc_textual."""
import sys
from pathlib import Path
from klayout_drc.cli import run_pipeline

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_drc_textual.py <drc_script> <in_gds>")
        sys.exit(1)
    drc_script = Path(sys.argv[1])
    in_gds = Path(sys.argv[2])
    result = run_pipeline(
        input_gds=in_gds,
        drc_script=drc_script,
        output_lyrdb=Path("reports/temp_drc_report.lyrdb"),
    )
    print(result["textual_report"])
