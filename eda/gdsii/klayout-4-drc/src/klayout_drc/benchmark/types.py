"""Data models and type definitions for the KLayout DRC Benchmark Suite.

Defines schemas for benchmark case specifications, difficulty tiers,
cryptographic verification, evaluation outcomes, and summary reports.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class DifficultyTier(str, Enum):
    """Classification of benchmark case complexity."""
    ISOLATED = "isolated"
    BOUNDARY = "boundary"
    INTERACTION = "interaction"
    NEGATIVE = "negative"


class BenchmarkVerdict(str, Enum):
    """Categorical evaluation verdict for a repair candidate."""
    CLEAN_SUCCESS = "clean_success"          # 0 violations remaining, 0 regressions
    PARTIAL_SUCCESS = "partial_success"      # violations strictly reduced, 0 regressions
    REGRESSION = "regression"                # new rule violations introduced or total violations increased
    FAILED_UNCHANGED = "failed_unchanged"    # violation count unchanged
    EXECUTION_ERROR = "execution_error"      # patch syntax error, crash, timeout, or missing output


@dataclass(frozen=True)
class BenchmarkCaseSpec:
    """Specification of a single benchmark test case."""
    case_id: str
    rule_id: str
    tier: DifficultyTier
    gds_rel_path: str
    sha256: str
    expected_initial_violations: int
    expected_rules: List[str]
    description: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert specification to a JSON-serializable dictionary."""
        return {
            "case_id": self.case_id,
            "rule_id": self.rule_id,
            "tier": self.tier.value,
            "gds_rel_path": self.gds_rel_path,
            "sha256": self.sha256,
            "expected_initial_violations": self.expected_initial_violations,
            "expected_rules": list(self.expected_rules),
            "description": self.description,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkCaseSpec":
        """Reconstruct specification from dictionary representation."""
        return cls(
            case_id=data["case_id"],
            rule_id=data["rule_id"],
            tier=DifficultyTier(data["tier"]),
            gds_rel_path=data["gds_rel_path"],
            sha256=data["sha256"],
            expected_initial_violations=int(data["expected_initial_violations"]),
            expected_rules=list(data.get("expected_rules", [])),
            description=data.get("description", ""),
            tags=list(data.get("tags", [])),
        )


@dataclass(frozen=True)
class BenchmarkManifest:
    """Complete manifest indexing the benchmark suite."""
    benchmark_version: str
    created_at: str
    description: str
    rule_families: List[str]
    cases: List[BenchmarkCaseSpec]

    @property
    def case_count(self) -> int:
        """Total number of benchmark cases in the manifest."""
        return len(self.cases)

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to a JSON-serializable dictionary."""
        return {
            "benchmark_version": self.benchmark_version,
            "created_at": self.created_at,
            "description": self.description,
            "rule_families": list(self.rule_families),
            "case_count": self.case_count,
            "cases": [case.to_dict() for case in self.cases],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkManifest":
        """Reconstruct manifest from dictionary representation."""
        cases = [BenchmarkCaseSpec.from_dict(c) for c in data.get("cases", [])]
        return cls(
            benchmark_version=data.get("benchmark_version", "1.0.0"),
            created_at=data.get("created_at", ""),
            description=data.get("description", ""),
            rule_families=list(data.get("rule_families", [])),
            cases=cases,
        )


@dataclass
class EvaluationResult:
    """Outcome of running a single benchmark case evaluation."""
    case_id: str
    rule_id: str
    tier: DifficultyTier
    mode: str
    initial_violations: Dict[str, int]
    final_violations: Dict[str, int]
    initial_total: int
    final_total: int
    verdict: BenchmarkVerdict
    area_added_um2: float
    area_removed_um2: float
    execution_time_s: float
    error_message: Optional[str] = None
    run_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "case_id": self.case_id,
            "rule_id": self.rule_id,
            "tier": self.tier.value,
            "mode": self.mode,
            "initial_violations": dict(self.initial_violations),
            "final_violations": dict(self.final_violations),
            "initial_total": self.initial_total,
            "final_total": self.final_total,
            "verdict": self.verdict.value,
            "area_added_um2": self.area_added_um2,
            "area_removed_um2": self.area_removed_um2,
            "execution_time_s": self.execution_time_s,
            "error_message": self.error_message,
            "run_dir": self.run_dir,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationResult":
        """Reconstruct evaluation result from dictionary representation."""
        return cls(
            case_id=data["case_id"],
            rule_id=data["rule_id"],
            tier=DifficultyTier(data["tier"]),
            mode=data["mode"],
            initial_violations=dict(data.get("initial_violations", {})),
            final_violations=dict(data.get("final_violations", {})),
            initial_total=int(data.get("initial_total", 0)),
            final_total=int(data.get("final_total", 0)),
            verdict=BenchmarkVerdict(data["verdict"]),
            area_added_um2=float(data.get("area_added_um2", 0.0)),
            area_removed_um2=float(data.get("area_removed_um2", 0.0)),
            execution_time_s=float(data.get("execution_time_s", 0.0)),
            error_message=data.get("error_message"),
            run_dir=data.get("run_dir"),
        )


@dataclass
class BenchmarkSummary:
    """Aggregated summary of benchmark evaluation across multiple cases."""
    benchmark_version: str
    mode: str
    total_cases: int
    clean_success_count: int
    partial_success_count: int
    regression_count: int
    failed_unchanged_count: int
    execution_error_count: int
    clean_success_rate: float
    total_runtime_s: float
    tier_breakdown: Dict[str, Dict[str, int]]
    rule_breakdown: Dict[str, Dict[str, int]]
    results: List[EvaluationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation."""
        return {
            "benchmark_version": self.benchmark_version,
            "mode": self.mode,
            "total_cases": self.total_cases,
            "clean_success_count": self.clean_success_count,
            "partial_success_count": self.partial_success_count,
            "regression_count": self.regression_count,
            "failed_unchanged_count": self.failed_unchanged_count,
            "execution_error_count": self.execution_error_count,
            "clean_success_rate": round(self.clean_success_rate, 4),
            "total_runtime_s": round(self.total_runtime_s, 2),
            "tier_breakdown": self.tier_breakdown,
            "rule_breakdown": self.rule_breakdown,
            "results": [r.to_dict() for r in self.results],
        }
