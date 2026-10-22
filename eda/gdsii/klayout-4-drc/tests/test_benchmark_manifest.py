"""Tests for benchmark manifest schema, serialization, filtering, and cryptographic hashing."""

import json
from pathlib import Path
import pytest

from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.types import (
    BenchmarkCaseSpec,
    BenchmarkManifest,
    BenchmarkSummary,
    BenchmarkVerdict,
    DifficultyTier,
    EvaluationResult,
)
from klayout_drc.config import DRCConfigurationError


def test_benchmark_case_spec_serialization():
    """Verify BenchmarkCaseSpec to_dict and from_dict roundtrip."""
    spec = BenchmarkCaseSpec(
        case_id="m1_w1_iso_01",
        rule_id="M1.W.1",
        tier=DifficultyTier.ISOLATED,
        gds_rel_path="cases/m1_w1_iso_01.gds",
        sha256="abc123def456",
        expected_initial_violations=1,
        expected_rules=["M1.W.1"],
        description="Test case description",
        tags=["width", "isolated"],
    )

    data = spec.to_dict()
    assert data["case_id"] == "m1_w1_iso_01"
    assert data["tier"] == "isolated"
    assert data["expected_initial_violations"] == 1

    restored = BenchmarkCaseSpec.from_dict(data)
    assert restored == spec


def test_manifest_manager_save_load(tmp_path: Path):
    """Verify BenchmarkManifestManager saving and loading from disk."""
    case1 = BenchmarkCaseSpec(
        case_id="m1_w1_iso_01",
        rule_id="M1.W.1",
        tier=DifficultyTier.ISOLATED,
        gds_rel_path="cases/m1_w1_iso_01.gds",
        sha256="hash1",
        expected_initial_violations=1,
        expected_rules=["M1.W.1"],
        description="Iso 1",
        tags=["isolated"],
    )
    case2 = BenchmarkCaseSpec(
        case_id="m1_s1_bnd_01",
        rule_id="M1.S.1",
        tier=DifficultyTier.BOUNDARY,
        gds_rel_path="cases/m1_s1_bnd_01.gds",
        sha256="hash2",
        expected_initial_violations=1,
        expected_rules=["M1.S.1"],
        description="Bnd 1",
        tags=["boundary"],
    )

    manifest = BenchmarkManifest(
        benchmark_version="1.0.0",
        created_at="2026-10-22T00:00:00Z",
        description="Test Manifest",
        rule_families=["M1.W.1", "M1.S.1"],
        cases=[case1, case2],
    )

    manifest_file = tmp_path / "manifest.json"
    BenchmarkManifestManager.save(manifest, manifest_file)

    loaded = BenchmarkManifestManager.load(manifest_file)
    assert loaded.benchmark_version == "1.0.0"
    assert loaded.case_count == 2
    assert loaded.cases[0].case_id == "m1_w1_iso_01"
    assert loaded.cases[1].case_id == "m1_s1_bnd_01"


def test_manifest_filter_cases():
    """Verify rule, tier, and limit filtering on benchmark manifest."""
    cases = [
        BenchmarkCaseSpec(
            case_id="c1", rule_id="M1.W.1", tier=DifficultyTier.ISOLATED,
            gds_rel_path="c1.gds", sha256="h1", expected_initial_violations=1,
            expected_rules=["M1.W.1"], description="c1",
        ),
        BenchmarkCaseSpec(
            case_id="c2", rule_id="M1.W.1", tier=DifficultyTier.BOUNDARY,
            gds_rel_path="c2.gds", sha256="h2", expected_initial_violations=1,
            expected_rules=["M1.W.1"], description="c2",
        ),
        BenchmarkCaseSpec(
            case_id="c3", rule_id="M2.W.1", tier=DifficultyTier.ISOLATED,
            gds_rel_path="c3.gds", sha256="h3", expected_initial_violations=1,
            expected_rules=["M2.W.1"], description="c3",
        ),
        BenchmarkCaseSpec(
            case_id="c4", rule_id="V1.W.1", tier=DifficultyTier.NEGATIVE,
            gds_rel_path="c4.gds", sha256="h4", expected_initial_violations=0,
            expected_rules=[], description="c4",
        ),
    ]
    manifest = BenchmarkManifest("1.0", "today", "desc", ["M1.W.1", "M2.W.1", "V1.W.1"], cases)

    # Filter by rule
    res_m1 = BenchmarkManifestManager.filter_cases(manifest, rules=["M1.W.1"])
    assert len(res_m1) == 2
    assert {c.case_id for c in res_m1} == {"c1", "c2"}

    # Filter by tier
    res_iso = BenchmarkManifestManager.filter_cases(manifest, tiers=[DifficultyTier.ISOLATED])
    assert len(res_iso) == 2
    assert {c.case_id for c in res_iso} == {"c1", "c3"}

    # Filter by rule and tier
    res_comb = BenchmarkManifestManager.filter_cases(
        manifest, rules=["M1.W.1"], tiers=[DifficultyTier.BOUNDARY]
    )
    assert len(res_comb) == 1
    assert res_comb[0].case_id == "c2"

    # Filter by limit
    res_lim = BenchmarkManifestManager.filter_cases(manifest, limit=2)
    assert len(res_lim) == 2


def test_manifest_integrity_verification(tmp_path: Path):
    """Verify cryptographic SHA-256 verification and detection of tampering."""
    test_file = tmp_path / "cases" / "test.gds"
    test_file.parent.mkdir(parents=True)
    test_file.write_bytes(b"ORIGINAL_GDS_BYTES_12345")

    valid_hash = BenchmarkManifestManager.compute_sha256(test_file)
    case = BenchmarkCaseSpec(
        case_id="test_case",
        rule_id="M1.W.1",
        tier=DifficultyTier.ISOLATED,
        gds_rel_path="cases/test.gds",
        sha256=valid_hash,
        expected_initial_violations=1,
        expected_rules=["M1.W.1"],
        description="test",
    )
    manifest = BenchmarkManifest("1.0", "now", "d", ["M1.W.1"], [case])

    # Check valid integrity
    status = BenchmarkManifestManager.verify_integrity(manifest, tmp_path)
    assert status["test_case"] is True

    # Tamper with file
    test_file.write_bytes(b"MODIFIED_TAMPERED_BYTES")
    status_tampered = BenchmarkManifestManager.verify_integrity(manifest, tmp_path)
    assert status_tampered["test_case"] is False

    # Non-existent file
    test_file.unlink()
    status_missing = BenchmarkManifestManager.verify_integrity(manifest, tmp_path)
    assert status_missing["test_case"] is False


def test_manifest_missing_file_raises():
    """Verify loading non-existent manifest raises DRCConfigurationError."""
    with pytest.raises(DRCConfigurationError, match="not found"):
        BenchmarkManifestManager.load(Path("/non/existent/manifest.json"))
