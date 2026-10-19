"""Backward-compatible wrapper for drc_fix."""
from pathlib import Path
from klayout_drc.fixer import DRCFixer

if __name__ == "__main__":
    in_gds = Path("test_data/layouts/asap7_test.gds")
    out_gds = Path("test_data/layouts/asap7_fixed.gds")
    if not in_gds.exists():
        in_gds = Path("asap7_test.gds")
        out_gds = Path("asap7_fixed.gds")
    fixer = DRCFixer(input_gds=in_gds, output_gds=out_gds)
    fixer.fix()
    print(f"Repaired layout generated successfully at: {out_gds}")
