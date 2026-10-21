"""Deterministic fixture generator for ASAP7 BEOL 4-case boundary matrix (PR B-4).

Generates 20 testcases covering 5 core BEOL rule families across 4 boundary conditions:
  1. Legal (wide margin)
  2. Legal boundary (exact specification threshold)
  3. Illegal boundary (1 manufacturing-grid step below threshold: -0.25 nm)
  4. Clearly illegal (gross geometric violation)
Plus 1 compound interaction testcase.
"""

from pathlib import Path
import pya

from klayout_drc.config import (
    ASAP7_DBU_UM,
    ASAP7_LAYER_M1,
    ASAP7_LAYER_M2,
    ASAP7_LAYER_V1,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "asap7_beol_v1"


def create_wire_layout(
    layer_info: tuple[int, int],
    width_um: float,
    length_um: float,
    output_path: Path,
    dbu_um: float = ASAP7_DBU_UM,
) -> None:
    """Create a single rectangular wire layout on specified layer."""
    layout = pya.Layout()
    layout.dbu = dbu_um
    top_cell = layout.create_cell("TOP")
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_dbu = int(round(width_um / dbu_um))
    l_dbu = int(round(length_um / dbu_um))

    box = pya.Box(0, 0, w_dbu, l_dbu)
    top_cell.shapes(layer_idx).insert(box)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_path))


def create_spacing_layout(
    layer_info: tuple[int, int],
    width_um: float,
    length_um: float,
    spacing_um: float,
    output_path: Path,
    dbu_um: float = ASAP7_DBU_UM,
) -> None:
    """Create two parallel wires separated by spacing_um on specified layer."""
    layout = pya.Layout()
    layout.dbu = dbu_um
    top_cell = layout.create_cell("TOP")
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_dbu = int(round(width_um / dbu_um))
    l_dbu = int(round(length_um / dbu_um))
    s_dbu = int(round(spacing_um / dbu_um))

    box1 = pya.Box(0, 0, w_dbu, l_dbu)
    box2 = pya.Box(w_dbu + s_dbu, 0, 2 * w_dbu + s_dbu, l_dbu)

    top_cell.shapes(layer_idx).insert(box1)
    top_cell.shapes(layer_idx).insert(box2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_path))


def create_compound_layout(
    output_path: Path,
    dbu_um: float = ASAP7_DBU_UM,
) -> None:
    """Create a layout with compound M1 width, M1 spacing, and V1 width violations."""
    layout = pya.Layout()
    layout.dbu = dbu_um
    top_cell = layout.create_cell("TOP")
    layer_m1 = layout.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
    layer_v1 = layout.layer(ASAP7_LAYER_V1[0], ASAP7_LAYER_V1[1])

    # 1. Spaced wires for M1.S.1: width 40nm, length 100nm, spacing 14nm (< 18nm)
    w = int(round(0.040 / dbu_um))
    l = int(round(0.100 / dbu_um))
    s = int(round(0.014 / dbu_um))
    top_cell.shapes(layer_m1).insert(pya.Box(0, 0, w, l))
    top_cell.shapes(layer_m1).insert(pya.Box(w + s, 0, 2 * w + s, l))

    # 2. Narrow wire for M1.W.1: width 12nm (< 18nm), length 100nm, at x = 200nm
    x3 = int(round(0.200 / dbu_um))
    w3 = int(round(0.012 / dbu_um))
    top_cell.shapes(layer_m1).insert(pya.Box(x3, 0, x3 + w3, l))

    # 3. Narrow via for V1.W.1: width 12nm (< 18nm) at x = 300nm
    x4 = int(round(0.300 / dbu_um))
    w4 = int(round(0.012 / dbu_um))
    top_cell.shapes(layer_v1).insert(pya.Box(x4, 0, x4 + w4, w4))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_path))


def generate_all_fixtures() -> dict[str, Path]:
    """Generate all 20 boundary matrix cases + 1 compound interaction case."""
    fixtures: dict[str, Path] = {}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. M1.W.1 (threshold: 18 nm)
    create_wire_layout(ASAP7_LAYER_M1, 0.024, 0.100, OUTPUT_DIR / "m1_w1_legal.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.018, 0.100, OUTPUT_DIR / "m1_w1_legal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.01775, 0.100, OUTPUT_DIR / "m1_w1_illegal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.010, 0.100, OUTPUT_DIR / "m1_w1_clearly_illegal.gds")

    # 2. M2.W.1 (threshold: 18 nm)
    create_wire_layout(ASAP7_LAYER_M2, 0.024, 0.100, OUTPUT_DIR / "m2_w1_legal.gds")
    create_wire_layout(ASAP7_LAYER_M2, 0.018, 0.100, OUTPUT_DIR / "m2_w1_legal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M2, 0.01775, 0.100, OUTPUT_DIR / "m2_w1_illegal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M2, 0.010, 0.100, OUTPUT_DIR / "m2_w1_clearly_illegal.gds")

    # 3. M1.A.1 (threshold: 504 nm2 = 0.000504 um2)
    create_wire_layout(ASAP7_LAYER_M1, 0.018, 0.040, OUTPUT_DIR / "m1_a1_legal.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.018, 0.02825, OUTPUT_DIR / "m1_a1_legal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.018, 0.02775, OUTPUT_DIR / "m1_a1_illegal_bound.gds")
    create_wire_layout(ASAP7_LAYER_M1, 0.018, 0.018, OUTPUT_DIR / "m1_a1_clearly_illegal.gds")

    # 4. M1.S.1 (threshold: 18 nm, parallel run > 36 nm, wire width > 36 nm)
    create_spacing_layout(ASAP7_LAYER_M1, 0.040, 0.100, 0.024, OUTPUT_DIR / "m1_s1_legal.gds")
    create_spacing_layout(ASAP7_LAYER_M1, 0.040, 0.100, 0.018, OUTPUT_DIR / "m1_s1_legal_bound.gds")
    create_spacing_layout(ASAP7_LAYER_M1, 0.040, 0.100, 0.01775, OUTPUT_DIR / "m1_s1_illegal_bound.gds")
    create_spacing_layout(ASAP7_LAYER_M1, 0.040, 0.100, 0.010, OUTPUT_DIR / "m1_s1_clearly_illegal.gds")

    # 5. V1.W.1 (threshold: 18 nm)
    create_wire_layout(ASAP7_LAYER_V1, 0.024, 0.024, OUTPUT_DIR / "v1_w1_legal.gds")
    create_wire_layout(ASAP7_LAYER_V1, 0.018, 0.018, OUTPUT_DIR / "v1_w1_legal_bound.gds")
    create_wire_layout(ASAP7_LAYER_V1, 0.01775, 0.01775, OUTPUT_DIR / "v1_w1_illegal_bound.gds")
    create_wire_layout(ASAP7_LAYER_V1, 0.010, 0.010, OUTPUT_DIR / "v1_w1_clearly_illegal.gds")

    # 6. Compound Interaction
    create_compound_layout(OUTPUT_DIR / "compound_beol_interaction.gds")

    for f in OUTPUT_DIR.glob("*.gds"):
        fixtures[f.stem] = f

    return fixtures


if __name__ == "__main__":
    fixtures = generate_all_fixtures()
    print(f"Successfully generated {len(fixtures)} ASAP7 BEOL fixtures in {OUTPUT_DIR}")
