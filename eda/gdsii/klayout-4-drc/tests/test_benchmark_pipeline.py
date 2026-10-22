"""Integration tests for benchmark evaluator, scoring engine, and reporting pipeline."""

from pathlib import Path
import pytest

from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.types import (
    BenchmarkVerdict,
    DifficultyTier,
)
from klayout_drc.cli import (
    execute_benchmark_list,
    execute_benchmark_verify,
    execute_benchmark_evaluate,
)

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "test_data" / "benchmark_v1"


def test_evaluator_heuristic_sample(tmp_path: Path):
    """Verify BenchmarkEvaluator running heuristic repair across a 4-tier sample."""
    manifest_path = BENCHMARK_DIR / "manifest.json"
    manifest = BenchmarkManifestManager.load(manifest_path)

    # Pick 4 specific cases: 1 isolated (M1 width), 1 boundary clean, 1 negative clean, 1 boundary illegal
    selected_ids = {"m1_w1_iso_01", "m1_w1_bnd_04", "m1_w1_neg_01", "m1_w1_bnd_01"}
    cases = [c for c in manifest.cases if c.case_id in selected_ids]
    assert len(cases) == 4

    evaluator = BenchmarkEvaluator(
        base_dir=BENCHMARK_DIR,
        output_dir=tmp_path / "eval_out",
        profile_name="asap7_curated",
    )
    summary = evaluator.evaluate_batch(cases, mode="heuristic", verbose=False)

    assert summary.total_cases == 4
    # All 4 should achieve CLEAN_SUCCESS under heuristic (isolated and boundary widen; negative/clean stay 0)
    assert summary.clean_success_count >= 3
    assert summary.execution_error_count == 0

    # Verify summary files written to disk
    assert (evaluator.output_dir / "summary.json").exists()
    assert (evaluator.output_dir / "summary.csv").exists()
    assert (evaluator.output_dir / "report.md").exists()


def test_cli_benchmark_list_and_verify():
    """Verify CLI helper functions for benchmark-list and benchmark-verify."""
    # List filtered by M1.W.1 and boundary
    list_res = execute_benchmark_list(
        benchmark_dir=BENCHMARK_DIR,
        rules=["M1.W.1"],
        tiers=["boundary"],
    )
    assert list_res["status"] == "success"
    assert list_res["filtered_count"] == 4

    # Verify SHA-256 hashes of all 100 cases
    verify_res = execute_benchmark_verify(benchmark_dir=BENCHMARK_DIR)
    assert verify_res["status"] == "success"
    assert verify_res["all_valid"] is True
    assert verify_res["verified_cases"] == 100


def test_cli_benchmark_evaluate(tmp_path: Path):
    """Verify execute_benchmark_evaluate CLI entry point."""
    eval_res = execute_benchmark_evaluate(
        benchmark_dir=BENCHMARK_DIR,
        output_dir=tmp_path / "cli_eval",
        candidate_mode="heuristic",
        rules=["M1.W.1"],
        tiers=["isolated"],
        limit=2,
    )
    assert eval_res["status"] == "success"
    summary_data = eval_res["summary"]
    assert summary_data["total_cases"] == 2
    assert summary_data["clean_success_count"] == 2
    assert summary_data["clean_success_rate"] == 1.0
