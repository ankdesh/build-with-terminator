#!/usr/bin/env python3
"""Known-good layout repair script for ASAP7 mini DRC test fixture.

Repairs width, spacing, and via enclosure errors using KLayout Region operations.
"""

import sys
from pathlib import Path
import klayout.db as db


def fix_layout(input_gds: str, output_gds: str) -> None:
    """Repair M1 and V1 DRC violations on legacy_mini testcase."""
    layout = db.Layout()
    layout.read(str(input_gds))
    top = layout.top_cell()
    if top is None:
        raise RuntimeError("No top cell found in layout.")

    dbu = layout.dbu
    # Layer 18/0 for M1, Layer 19/0 for V1 under legacy_mini
    m1_idx = layout.find_layer(18, 0)
    v1_idx = layout.find_layer(19, 0)

    m1_reg = db.Region(top.shapes(m1_idx)) if m1_idx is not None else db.Region()
    v1_reg = db.Region(top.shapes(v1_idx)) if v1_idx is not None else db.Region()

    # 1. Enclosure pad V1 by 9nm
    if not v1_reg.is_empty():
        enc_pad_dbu = int(round(0.009 / dbu))
        m1_reg = m1_reg | v1_reg.sized(enc_pad_dbu)

    # 2. Fix spacing: merge wires closer than 18nm
    if not m1_reg.is_empty():
        merge_dbu = int(round(0.009 / dbu))
        m1_reg = m1_reg.sized(merge_dbu).sized(-merge_dbu)

        # 3. Fix width: expand narrow regions (< 18nm)
        min_width_dbu = int(round(0.018 / dbu))
        width_boost_dbu = int(round(0.005 / dbu))
        error_edges = m1_reg.width_check(min_width_dbu)
        m1_reg = m1_reg | error_edges.polygons(0).sized(width_boost_dbu)

        if m1_idx is None:
            m1_idx = layout.layer(18, 0)
        top.shapes(m1_idx).clear()
        top.shapes(m1_idx).insert(m1_reg)

    Path(output_gds).parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_gds))


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "input.gds"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "patched.gds"
    fix_layout(in_path, out_path)
