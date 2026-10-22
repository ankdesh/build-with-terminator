"""Geometric mutation operators and layout construction primitives.

Constructs synthetic layout structures with precise dimensional control at the
0.25 nm database unit (DBU) grid for all 5 BEOL rule families:
  - M1.W.1 (M1 Width, 18 nm threshold)
  - M2.W.1 (M2 Width, 18 nm threshold)
  - M1.A.1 (M1 Area, 504 nm2 threshold)
  - M1.S.1 (M1 Spacing, 18 nm threshold for edges > 36 nm)
  - V1.W.1 (V1 Via Cut Width, 18 nm threshold)
"""

from pathlib import Path
from typing import Optional, Tuple
import pya

from klayout_drc.config import (
    ASAP7_DBU_UM,
    ASAP7_LAYER_M1,
    ASAP7_LAYER_M2,
    ASAP7_LAYER_V1,
)

TOP_CELL_NAME: str = "TOP"


def init_benchmark_layout(dbu_um: float = ASAP7_DBU_UM) -> Tuple[pya.Layout, pya.Cell]:
    """Initialize an empty layout with TOP cell and standard ASAP7 DBU."""
    layout = pya.Layout()
    layout.dbu = dbu_um
    top_cell = layout.create_cell(TOP_CELL_NAME)
    return layout, top_cell


def write_layout(layout: pya.Layout, output_path: Path) -> None:
    """Save layout deterministically to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    opt = pya.SaveLayoutOptions()
    opt.gds2_write_timestamps = False
    layout.write(str(output_path), opt)


def to_dbu(val_um: float, dbu_um: float = ASAP7_DBU_UM) -> int:
    """Convert micrometer coordinate to integer database units."""
    return int(round(val_um / dbu_um))


# ---------------------------------------------------------------------------
# Wire & Width Primitives (M1.W.1 / M2.W.1)
# ---------------------------------------------------------------------------

def create_straight_wire(
    layer_info: Tuple[int, int],
    width_um: float,
    length_um: float,
    vertical: bool = True,
    x_offset_um: float = 0.0,
    y_offset_um: float = 0.0,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a single straight rectangular wire."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    x0 = to_dbu(x_offset_um, dbu_um)
    y0 = to_dbu(y_offset_um, dbu_um)

    if vertical:
        w = to_dbu(width_um, dbu_um)
        l = to_dbu(length_um, dbu_um)
        box = pya.Box(x0, y0, x0 + w, y0 + l)
    else:
        w = to_dbu(length_um, dbu_um)
        l = to_dbu(width_um, dbu_um)
        box = pya.Box(x0, y0, x0 + w, y0 + l)

    top.shapes(layer_idx).insert(box)
    return layout


def create_notched_wire(
    layer_info: Tuple[int, int],
    base_width_um: float,
    notch_width_um: float,
    total_length_um: float,
    notch_length_um: float,
    notch_start_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a vertical wire containing a narrow notch along one edge."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_base = to_dbu(base_width_um, dbu_um)
    w_notch = to_dbu(notch_width_um, dbu_um)
    l_total = to_dbu(total_length_um, dbu_um)
    l_notch = to_dbu(notch_length_um, dbu_um)
    y_start = to_dbu(notch_start_um, dbu_um)

    # Base full wire
    r_base = pya.Region(pya.Box(0, 0, w_base, l_total))
    # Cutout notch
    r_cutout = pya.Region(pya.Box(w_notch, y_start, w_base, y_start + l_notch))
    r_result = r_base - r_cutout

    top.shapes(layer_idx).insert(r_result)
    return layout


def create_stepped_wire(
    layer_info: Tuple[int, int],
    wide_width_um: float,
    narrow_width_um: float,
    segment_lengths_um: Tuple[float, float, float],
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a 3-segment stepped wire (wide -> narrow bottleneck -> wide)."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_wide = to_dbu(wide_width_um, dbu_um)
    w_narrow = to_dbu(narrow_width_um, dbu_um)
    l1 = to_dbu(segment_lengths_um[0], dbu_um)
    l2 = to_dbu(segment_lengths_um[1], dbu_um)
    l3 = to_dbu(segment_lengths_um[2], dbu_um)

    # Segment 1 (wide)
    box1 = pya.Box(0, 0, w_wide, l1)
    # Segment 2 (narrow bottleneck, centered or aligned)
    dx = (w_wide - w_narrow) // 2
    box2 = pya.Box(dx, l1, dx + w_narrow, l1 + l2)
    # Segment 3 (wide)
    box3 = pya.Box(0, l1 + l2, w_wide, l1 + l2 + l3)

    r = pya.Region(box1) + pya.Region(box2) + pya.Region(box3)
    top.shapes(layer_idx).insert(r)
    return layout


def create_l_bend_wire(
    layer_info: Tuple[int, int],
    leg1_w_um: float,
    leg1_l_um: float,
    leg2_w_um: float,
    leg2_l_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create an L-shaped bent wire with independent leg dimensions."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w1 = to_dbu(leg1_w_um, dbu_um)
    l1 = to_dbu(leg1_l_um, dbu_um)
    w2 = to_dbu(leg2_w_um, dbu_um)
    l2 = to_dbu(leg2_l_um, dbu_um)

    # Vertical leg
    box1 = pya.Box(0, 0, w1, l1)
    # Horizontal leg extending to the right from top of leg 1
    box2 = pya.Box(0, l1 - w2, l2, l1)

    r = pya.Region(box1) + pya.Region(box2)
    top.shapes(layer_idx).insert(r)
    return layout


def create_t_junction_wire(
    layer_info: Tuple[int, int],
    trunk_w_um: float,
    trunk_l_um: float,
    branch_w_um: float,
    branch_l_um: float,
    branch_y_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a T-junction with a main trunk and a perpendicular branch."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_trunk = to_dbu(trunk_w_um, dbu_um)
    l_trunk = to_dbu(trunk_l_um, dbu_um)
    w_branch = to_dbu(branch_w_um, dbu_um)
    l_branch = to_dbu(branch_l_um, dbu_um)
    y_branch = to_dbu(branch_y_um, dbu_um)

    box_trunk = pya.Box(0, 0, w_trunk, l_trunk)
    box_branch = pya.Box(w_trunk, y_branch, w_trunk + l_branch, y_branch + w_branch)

    r = pya.Region(box_trunk) + pya.Region(box_branch)
    top.shapes(layer_idx).insert(r)
    return layout


def create_jog_wire(
    layer_info: Tuple[int, int],
    wire_w_um: float,
    jog_neck_w_um: float,
    seg_l_um: float,
    jog_offset_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a dogleg jog with a narrow diagonal or offset bridge."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(wire_w_um, dbu_um)
    w_jog = to_dbu(jog_neck_w_um, dbu_um)
    l_seg = to_dbu(seg_l_um, dbu_um)
    dx = to_dbu(jog_offset_um, dbu_um)

    # Lower vertical wire
    box1 = pya.Box(0, 0, w, l_seg)
    # Horizontal jog neck
    box_jog = pya.Box(0, l_seg - w_jog, dx + w, l_seg)
    # Upper vertical wire offset by dx
    box2 = pya.Box(dx, l_seg, dx + w, 2 * l_seg)

    r = pya.Region(box1) + pya.Region(box_jog) + pya.Region(box2)
    top.shapes(layer_idx).insert(r)
    return layout


# ---------------------------------------------------------------------------
# Area Primitives (M1.A.1)
# ---------------------------------------------------------------------------

def create_area_pad(
    layer_info: Tuple[int, int],
    width_um: float,
    length_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create an isolated rectangular landing pad with precise area."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(width_um, dbu_um)
    l = to_dbu(length_um, dbu_um)
    top.shapes(layer_idx).insert(pya.Box(0, 0, w, l))
    return layout


def create_l_shaped_pad(
    layer_info: Tuple[int, int],
    w1_um: float,
    l1_um: float,
    w2_um: float,
    l2_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create an L-shaped small pad with exact total area."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w1 = to_dbu(w1_um, dbu_um)
    l1 = to_dbu(l1_um, dbu_um)
    w2 = to_dbu(w2_um, dbu_um)
    l2 = to_dbu(l2_um, dbu_um)

    b1 = pya.Box(0, 0, w1, l1)
    b2 = pya.Box(0, l1 - w2, l2, l1)
    r = pya.Region(b1) + pya.Region(b2)
    top.shapes(layer_idx).insert(r)
    return layout


def create_cross_shaped_pad(
    layer_info: Tuple[int, int],
    core_w_um: float,
    core_l_um: float,
    arm_w_um: float,
    arm_l_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a cross-shaped micro pad."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_core = to_dbu(core_w_um, dbu_um)
    l_core = to_dbu(core_l_um, dbu_um)
    w_arm = to_dbu(arm_w_um, dbu_um)
    l_arm = to_dbu(arm_l_um, dbu_um)

    # Vertical bar
    b_vert = pya.Box(0, 0, w_core, l_core)
    # Horizontal arms
    y_mid = (l_core - w_arm) // 2
    b_horiz = pya.Box(-l_arm, y_mid, w_core + l_arm, y_mid + w_arm)

    r = pya.Region(b_vert) + pya.Region(b_horiz)
    top.shapes(layer_idx).insert(r)
    return layout


# ---------------------------------------------------------------------------
# Spacing Primitives (M1.S.1)
# ---------------------------------------------------------------------------

def create_parallel_wires(
    layer_info: Tuple[int, int],
    width_um: float,
    length_um: float,
    spacing_um: float,
    vertical: bool = True,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create two parallel wires separated by spacing_um.

    Note: Wires must have width and length > 36 nm to ensure edges are not
    filtered by upstream M1.S.1 rule:
      m1.space(18.nm).polygons.not_interacting(m1.edges.with_length(0..36.nm))
    """
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(width_um, dbu_um)
    l = to_dbu(length_um, dbu_um)
    s = to_dbu(spacing_um, dbu_um)

    if vertical:
        b1 = pya.Box(0, 0, w, l)
        b2 = pya.Box(w + s, 0, 2 * w + s, l)
    else:
        b1 = pya.Box(0, 0, l, w)
        b2 = pya.Box(0, w + s, l, 2 * w + s)

    top.shapes(layer_idx).insert(b1)
    top.shapes(layer_idx).insert(b2)
    return layout


def create_three_parallel_wires(
    layer_info: Tuple[int, int],
    width_um: float,
    length_um: float,
    spacing1_um: float,
    spacing2_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create three parallel vertical wires separated by independent spacings."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(width_um, dbu_um)
    l = to_dbu(length_um, dbu_um)
    s1 = to_dbu(spacing1_um, dbu_um)
    s2 = to_dbu(spacing2_um, dbu_um)

    x1 = 0
    x2 = w + s1
    x3 = x2 + w + s2

    top.shapes(layer_idx).insert(pya.Box(x1, 0, x1 + w, l))
    top.shapes(layer_idx).insert(pya.Box(x2, 0, x2 + w, l))
    top.shapes(layer_idx).insert(pya.Box(x3, 0, x3 + w, l))
    return layout


def create_u_channel(
    layer_info: Tuple[int, int],
    wall_w_um: float,
    channel_w_um: float,
    channel_depth_um: float,
    base_h_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a U-shaped channel testing inner cavity spacing."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_wall = to_dbu(wall_w_um, dbu_um)
    w_chan = to_dbu(channel_w_um, dbu_um)
    d_chan = to_dbu(channel_depth_um, dbu_um)
    h_base = to_dbu(base_h_um, dbu_um)

    # Base horizontal bar
    total_w = 2 * w_wall + w_chan
    total_h = h_base + d_chan

    r_outer = pya.Region(pya.Box(0, 0, total_w, total_h))
    r_cavity = pya.Region(pya.Box(w_wall, h_base, w_wall + w_chan, total_h))
    r_result = r_outer - r_cavity

    top.shapes(layer_idx).insert(r_result)
    return layout


# ---------------------------------------------------------------------------
# Via Primitives (V1.W.1)
# ---------------------------------------------------------------------------

def create_via_cut(
    layer_info: Tuple[int, int],
    width_um: float,
    height_um: float,
    x_offset_um: float = 0.0,
    y_offset_um: float = 0.0,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create a single isolated via cut on V1."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(width_um, dbu_um)
    h = to_dbu(height_um, dbu_um)
    x0 = to_dbu(x_offset_um, dbu_um)
    y0 = to_dbu(y_offset_um, dbu_um)

    top.shapes(layer_idx).insert(pya.Box(x0, y0, x0 + w, y0 + h))
    return layout


def create_via_array(
    layer_info: Tuple[int, int],
    width_um: float,
    height_um: float,
    pitch_x_um: float,
    count: int = 2,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Create an array of multiple via cuts along X."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w = to_dbu(width_um, dbu_um)
    h = to_dbu(height_um, dbu_um)
    pitch = to_dbu(pitch_x_um, dbu_um)

    for i in range(count):
        x0 = i * pitch
        top.shapes(layer_idx).insert(pya.Box(x0, 0, x0 + w, h))

    return layout


# ---------------------------------------------------------------------------
# Compound Interaction Primitives
# ---------------------------------------------------------------------------

def create_width_and_spacing_interaction(
    layer_info: Tuple[int, int],
    narrow_w_um: float,
    narrow_l_um: float,
    neighbor_w_um: float,
    neighbor_l_um: float,
    spacing_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Simultaneously triggers width violation on wire 1 and spacing violation to wire 2."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w1 = to_dbu(narrow_w_um, dbu_um)
    l1 = to_dbu(narrow_l_um, dbu_um)
    w2 = to_dbu(neighbor_w_um, dbu_um)
    l2 = to_dbu(neighbor_l_um, dbu_um)
    s = to_dbu(spacing_um, dbu_um)

    top.shapes(layer_idx).insert(pya.Box(0, 0, w1, l1))
    top.shapes(layer_idx).insert(pya.Box(w1 + s, 0, w1 + s + w2, l2))
    return layout


def create_area_and_spacing_interaction(
    layer_info: Tuple[int, int],
    pad_w_um: float,
    pad_l_um: float,
    trunk_w_um: float,
    trunk_l_um: float,
    spacing_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Simultaneously triggers M1.A.1 on small pad and M1.S.1 spacing to adjacent trunk."""
    layout, top = init_benchmark_layout(dbu_um)
    layer_idx = layout.layer(layer_info[0], layer_info[1])

    w_pad = to_dbu(pad_w_um, dbu_um)
    l_pad = to_dbu(pad_l_um, dbu_um)
    w_trunk = to_dbu(trunk_w_um, dbu_um)
    l_trunk = to_dbu(trunk_l_um, dbu_um)
    s = to_dbu(spacing_um, dbu_um)

    # Pad on left
    top.shapes(layer_idx).insert(pya.Box(0, 0, w_pad, l_pad))
    # Trunk on right
    top.shapes(layer_idx).insert(pya.Box(w_pad + s, 0, w_pad + s + w_trunk, l_trunk))
    return layout


def create_via_and_wire_interaction(
    via_layer: Tuple[int, int],
    wire_layer: Tuple[int, int],
    via_w_um: float,
    via_h_um: float,
    wire_w_um: float,
    wire_l_um: float,
    dbu_um: float = ASAP7_DBU_UM,
) -> pya.Layout:
    """Triggers both via cut width violation and underlying wire width violation."""
    layout, top = init_benchmark_layout(dbu_um)
    l_via = layout.layer(via_layer[0], via_layer[1])
    l_wire = layout.layer(wire_layer[0], wire_layer[1])

    w_wire = to_dbu(wire_w_um, dbu_um)
    l_wire_len = to_dbu(wire_l_um, dbu_um)
    w_via = to_dbu(via_w_um, dbu_um)
    h_via = to_dbu(via_h_um, dbu_um)

    top.shapes(l_wire).insert(pya.Box(0, 0, w_wire, l_wire_len))
    top.shapes(l_via).insert(pya.Box(0, 0, w_via, h_via))
    return layout
