"""Tests for BenchmarkGenerator: 100-case dataset creation, cryptographic hashing, and oracle verification."""

from pathlib import Path
import pytest

from klayout_drc.benchmark.generator import BenchmarkGenerator, RULE_FAMILIES
from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.types import DifficultyTier
from klayout_drc.config import DRCJobConfig
from klayout_drc.parser import DRCParser
from klayout_drc.profile import DRCProfileManager
from klayout_drc.runner import DRCRunner

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "test_data" / "benchmark_v1"


def test_benchmark_generator_generates_100_cases(tmp_path: Path):
    """Verify that BenchmarkGenerator creates all 100 cases with exact tier and rule distributions."""
    gen = BenchmarkGenerator()
    manifest = gen.generate_all(tmp_path)

    # 1. Total count
    assert manifest.case_count == 100
    assert len(manifest.cases) == 100

    # 2. Rule distribution: 20 per rule family
    rule_counts: dict[str, int] = {}
    for case in manifest.cases:
        rule_counts[case.rule_id] = rule_counts.get(case.rule_id, 0) + 1

    for rule in RULE_FAMILIES:
        assert rule_counts.get(rule, 0) == 20, f"Expected 20 cases for {rule}, got {rule_counts.get(rule, 0)}"

    # 3. Tier distribution per rule: 10 isolated, 4 boundary, 3 interaction, 3 negative
    for rule in RULE_FAMILIES:
        rule_cases = [c for c in manifest.cases if c.rule_id == rule]
        tier_counts = {t: 0 for t in DifficultyTier}
        for c in rule_cases:
            tier_counts[c.tier] += 1

        assert tier_counts[DifficultyTier.ISOLATED] == 10, f"{rule} isolated count: {tier_counts[DifficultyTier.ISOLATED]}"
        assert tier_counts[DifficultyTier.BOUNDARY] == 4, f"{rule} boundary count: {tier_counts[DifficultyTier.BOUNDARY]}"
        assert tier_counts[DifficultyTier.INTERACTION] == 3, f"{rule} interaction count: {tier_counts[DifficultyTier.INTERACTION]}"
        assert tier_counts[DifficultyTier.NEGATIVE] == 3, f"{rule} negative count: {tier_counts[DifficultyTier.NEGATIVE]}"

    # 4. Verify all GDS files exist and hashes match
    integrity = BenchmarkManifestManager.verify_integrity(manifest, tmp_path)
    assert all(integrity.values()), f"Some GDS files failed integrity check: {[k for k, v in integrity.items() if not v]}"

    # 5. Check manifest.json was persisted on disk
    manifest_on_disk = tmp_path / "manifest.json"
    assert manifest_on_disk.exists()
    loaded_manifest = BenchmarkManifestManager.load(manifest_on_disk)
    assert loaded_manifest.case_count == 100


def test_benchmark_v1_manifest_and_sha256_integrity():
    """Verify that the checked-in test_data/benchmark_v1 dataset has 100% valid SHA-256 hashes."""
    manifest_path = BENCHMARK_DIR / "manifest.json"
    assert manifest_path.exists(), f"Benchmark manifest missing at: {manifest_path}"

    manifest = BenchmarkManifestManager.load(manifest_path)
    assert manifest.case_count == 100

    integrity = BenchmarkManifestManager.verify_integrity(manifest, BENCHMARK_DIR)
    failed = [case_id for case_id, ok in integrity.items() if not ok]
    assert len(failed) == 0, f"Integrity check failed for {len(failed)} cases: {failed}"


@pytest.mark.parametrize(
    "case_id",
    [
        "m1_w1_iso_01",
        "m1_w1_bnd_01",
        "m1_w1_bnd_04",
        "m1_w1_int_01",
        "m1_w1_neg_01",
        "m2_w1_iso_01",
        "m2_w1_bnd_04",
        "m1_a1_iso_01",
        "m1_a1_bnd_03",
        "m1_a1_int_01",
        "m1_s1_iso_01",
        "m1_s1_bnd_03",
        "m1_s1_int_01",
        "m1_s1_neg_03",
        "v1_w1_iso_01",
        "v1_w1_iso_06",
        "v1_w1_bnd_04",
        "v1_w1_int_01",
    ],
)
def test_benchmark_v1_oracle_spot_check(case_id: str, tmp_path: Path):
    """Spot-check representative benchmark cases against live ASAP7 curated DRC engine."""
    manifest_path = BENCHMARK_DIR / "manifest.json"
    manifest = BenchmarkManifestManager.load(manifest_path)
    case_map = {c.case_id: c for c in manifest.cases}
    case = case_map[case_id]

    gds_path = BENCHMARK_DIR / case.gds_rel_path
    rdb_path = tmp_path / f"{case_id}.lyrdb"

    mgr = DRCProfileManager()
    profile = mgr.get_profile("asap7_curated")
    cfg = DRCJobConfig(
        input_gds=gds_path,
        drc_script=profile.deck_path,
        output_lyrdb=rdb_path,
        param_in_gds=profile.param_in_gds,
        param_report=profile.param_report,
    )
    runner = DRCRunner(cfg)
    runner.run()

    parser = DRCParser()
    db = parser.parse(rdb_path)
    actual_violations = {c.name: c.count for c in db.categories if c.count > 0}
    actual_total = sum(actual_violations.values())

    assert actual_total == case.expected_initial_violations, (
        f"Mismatch for {case_id}: expected {case.expected_initial_violations}, got {actual_total} ({actual_violations})"
    )
    assert set(actual_violations.keys()) == set(case.expected_rules), (
        f"Rule category mismatch for {case_id}: expected {case.expected_rules}, got {list(actual_violations.keys())}"
    )
