"""Unit and integration tests for hierarchical GDS context extraction with transforms (PR B-3)."""

from pathlib import Path
import pya
import pytest

from klayout_drc.config import ASAP7_LAYER_M1
from klayout_drc.gds_context import GDSContextProcessor
from klayout_drc.parser import DRCReportData, RuleCategory, ViolationGeometry, ViolationItem
from klayout_drc.marker_geometry import BoxMarker, MarkerGeometry


def create_hierarchical_gds(output_path: Path, dbu_um: float = 0.00025) -> None:
    """Create a 3-level hierarchical GDS: TOP -> BLOCK -> LEAF.

    LEAF has a box at (0, 0) to (0.020, 0.020) um on M1 (19/0).
    BLOCK instantiates LEAF at offset (0.100, 0.100) um.
    TOP instantiates BLOCK at offset (0.500, 0.500) um.

    Expected world coordinates of LEAF box in TOP:
    x: 0.500 + 0.100 + [0.000, 0.020] = [0.600, 0.620] um
    y: 0.500 + 0.100 + [0.000, 0.020] = [0.600, 0.620] um
    """
    layout = pya.Layout()
    layout.dbu = dbu_um

    top_cell = layout.create_cell("TOP")
    block_cell = layout.create_cell("BLOCK")
    leaf_cell = layout.create_cell("LEAF")

    layer_m1 = layout.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])

    # Leaf box: 20nm x 20nm
    bx1 = int(round(0.0 / dbu_um))
    by1 = int(round(0.0 / dbu_um))
    bx2 = int(round(0.020 / dbu_um))
    by2 = int(round(0.020 / dbu_um))
    leaf_cell.shapes(layer_m1).insert(pya.Box(bx1, by1, bx2, by2))

    # Place LEAF inside BLOCK at (0.100, 0.100) um
    leaf_dx = int(round(0.100 / dbu_um))
    leaf_dy = int(round(0.100 / dbu_um))
    block_cell.insert(pya.CellInstArray(leaf_cell.cell_index(), pya.Trans(leaf_dx, leaf_dy)))

    # Place BLOCK inside TOP at (0.500, 0.500) um
    block_dx = int(round(0.500 / dbu_um))
    block_dy = int(round(0.500 / dbu_um))
    top_cell.insert(pya.CellInstArray(block_cell.cell_index(), pya.Trans(block_dx, block_dy)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_path))


def test_hierarchical_context_extraction(tmp_path: Path):
    """Verify that GDSContextProcessor finds child cell shapes and transforms them to world coords."""
    gds_path = tmp_path / "hier_test.gds"
    create_hierarchical_gds(gds_path, dbu_um=0.00025)

    # Synthetic report item positioned near the transformed LEAF box [0.600, 0.620] um
    marker = BoxMarker(x1=0.600, y1=0.600, x2=0.610, y2=0.620)
    v_item = ViolationItem(
        item_id=1,
        category_name="M1.W.1",
        cell_name="TOP",
        geometries=[
            ViolationGeometry(
                kind="box",
                representation="box: (0.600,0.600;0.610,0.620)",
                marker=marker,
            )
        ],
    )
    report_data = DRCReportData(
        source_path=Path("dummy.lyrdb"),
        categories=[RuleCategory(name="M1.W.1", description="M1 width", violations=[v_item])],
    )

    processor = GDSContextProcessor(gds_path=gds_path, halo_um=0.050)
    windows = processor.extract_windows_for_report(report_data)

    assert len(windows) == 1
    win = windows[0]
    assert len(win.polygons) >= 1

    # Find the shape originated from LEAF
    leaf_shapes = [p for p in win.polygons if p.source_cell == "LEAF"]
    assert len(leaf_shapes) == 1

    leaf_poly = leaf_shapes[0]
    # Check transformed coordinates match world space: [0.600, 0.600] to [0.620, 0.620] um
    assert leaf_poly.bbox_um[0] == pytest.approx(0.600, abs=1e-4)
    assert leaf_poly.bbox_um[1] == pytest.approx(0.600, abs=1e-4)
    assert leaf_poly.bbox_um[2] == pytest.approx(0.620, abs=1e-4)
    assert leaf_poly.bbox_um[3] == pytest.approx(0.620, abs=1e-4)

    # Check formatted prompt output mentions LEAF cell and world coordinates
    text = processor.format_as_text(report_data)
    assert "LEAF" in text
    assert "0.6000" in text
    assert "0.6200" in text
