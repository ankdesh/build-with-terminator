"""Deterministic generator for versioned legacy_mini_v2 test fixtures.

Generates targeted, isolated GDS layout test cases for Phase A:
- A-W-1: Isolated narrow wire (M1_W)
- A-S-1: Parallel wire spacing violation (M1_S)
- A-E-1: Insufficient via enclosure (V1_M1_ENC)
- A-OK-1: DRC clean layout
- A-MIX-1: Combined violations
- A-DBU-1: Physical equivalent layout with high-resolution DBU (0.00025 um)
"""

from pathlib import Path
import klayout.db as db

FIXTURES_DIR = Path(__file__).resolve().parent / "legacy_mini_v2"


def create_a_w_1_min_width(out_path: Path) -> Path:
    """Create A-W-1: Isolated narrow M1 wire (width 10nm < 18nm threshold)."""
    layout = db.Layout()
    layout.dbu = 0.001  # 1 nm
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)

    # 10nm width x 100nm length (10 DBU x 100 DBU)
    top.shapes(m1).insert(db.Box(0, 0, 10, 100))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def create_a_s_1_min_spacing(out_path: Path) -> Path:
    """Create A-S-1: Two parallel M1 wires with 10nm gap (< 18nm threshold)."""
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)

    # Wire 1: width 20nm (x=0 to 20), length 100nm
    top.shapes(m1).insert(db.Box(0, 0, 20, 100))
    # Wire 2: width 20nm (x=30 to 50), length 100nm -> 10nm gap between x=20 and x=30
    top.shapes(m1).insert(db.Box(30, 0, 50, 100))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def create_a_e_1_via_enclosure(out_path: Path) -> Path:
    """Create A-E-1: V1 via with insufficient M1 enclosure (2nm < 9nm threshold)."""
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)
    v1 = layout.layer(19, 0)

    # V1 via: 18nm x 18nm at (10, 10) to (28, 28)
    top.shapes(v1).insert(db.Box(10, 10, 28, 28))
    # M1 pad: (8, 8) to (30, 30) -> enclosure is only 2nm on each side (< 9nm)
    top.shapes(m1).insert(db.Box(8, 8, 30, 30))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def create_a_ok_1_clean(out_path: Path) -> Path:
    """Create A-OK-1: DRC clean layout under legacy_mini ruleset."""
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)
    v1 = layout.layer(19, 0)

    # V1 via: 18nm x 18nm at (20, 20) to (38, 38)
    top.shapes(v1).insert(db.Box(20, 20, 38, 38))
    # M1 pad: (10, 10) to (48, 48) -> 10nm enclosure on all sides (>= 9nm)
    # Total width is 38nm >= 18nm
    top.shapes(m1).insert(db.Box(10, 10, 48, 48))

    # Second M1 wire placed at x=70 (spacing is 22nm >= 18nm)
    top.shapes(m1).insert(db.Box(70, 10, 95, 48))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def create_a_mix_1_combined(out_path: Path) -> Path:
    """Create A-MIX-1: Combined layout with width, spacing, and enclosure violations."""
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)
    v1 = layout.layer(19, 0)

    # 1. Width violation: 12nm wire
    top.shapes(m1).insert(db.Box(0, 0, 12, 80))

    # 2. Spacing violation: wire at x=24 (12nm gap < 18nm)
    top.shapes(m1).insert(db.Box(24, 0, 50, 80))

    # 3. Via enclosure violation: V1 at (60, 20) to (78, 38), M1 at (58, 15) to (80, 43) -> 2nm lateral enclosure
    top.shapes(v1).insert(db.Box(60, 20, 78, 38))
    top.shapes(m1).insert(db.Box(58, 15, 80, 43))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def create_a_dbu_1_high_res(out_path: Path) -> Path:
    """Create A-DBU-1: Physically identical to A-W-1 (10nm wire) with DBU=0.00025 um."""
    layout = db.Layout()
    layout.dbu = 0.00025  # 0.25 nm DBU
    top = layout.create_cell("TOP")
    m1 = layout.layer(18, 0)

    # 10nm = 40 DBU, 100nm = 400 DBU
    top.shapes(m1).insert(db.Box(0, 0, 40, 400))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    return out_path


def generate_all_fixtures(target_dir: Path = FIXTURES_DIR) -> dict[str, Path]:
    """Generate all legacy_mini_v2 fixtures in target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "A-W-1": create_a_w_1_min_width(target_dir / "a_w_1_min_width.gds"),
        "A-S-1": create_a_s_1_min_spacing(target_dir / "a_s_1_min_spacing.gds"),
        "A-E-1": create_a_e_1_via_enclosure(target_dir / "a_e_1_via_enclosure.gds"),
        "A-OK-1": create_a_ok_1_clean(target_dir / "a_ok_1_clean.gds"),
        "A-MIX-1": create_a_mix_1_combined(target_dir / "a_mix_1_combined.gds"),
        "A-DBU-1": create_a_dbu_1_high_res(target_dir / "a_dbu_1_high_res.gds"),
    }
    return fixtures


if __name__ == "__main__":
    print(f"Generating fixtures in {FIXTURES_DIR}...")
    paths = generate_all_fixtures()
    for name, p in paths.items():
        print(f"  {name}: {p.name}")
