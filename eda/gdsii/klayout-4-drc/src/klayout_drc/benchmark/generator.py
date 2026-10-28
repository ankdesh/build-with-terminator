"""Deterministic layout generator for the 100-case ASAP7 BEOL benchmark suite.

Constructs 20 cases per rule family across 4 difficulty tiers:
  - 10 Isolated
  - 4 Boundary
  - 3 Interaction
  - 3 Negative
Total: 100 cases across M1.W.1, M2.W.1, M1.A.1, M1.S.1, V1.W.1.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import pya

from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.mutations import (
    create_area_and_spacing_interaction,
    create_area_pad,
    create_cross_shaped_pad,
    create_jog_wire,
    create_l_bend_wire,
    create_l_shaped_pad,
    create_notched_wire,
    create_parallel_wires,
    create_stepped_wire,
    create_straight_wire,
    create_t_junction_wire,
    create_three_parallel_wires,
    create_u_channel,
    create_via_array,
    create_via_cut,
    create_via_and_wire_interaction,
    create_width_and_spacing_interaction,
    write_layout,
)
from klayout_drc.benchmark.types import (
    BenchmarkCaseSpec,
    BenchmarkManifest,
    DifficultyTier,
)
from klayout_drc.config import (
    ASAP7_DBU_UM,
    ASAP7_LAYER_M1,
    ASAP7_LAYER_M2,
    ASAP7_LAYER_V1,
)

BENCHMARK_VERSION: str = "1.1.0"
BENCHMARK_DESCRIPTION: str = "ASAP7 7nm Predictive BEOL DRC Benchmark Suite (100 synthetic & boundary mutation cases)"
RULE_FAMILIES: List[str] = ["M1.W.1", "M2.W.1", "M1.A.1", "M1.S.1", "V1.W.1"]


class BenchmarkGenerator:
    """Orchestrates deterministic layout creation and manifest generation for the 100 benchmark cases."""

    def __init__(self, dbu_um: float = ASAP7_DBU_UM) -> None:
        if dbu_um != ASAP7_DBU_UM:
            raise ValueError("The frozen C1 catalog requires DBU 0.00025 um")
        self.dbu_um = dbu_um

    def generate_all(self, output_dir: Path) -> BenchmarkManifest:
        """Generate all 100 benchmark GDS files and save the manifest.json index.

        Args:
            output_dir: Root directory for the benchmark dataset (e.g. test_data/benchmark_v1).

        Returns:
            The complete, cryptographically verified BenchmarkManifest.
        """
        cases_dir = output_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)

        specs: List[BenchmarkCaseSpec] = []

        # 1. Generate 20 cases for M1.W.1
        specs.extend(self._generate_m1_w1_cases(cases_dir))

        # 2. Generate 20 cases for M2.W.1
        specs.extend(self._generate_m2_w1_cases(cases_dir))

        # 3. Generate 20 cases for M1.A.1
        specs.extend(self._generate_m1_a1_cases(cases_dir))

        # 4. Generate 20 cases for M1.S.1
        specs.extend(self._generate_m1_s1_cases(cases_dir))

        # 5. Generate 20 cases for V1.W.1
        specs.extend(self._generate_v1_w1_cases(cases_dir))

        assert len(specs) == 100, f"Expected exactly 100 cases, generated {len(specs)}"

        manifest = BenchmarkManifest(
            benchmark_version=BENCHMARK_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            description=BENCHMARK_DESCRIPTION,
            rule_families=list(RULE_FAMILIES),
            cases=specs,
        )

        from .acceptance import accept_manifest
        manifest = accept_manifest(manifest, output_dir)
        manifest_path = output_dir / "manifest.json"
        BenchmarkManifestManager.save(manifest, manifest_path)
        return manifest

    def _write_and_build_spec(
        self,
        layout: pya.Layout,
        cases_dir: Path,
        case_id: str,
        rule_id: str,
        tier: DifficultyTier,
        expected_violations: int,
        expected_rules: List[str],
        description: str,
        tags: List[str],
    ) -> BenchmarkCaseSpec:
        """Write layout to disk and compute cryptographic SHA-256 hash."""
        gds_filename = f"{case_id}.gds"
        full_gds_path = cases_dir / gds_filename
        write_layout(layout, full_gds_path)

        sha256 = BenchmarkManifestManager.compute_sha256(full_gds_path)
        rel_path = f"cases/{gds_filename}"

        return BenchmarkCaseSpec(
            case_id=case_id,
            rule_id=rule_id,
            tier=tier,
            gds_rel_path=rel_path,
            sha256=sha256,
            expected_initial_violations=expected_violations,
            expected_rules=expected_rules,
            description=description,
            tags=tags,
        )

    # -----------------------------------------------------------------------
    # 1. M1.W.1 Case Definitions (20 cases)
    # -----------------------------------------------------------------------
    def _generate_m1_w1_cases(self, cases_dir: Path) -> List[BenchmarkCaseSpec]:
        specs: List[BenchmarkCaseSpec] = []
        rule = "M1.W.1"

        # Isolated (10 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.010, 0.100, True),
            cases_dir, "m1_w1_iso_01", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M1 wire with width 10nm (< 18nm)", ["width", "vertical", "gross_defect"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.012, 0.080, True),
            cases_dir, "m1_w1_iso_02", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M1 wire with width 12nm (< 18nm)", ["width", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.014, 0.120, True),
            cases_dir, "m1_w1_iso_03", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M1 wire with width 14nm (< 18nm)", ["width", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.015, 0.100, True),
            cases_dir, "m1_w1_iso_04", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M1 wire with width 15nm (< 18nm)", ["width", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.016, 0.060, True),
            cases_dir, "m1_w1_iso_05", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M1 wire with width 16nm (< 18nm)", ["width", "vertical", "short_run"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.012, 0.100, False),
            cases_dir, "m1_w1_iso_06", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight horizontal M1 wire with width 12nm (< 18nm)", ["width", "horizontal"]
        ))
        specs.append(self._write_and_build_spec(
            create_notched_wire(ASAP7_LAYER_M1, 0.024, 0.014, 0.120, 0.030, 0.040),
            cases_dir, "m1_w1_iso_07", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M1 wire with narrow 14nm edge notch", ["width", "notch"]
        ))
        specs.append(self._write_and_build_spec(
            create_stepped_wire(ASAP7_LAYER_M1, 0.024, 0.012, (0.030, 0.040, 0.030)),
            cases_dir, "m1_w1_iso_08", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M1 wire with narrow 12nm bottleneck segment", ["width", "stepped", "bottleneck"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_bend_wire(ASAP7_LAYER_M1, 0.014, 0.060, 0.024, 0.060),
            cases_dir, "m1_w1_iso_09", rule, DifficultyTier.ISOLATED, 1, [rule],
            "L-bend M1 wire with narrow 14nm vertical leg", ["width", "l_bend"]
        ))
        specs.append(self._write_and_build_spec(
            create_t_junction_wire(ASAP7_LAYER_M1, 0.024, 0.100, 0.012, 0.050, 0.030),
            cases_dir, "m1_w1_iso_10", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M1 T-junction with narrow 12nm branch", ["width", "t_junction"]
        ))

        # Boundary (4 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.01775, 0.100, True),
            cases_dir, "m1_w1_bnd_01", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M1 wire at width 17.75nm (-1 DBU grid step below limit)", ["width", "boundary", "1dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.01750, 0.100, True),
            cases_dir, "m1_w1_bnd_02", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M1 wire at width 17.50nm (-2 DBU grid steps below limit)", ["width", "boundary", "2dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.01775, 0.100, False),
            cases_dir, "m1_w1_bnd_03", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "Horizontal M1 wire at width 17.75nm (-1 DBU grid step)", ["width", "boundary", "horizontal"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.018, 0.100, True),
            cases_dir, "m1_w1_bnd_04", rule, DifficultyTier.BOUNDARY, 0, [],
            "M1 wire exactly at specification threshold 18nm (legal boundary)", ["width", "boundary", "exact_threshold"]
        ))

        # Interaction (3 cases)
        # Compound: Spaced pair (40nm wires, 14nm space) + narrow wire (14nm width)
        l_w_s = pya.Layout()
        l_w_s.dbu = self.dbu_um
        top_ws = l_w_s.create_cell("TOP")
        l_m1_ws = l_w_s.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        top_ws.shapes(l_m1_ws).insert(pya.Box(0, 0, 160, 400))       # Track 1: 40nm x 100nm
        top_ws.shapes(l_m1_ws).insert(pya.Box(216, 0, 376, 400))     # Track 2: 40nm x 100nm (spacing 14nm = 56 DBU)
        top_ws.shapes(l_m1_ws).insert(pya.Box(500, 0, 556, 400))     # Track 3: 14nm width (56 DBU) -> M1.W.1
        specs.append(self._write_and_build_spec(
            l_w_s,
            cases_dir, "m1_w1_int_01", rule, DifficultyTier.INTERACTION, 2, ["M1.W.1", "M1.S.1"],
            "Compound layout with M1.S.1 spacing pair (14nm space) and M1.W.1 narrow wire (14nm)", ["compound", "width", "spacing"]
        ))
        # Narrow M1 wire (14nm width) with rectangular V1 via cut (18nm x 12nm, height 12nm -> 1 V1.W.1 violation)
        specs.append(self._write_and_build_spec(
            create_via_and_wire_interaction(ASAP7_LAYER_V1, ASAP7_LAYER_M1, 0.018, 0.012, 0.014, 0.100),
            cases_dir, "m1_w1_int_02", rule, DifficultyTier.INTERACTION, 2, ["M1.W.1", "V1.W.1"],
            "M1 narrow wire (14nm) coupled with rectangular V1 via (18nm x 12nm)", ["compound", "width", "via"]
        ))
        # Two narrow bottlenecks along one wire
        l_stepped_dual = pya.Layout()
        l_stepped_dual.dbu = self.dbu_um
        top = l_stepped_dual.create_cell("TOP")
        l_idx = l_stepped_dual.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        top.shapes(l_idx).insert(pya.Box(0, 0, 48, 120))          # 12nm bottleneck 1 (48 DBU)
        top.shapes(l_idx).insert(pya.Box(0, 120, 96, 240))        # 24nm wide
        top.shapes(l_idx).insert(pya.Box(0, 240, 56, 360))        # 14nm bottleneck 2 (56 DBU)
        specs.append(self._write_and_build_spec(
            l_stepped_dual,
            cases_dir, "m1_w1_int_03", rule, DifficultyTier.INTERACTION, 2, [rule],
            "Stepped M1 wire with dual independent width bottlenecks (12nm and 14nm)", ["compound", "width", "dual_violation"]
        ))

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.018, 0.100, True),
            cases_dir, "m1_w1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal straight M1 wire (18nm width)", ["negative", "clean", "legal_wire"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.028, 0.120, True),
            cases_dir, "m1_w1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean wide M1 wire (28nm width)", ["negative", "clean", "wide_wire"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_bend_wire(ASAP7_LAYER_M1, 0.020, 0.060, 0.020, 0.060),
            cases_dir, "m1_w1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal L-bend M1 wire (20nm width)", ["negative", "clean", "l_bend"]
        ))

        return specs

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.018, 0.100, True),
            cases_dir, "m1_w1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal straight M1 wire (18nm width)", ["negative", "clean", "legal_wire"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M1, 0.028, 0.120, True),
            cases_dir, "m1_w1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean wide M1 wire (28nm width)", ["negative", "clean", "wide_wire"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_bend_wire(ASAP7_LAYER_M1, 0.020, 0.060, 0.020, 0.060),
            cases_dir, "m1_w1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal L-bend M1 wire (20nm width)", ["negative", "clean", "l_bend"]
        ))

        return specs

    # -----------------------------------------------------------------------
    # 2. M2.W.1 Case Definitions (20 cases)
    # -----------------------------------------------------------------------
    def _generate_m2_w1_cases(self, cases_dir: Path) -> List[BenchmarkCaseSpec]:
        specs: List[BenchmarkCaseSpec] = []
        rule = "M2.W.1"

        # Isolated (10 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.010, 0.100, True),
            cases_dir, "m2_w1_iso_01", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M2 wire with width 10nm (< 18nm)", ["width", "vertical", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.012, 0.080, True),
            cases_dir, "m2_w1_iso_02", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M2 wire with width 12nm (< 18nm)", ["width", "vertical", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.014, 0.120, True),
            cases_dir, "m2_w1_iso_03", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M2 wire with width 14nm (< 18nm)", ["width", "vertical", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.015, 0.100, True),
            cases_dir, "m2_w1_iso_04", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M2 wire with width 15nm (< 18nm)", ["width", "vertical", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.016, 0.060, True),
            cases_dir, "m2_w1_iso_05", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight vertical M2 wire with width 16nm (< 18nm)", ["width", "vertical", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.012, 0.100, False),
            cases_dir, "m2_w1_iso_06", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Straight horizontal M2 wire with width 12nm (< 18nm)", ["width", "horizontal", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_notched_wire(ASAP7_LAYER_M2, 0.024, 0.014, 0.120, 0.030, 0.040),
            cases_dir, "m2_w1_iso_07", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M2 wire with narrow 14nm edge notch", ["width", "notch", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_stepped_wire(ASAP7_LAYER_M2, 0.024, 0.012, (0.030, 0.040, 0.030)),
            cases_dir, "m2_w1_iso_08", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M2 wire with narrow 12nm bottleneck segment", ["width", "stepped", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_bend_wire(ASAP7_LAYER_M2, 0.014, 0.060, 0.024, 0.060),
            cases_dir, "m2_w1_iso_09", rule, DifficultyTier.ISOLATED, 1, [rule],
            "L-bend M2 wire with narrow 14nm vertical leg", ["width", "l_bend", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_t_junction_wire(ASAP7_LAYER_M2, 0.024, 0.100, 0.012, 0.050, 0.030),
            cases_dir, "m2_w1_iso_10", rule, DifficultyTier.ISOLATED, 1, [rule],
            "M2 T-junction with narrow 12nm branch", ["width", "t_junction", "m2"]
        ))

        # Boundary (4 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.01775, 0.100, True),
            cases_dir, "m2_w1_bnd_01", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M2 wire at width 17.75nm (-1 DBU grid step below limit)", ["width", "boundary", "m2", "1dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.01750, 0.100, True),
            cases_dir, "m2_w1_bnd_02", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M2 wire at width 17.50nm (-2 DBU grid steps below limit)", ["width", "boundary", "m2", "2dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.01775, 0.100, False),
            cases_dir, "m2_w1_bnd_03", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "Horizontal M2 wire at width 17.75nm (-1 DBU grid step)", ["width", "boundary", "m2", "horizontal"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.018, 0.100, True),
            cases_dir, "m2_w1_bnd_04", rule, DifficultyTier.BOUNDARY, 0, [],
            "M2 wire exactly at specification threshold 18nm (legal boundary)", ["width", "boundary", "m2", "exact_threshold"]
        ))

        # Interaction (3 cases)
        specs.append(self._write_and_build_spec(
            create_via_and_wire_interaction(ASAP7_LAYER_V1, ASAP7_LAYER_M2, 0.018, 0.012, 0.014, 0.100),
            cases_dir, "m2_w1_int_01", rule, DifficultyTier.INTERACTION, 2, ["M2.W.1", "V1.W.1"],
            "M2 narrow wire (14nm) coupled with rectangular V1 via (18nm x 12nm)", ["compound", "m2", "via"]
        ))
        # M2 narrow wire coupled with M1 wire crossing
        l_cross = pya.Layout()
        l_cross.dbu = self.dbu_um
        top = l_cross.create_cell("TOP")
        l_m1 = l_cross.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        l_m2 = l_cross.layer(ASAP7_LAYER_M2[0], ASAP7_LAYER_M2[1])
        top.shapes(l_m1).insert(pya.Box(0, 0, 48, 400))  # M1 narrow wire (12nm)
        top.shapes(l_m2).insert(pya.Box(0, 160, 400, 208)) # M2 narrow wire (12nm)
        specs.append(self._write_and_build_spec(
            l_cross,
            cases_dir, "m2_w1_int_02", rule, DifficultyTier.INTERACTION, 2, ["M1.W.1", "M2.W.1"],
            "Cross-layer routing: M1 narrow wire (12nm) intersecting M2 narrow wire (12nm)", ["compound", "cross_layer"]
        ))
        # Two narrow bottlenecks along one M2 wire
        l_stepped_m2 = pya.Layout()
        l_stepped_m2.dbu = self.dbu_um
        top_m2 = l_stepped_m2.create_cell("TOP")
        l_m2_idx = l_stepped_m2.layer(ASAP7_LAYER_M2[0], ASAP7_LAYER_M2[1])
        top_m2.shapes(l_m2_idx).insert(pya.Box(0, 0, 48, 120))          # 12nm bottleneck
        top_m2.shapes(l_m2_idx).insert(pya.Box(0, 120, 96, 240))        # 24nm wide
        top_m2.shapes(l_m2_idx).insert(pya.Box(0, 240, 56, 360))        # 14nm bottleneck
        specs.append(self._write_and_build_spec(
            l_stepped_m2,
            cases_dir, "m2_w1_int_03", rule, DifficultyTier.INTERACTION, 2, [rule],
            "Stepped M2 wire with dual independent width bottlenecks", ["compound", "m2", "dual_violation"]
        ))

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.018, 0.100, True),
            cases_dir, "m2_w1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal straight M2 wire (18nm width)", ["negative", "clean", "m2"]
        ))
        specs.append(self._write_and_build_spec(
            create_straight_wire(ASAP7_LAYER_M2, 0.028, 0.120, True),
            cases_dir, "m2_w1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean wide M2 wire (28nm width)", ["negative", "clean", "m2", "wide_wire"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_bend_wire(ASAP7_LAYER_M2, 0.020, 0.060, 0.020, 0.060),
            cases_dir, "m2_w1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal L-bend M2 wire (20nm width)", ["negative", "clean", "m2", "l_bend"]
        ))

        return specs

    # -----------------------------------------------------------------------
    # 3. M1.A.1 Case Definitions (20 cases)
    # -----------------------------------------------------------------------
    def _generate_m1_a1_cases(self, cases_dir: Path) -> List[BenchmarkCaseSpec]:
        specs: List[BenchmarkCaseSpec] = []
        rule = "M1.A.1"

        # Isolated (10 cases) - sub-504nm2 pads
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.018),
            cases_dir, "m1_a1_iso_01", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Square M1 pad 18nm x 18nm (area 324nm2 < 504nm2)", ["area", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.020),
            cases_dir, "m1_a1_iso_02", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 18nm x 20nm (area 360nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.022),
            cases_dir, "m1_a1_iso_03", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 18nm x 22nm (area 396nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.024),
            cases_dir, "m1_a1_iso_04", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 18nm x 24nm (area 432nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.026),
            cases_dir, "m1_a1_iso_05", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 18nm x 26nm (area 468nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.020, 0.020),
            cases_dir, "m1_a1_iso_06", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Square M1 pad 20nm x 20nm (area 400nm2 < 504nm2)", ["area", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.022, 0.020),
            cases_dir, "m1_a1_iso_07", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 22nm x 20nm (area 440nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_l_shaped_pad(ASAP7_LAYER_M1, 0.018, 0.020, 0.018, 0.024),
            cases_dir, "m1_a1_iso_08", rule, DifficultyTier.ISOLATED, 1, [rule],
            "L-shaped M1 pad with sub-504nm2 total area (~432nm2)", ["area", "l_shaped"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.025),
            cases_dir, "m1_a1_iso_09", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 18nm x 25nm (area 450nm2 < 504nm2)", ["area", "pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.019, 0.024),
            cases_dir, "m1_a1_iso_10", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular M1 pad 19nm x 24nm (area 456nm2 < 504nm2)", ["area", "pad"]
        ))

        # Boundary (4 cases)
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.02775),
            cases_dir, "m1_a1_bnd_01", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M1 pad with area 499.5nm2 (just below 504nm2 threshold)", ["area", "boundary", "1dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.02750),
            cases_dir, "m1_a1_bnd_02", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "M1 pad with area 495.0nm2 (just below 504nm2 threshold)", ["area", "boundary", "2dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.02800),
            cases_dir, "m1_a1_bnd_03", rule, DifficultyTier.BOUNDARY, 0, [],
            "M1 pad with area 504.0nm2 (exact threshold boundary)", ["area", "boundary", "exact_threshold"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.02825),
            cases_dir, "m1_a1_bnd_04", rule, DifficultyTier.BOUNDARY, 0, [],
            "M1 pad with area 508.5nm2 (just above 504nm2 threshold)", ["area", "boundary", "legal"]
        ))

        # Interaction (3 cases)
        specs.append(self._write_and_build_spec(
            create_area_and_spacing_interaction(ASAP7_LAYER_M1, 0.018, 0.020, 0.040, 0.100, 0.014),
            cases_dir, "m1_a1_int_01", rule, DifficultyTier.INTERACTION, 1, ["M1.A.1"],
            "Sub-area M1 pad (360nm2) adjacent to M1 trunk", ["compound", "area"]
        ))
        # Two independent sub-area pads separated by legal spacing
        l_dual_pad = pya.Layout()
        l_dual_pad.dbu = self.dbu_um
        top_dp = l_dual_pad.create_cell("TOP")
        l_dp = l_dual_pad.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        top_dp.shapes(l_dp).insert(pya.Box(0, 0, 72, 80))        # 18nm x 20nm (360 nm2)
        top_dp.shapes(l_dp).insert(pya.Box(200, 0, 272, 80))    # 18nm x 20nm (360 nm2)
        specs.append(self._write_and_build_spec(
            l_dual_pad,
            cases_dir, "m1_a1_int_02", rule, DifficultyTier.INTERACTION, 2, [rule],
            "Dual independent sub-area M1 pads (360nm2 each)", ["compound", "area", "dual_pad"]
        ))
        # Sub-area pad with rectangular V1 via (18nm x 12nm)
        specs.append(self._write_and_build_spec(
            create_via_and_wire_interaction(ASAP7_LAYER_V1, ASAP7_LAYER_M1, 0.018, 0.012, 0.018, 0.020),
            cases_dir, "m1_a1_int_03", rule, DifficultyTier.INTERACTION, 2, ["M1.A.1", "V1.W.1"],
            "Sub-area M1 pad (360nm2) coupled with rectangular V1 via (18nm x 12nm)", ["compound", "area", "via"]
        ))

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.040),
            cases_dir, "m1_a1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean standard M1 landing pad (area 720nm2 > 504nm2)", ["negative", "clean", "landing_pad"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.030, 0.030),
            cases_dir, "m1_a1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean square M1 plate (area 900nm2 > 504nm2)", ["negative", "clean", "plate"]
        ))
        specs.append(self._write_and_build_spec(
            create_area_pad(ASAP7_LAYER_M1, 0.018, 0.060),
            cases_dir, "m1_a1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean M1 trace segment (area 1080nm2 > 504nm2)", ["negative", "clean", "trace"]
        ))

        return specs

    # -----------------------------------------------------------------------
    # 4. M1.S.1 Case Definitions (20 cases)
    # -----------------------------------------------------------------------
    def _generate_m1_s1_cases(self, cases_dir: Path) -> List[BenchmarkCaseSpec]:
        specs: List[BenchmarkCaseSpec] = []
        rule = "M1.S.1"

        # Isolated (10 cases) - parallel edges > 36nm, spacing < 18nm
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.080, 0.010, True),
            cases_dir, "m1_s1_iso_01", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires with spacing 10nm (< 18nm)", ["spacing", "vertical", "gross_defect"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.080, 0.012, True),
            cases_dir, "m1_s1_iso_02", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires with spacing 12nm (< 18nm)", ["spacing", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.080, 0.014, True),
            cases_dir, "m1_s1_iso_03", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires with spacing 14nm (< 18nm)", ["spacing", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.080, 0.015, True),
            cases_dir, "m1_s1_iso_04", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires with spacing 15nm (< 18nm)", ["spacing", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.080, 0.016, True),
            cases_dir, "m1_s1_iso_05", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires with spacing 16nm (< 18nm)", ["spacing", "vertical"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.012, False),
            cases_dir, "m1_s1_iso_06", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Horizontal parallel M1 wires with spacing 12nm (< 18nm)", ["spacing", "horizontal"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.014, False),
            cases_dir, "m1_s1_iso_07", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Horizontal parallel M1 wires with spacing 14nm (< 18nm)", ["spacing", "horizontal"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.050, 0.120, 0.014, True),
            cases_dir, "m1_s1_iso_08", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Wide parallel M1 wires (50nm width) with spacing 14nm", ["spacing", "wide_wires"]
        ))
        # Staggered parallel M1 wires (both wires 40nm x 80nm, overlap 60nm, spacing 14nm)
        l_stag = pya.Layout()
        l_stag.dbu = self.dbu_um
        top_st = l_stag.create_cell("TOP")
        l_m1_st = l_stag.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        top_st.shapes(l_m1_st).insert(pya.Box(0, 0, 160, 320))        # 40nm x 80nm
        top_st.shapes(l_m1_st).insert(pya.Box(216, 80, 376, 400))    # 40nm x 80nm, shifted by 20nm Y, space 14nm = 56 DBU
        specs.append(self._write_and_build_spec(
            l_stag,
            cases_dir, "m1_s1_iso_09", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Staggered parallel M1 wires (spacing 14nm, 60nm overlap)", ["spacing", "staggered"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.060, 0.014, True),
            cases_dir, "m1_s1_iso_10", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Parallel M1 wires (60nm length) with spacing 14nm", ["spacing", "short_run"]
        ))

        # Boundary (4 cases)
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.01775, True),
            cases_dir, "m1_s1_bnd_01", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "Parallel M1 wires at spacing 17.75nm (-1 DBU grid step below limit)", ["spacing", "boundary", "1dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.01750, True),
            cases_dir, "m1_s1_bnd_02", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "Parallel M1 wires at spacing 17.50nm (-2 DBU grid steps below limit)", ["spacing", "boundary", "2dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.01800, True),
            cases_dir, "m1_s1_bnd_03", rule, DifficultyTier.BOUNDARY, 0, [],
            "Parallel M1 wires at exact threshold spacing 18.0nm (legal boundary)", ["spacing", "boundary", "exact_threshold"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.01825, True),
            cases_dir, "m1_s1_bnd_04", rule, DifficultyTier.BOUNDARY, 0, [],
            "Parallel M1 wires at spacing 18.25nm (+1 DBU grid step above limit)", ["spacing", "boundary", "legal"]
        ))

        # Interaction (3 cases)
        specs.append(self._write_and_build_spec(
            create_three_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.014, 0.014),
            cases_dir, "m1_s1_int_01", rule, DifficultyTier.INTERACTION, 2, [rule],
            "Three parallel M1 wires with dual spacing violations (14nm and 14nm)", ["compound", "spacing", "bus_track"]
        ))
        # Spacing violation + width violation: pair spaced at 14nm + track 3 at 14nm width
        l_s_w = pya.Layout()
        l_s_w.dbu = self.dbu_um
        top_sw = l_s_w.create_cell("TOP")
        l_m1_sw = l_s_w.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        top_sw.shapes(l_m1_sw).insert(pya.Box(0, 0, 160, 400))       # Track 1 (40nm x 100nm)
        top_sw.shapes(l_m1_sw).insert(pya.Box(216, 0, 376, 400))     # Track 2 (spacing 14nm = 56 DBU) -> M1.S.1
        top_sw.shapes(l_m1_sw).insert(pya.Box(500, 0, 556, 400))     # Track 3 (14nm width) -> M1.W.1
        specs.append(self._write_and_build_spec(
            l_s_w,
            cases_dir, "m1_s1_int_02", rule, DifficultyTier.INTERACTION, 2, ["M1.S.1", "M1.W.1"],
            "M1 parallel track pair at 14nm spacing plus narrow 14nm wire", ["compound", "spacing", "width"]
        ))
        # Spacing violation + V1 via cut violation: pair spaced at 14nm + rectangular V1 cut (18nm x 12nm)
        l_sp_via = pya.Layout()
        l_sp_via.dbu = self.dbu_um
        top_sv = l_sp_via.create_cell("TOP")
        l_m1_sv = l_sp_via.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        l_v1_sv = l_sp_via.layer(ASAP7_LAYER_V1[0], ASAP7_LAYER_V1[1])
        top_sv.shapes(l_m1_sv).insert(pya.Box(0, 0, 160, 400))       # Track 1 (40nm x 100nm)
        top_sv.shapes(l_m1_sv).insert(pya.Box(216, 0, 376, 400))     # Track 2 (spacing 14nm = 56 DBU)
        top_sv.shapes(l_v1_sv).insert(pya.Box(20, 20, 92, 68))       # V1 rectangular cut (18nm x 12nm = 72 DBU x 48 DBU) -> 1 V1.W.1
        specs.append(self._write_and_build_spec(
            l_sp_via,
            cases_dir, "m1_s1_int_03", rule, DifficultyTier.INTERACTION, 2, ["M1.S.1", "V1.W.1"],
            "M1 tight spacing (14nm) coupled with rectangular V1 via cut (18nm x 12nm)", ["compound", "spacing", "via"]
        ))

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.018, True),
            cases_dir, "m1_s1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean parallel M1 wires with legal 18nm spacing", ["negative", "clean", "legal_spacing"]
        ))
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.100, 0.024, True),
            cases_dir, "m1_s1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean parallel M1 wires with wide 24nm spacing", ["negative", "clean", "wide_spacing"]
        ))
        # Short parallel shapes (edge length 30nm <= 36nm) exempt by upstream rule
        specs.append(self._write_and_build_spec(
            create_parallel_wires(ASAP7_LAYER_M1, 0.040, 0.030, 0.012, True),
            cases_dir, "m1_s1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Short parallel stubs (30nm length <= 36nm filter) with 12nm spacing (rule-exempt clean)",
            ["negative", "clean", "filter_exempt"]
        ))

        return specs

    # -----------------------------------------------------------------------
    # 5. V1.W.1 Case Definitions (20 cases)
    # -----------------------------------------------------------------------
    def _generate_v1_w1_cases(self, cases_dir: Path) -> List[BenchmarkCaseSpec]:
        specs: List[BenchmarkCaseSpec] = []
        rule = "V1.W.1"

        # Isolated (10 cases) - undersized via cuts (< 18nm)
        # Note: In KLayout DRC, square cuts violate in both X and Y directions (2 edge-pair markers),
        # while rectangular cuts with one legal dimension violate in only 1 direction (1 edge-pair marker).
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.010, 0.010),
            cases_dir, "v1_w1_iso_01", rule, DifficultyTier.ISOLATED, 2, [rule],
            "Square V1 cut 10nm x 10nm (< 18nm, violates both dimensions)", ["via", "square", "gross_defect"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.012, 0.012),
            cases_dir, "v1_w1_iso_02", rule, DifficultyTier.ISOLATED, 2, [rule],
            "Square V1 cut 12nm x 12nm (< 18nm, violates both dimensions)", ["via", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.014, 0.014),
            cases_dir, "v1_w1_iso_03", rule, DifficultyTier.ISOLATED, 2, [rule],
            "Square V1 cut 14nm x 14nm (< 18nm, violates both dimensions)", ["via", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.015, 0.015),
            cases_dir, "v1_w1_iso_04", rule, DifficultyTier.ISOLATED, 2, [rule],
            "Square V1 cut 15nm x 15nm (< 18nm, violates both dimensions)", ["via", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.016, 0.016),
            cases_dir, "v1_w1_iso_05", rule, DifficultyTier.ISOLATED, 2, [rule],
            "Square V1 cut 16nm x 16nm (< 18nm, violates both dimensions)", ["via", "square"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.018, 0.012),
            cases_dir, "v1_w1_iso_06", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular V1 cut 18nm x 12nm (height < 18nm)", ["via", "rectangular"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.018, 0.014),
            cases_dir, "v1_w1_iso_07", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular V1 cut 18nm x 14nm (height < 18nm)", ["via", "rectangular"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.012, 0.018),
            cases_dir, "v1_w1_iso_08", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular V1 cut 12nm x 18nm (width < 18nm)", ["via", "rectangular"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.014, 0.020),
            cases_dir, "v1_w1_iso_09", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular V1 cut 14nm x 20nm (width < 18nm)", ["via", "rectangular"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.016, 0.018),
            cases_dir, "v1_w1_iso_10", rule, DifficultyTier.ISOLATED, 1, [rule],
            "Rectangular V1 cut 16nm x 18nm (width < 18nm)", ["via", "rectangular"]
        ))

        # Boundary (4 cases)
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.01775, 0.01775),
            cases_dir, "v1_w1_bnd_01", rule, DifficultyTier.BOUNDARY, 2, [rule],
            "Square V1 cut at 17.75nm x 17.75nm (-1 DBU grid step below limit)", ["via", "boundary", "1dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.01750, 0.01750),
            cases_dir, "v1_w1_bnd_02", rule, DifficultyTier.BOUNDARY, 2, [rule],
            "Square V1 cut at 17.50nm x 17.50nm (-2 DBU grid steps below limit)", ["via", "boundary", "2dbu"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.01800, 0.01775),
            cases_dir, "v1_w1_bnd_03", rule, DifficultyTier.BOUNDARY, 1, [rule],
            "Rectangular V1 cut at 18.0nm x 17.75nm (height -1 DBU)", ["via", "boundary", "rectangular"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.018, 0.018),
            cases_dir, "v1_w1_bnd_04", rule, DifficultyTier.BOUNDARY, 0, [],
            "Square V1 cut at exact threshold 18.0nm x 18.0nm (legal boundary)", ["via", "boundary", "exact_threshold"]
        ))

        # Interaction (3 cases)
        specs.append(self._write_and_build_spec(
            create_via_and_wire_interaction(ASAP7_LAYER_V1, ASAP7_LAYER_M1, 0.018, 0.012, 0.014, 0.100),
            cases_dir, "v1_w1_int_01", rule, DifficultyTier.INTERACTION, 2, ["V1.W.1", "M1.W.1"],
            "Rectangular V1 cut (18nm x 12nm) landing on narrow M1 wire (14nm)", ["compound", "via", "m1"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_and_wire_interaction(ASAP7_LAYER_V1, ASAP7_LAYER_M2, 0.018, 0.012, 0.014, 0.100),
            cases_dir, "v1_w1_int_02", rule, DifficultyTier.INTERACTION, 2, ["V1.W.1", "M2.W.1"],
            "Rectangular V1 cut (18nm x 12nm) landing on narrow M2 wire (14nm)", ["compound", "via", "m2"]
        ))
        # Dual rectangular via cuts
        specs.append(self._write_and_build_spec(
            create_via_array(ASAP7_LAYER_V1, 0.018, 0.012, 0.040, 2),
            cases_dir, "v1_w1_int_03", rule, DifficultyTier.INTERACTION, 2, [rule],
            "Dual rectangular V1 cuts (18nm x 12nm each)", ["compound", "via", "dual_via"]
        ))

        # Negative Clean (3 cases)
        specs.append(self._write_and_build_spec(
            create_via_cut(ASAP7_LAYER_V1, 0.018, 0.018),
            cases_dir, "v1_w1_neg_01", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal single V1 cut (18nm x 18nm)", ["negative", "clean", "legal_via"]
        ))
        specs.append(self._write_and_build_spec(
            create_via_array(ASAP7_LAYER_V1, 0.018, 0.018, 0.040, 2),
            cases_dir, "v1_w1_neg_02", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal dual V1 via array (18nm x 18nm cuts)", ["negative", "clean", "via_array"]
        ))
        # Legal via on legal M1 landing pad
        l_v1_pad = pya.Layout()
        l_v1_pad.dbu = self.dbu_um
        top_vp = l_v1_pad.create_cell("TOP")
        l_m1_vp = l_v1_pad.layer(ASAP7_LAYER_M1[0], ASAP7_LAYER_M1[1])
        l_v1_vp = l_v1_pad.layer(ASAP7_LAYER_V1[0], ASAP7_LAYER_V1[1])
        top_vp.shapes(l_m1_vp).insert(pya.Box(0, 0, 144, 144))  # 36nm x 36nm M1 pad
        top_vp.shapes(l_v1_vp).insert(pya.Box(36, 36, 108, 108)) # 18nm x 18nm V1 cut centered
        specs.append(self._write_and_build_spec(
            l_v1_pad,
            cases_dir, "v1_w1_neg_03", rule, DifficultyTier.NEGATIVE, 0, [],
            "Clean legal V1 via (18nm x 18nm) centered on legal M1 landing pad (36nm x 36nm)", ["negative", "clean", "enclosed_via"]
        ))

        return specs
