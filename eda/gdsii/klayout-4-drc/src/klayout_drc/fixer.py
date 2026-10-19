"""Programmatic repair tool for ASAP7 DRC violations using KLayout geometric APIs.

Implements automated healing for width, spacing, and via enclosure errors
using Region boolean and morphological operations.
"""

from pathlib import Path
import klayout.db as db

from .config import (
    LAYER_M1,
    LAYER_V1,
    ASAP7_M1_MIN_WIDTH_UM,
    ASAP7_V1_M1_MIN_ENCLOSURE_UM,
    DRCConfigurationError,
)


class DRCFixer:
    """Repairs geometric violations on M1 and V1 layers programmatically."""

    def __init__(self, input_gds: Path, output_gds: Path) -> None:
        """Initialize fixer with input and output file paths.
        
        Args:
            input_gds: Path to the layout containing violations.
            output_gds: Path where the repaired layout will be written.
        """
        self.input_gds = input_gds.resolve()
        self.output_gds = output_gds.resolve()
        if not self.input_gds.exists():
            raise DRCConfigurationError(f"Input GDS not found: {self.input_gds}")

    def fix(self) -> Path:
        """Execute geometric healing and write the repaired layout.
        
        Returns:
            Path: Path to the repaired GDS layout.
        """
        layout = db.Layout()
        layout.read(str(self.input_gds))
        top_cell = layout.top_cell()
        dbu = layout.dbu

        m1_layer = layout.layer(*LAYER_M1)
        v1_layer = layout.layer(*LAYER_V1)

        m1_shapes = top_cell.shapes(m1_layer)
        v1_shapes = top_cell.shapes(v1_layer)

        m1_reg = db.Region(m1_shapes)
        v1_reg = db.Region(v1_shapes)

        # 1. Fix Enclosure: Expand M1 to cover V1 by minimum enclosure (9nm)
        enc_dbu = int(round(ASAP7_V1_M1_MIN_ENCLOSURE_UM / dbu))
        m1_reg = m1_reg | v1_reg.sized(enc_dbu)

        # 2. Fix Spacing: Merge wires closer than minimum spacing (18nm) using morphological dilation/erosion
        merge_dbu = int(round((ASAP7_M1_MIN_WIDTH_UM / 2.0) / dbu))
        m1_reg = m1_reg.sized(merge_dbu).sized(-merge_dbu)

        # 3. Fix Width: Expand narrow regions (< 18nm) by adding sized width-check error markers
        min_width_dbu = int(round(ASAP7_M1_MIN_WIDTH_UM / dbu))
        width_boost_dbu = int(round(0.005 / dbu))
        error_edges = m1_reg.width_check(min_width_dbu)
        m1_reg = m1_reg | error_edges.polygons(0).sized(width_boost_dbu)

        # Replace shapes on M1 with healed region
        m1_shapes.clear()
        m1_shapes.insert(m1_reg)

        self.output_gds.parent.mkdir(parents=True, exist_ok=True)
        layout.write(str(self.output_gds))
        return self.output_gds
