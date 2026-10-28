"""Versioned benchmark contracts. Missing observations remain null."""
from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any


class DifficultyTier(str, Enum):
    ISOLATED = "isolated"
    BOUNDARY = "boundary"
    INTERACTION = "interaction"
    NEGATIVE = "negative"


class BenchmarkVerdict(str, Enum):
    CLEAN_SUCCESS = "clean_success"
    PARTIAL_SUCCESS = "partial_success"
    REGRESSION = "regression"
    FAILED_UNCHANGED = "failed_unchanged"
    EXECUTION_ERROR = "execution_error"
    INVALID_PATCH = "invalid_patch"
    MODEL_ERROR = "model_error"
    CHECKER_ERROR = "checker_error"
    BLOCKED = "blocked"
    ORACLE_MISMATCH = "oracle_mismatch"
    CLEAN_UNCHANGED = "clean_unchanged"
    UNNECESSARY_EDIT = "unnecessary_edit"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class BenchmarkCaseSpec:
    case_id: str
    rule_id: str
    tier: DifficultyTier
    gds_rel_path: str
    sha256: str
    expected_initial_violations: int
    expected_rules: list[str]
    description: str
    tags: list[str] = field(default_factory=list)
    acceptance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data["tier"] = self.tier.value
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(**{**{k: v for k, v in data.items() if k in cls.__dataclass_fields__},
                      "tier": DifficultyTier(data["tier"])})


@dataclass(frozen=True)
class BenchmarkManifest:
    benchmark_version: str
    created_at: str
    description: str
    rule_families: list[str]
    cases: list[BenchmarkCaseSpec]
    acceptance: dict[str, Any] = field(default_factory=dict)

    @property
    def case_count(self):
        return len(self.cases)

    def to_dict(self):
        return {"benchmark_version": self.benchmark_version, "created_at": self.created_at,
                "description": self.description, "rule_families": self.rule_families,
                "case_count": self.case_count, "cases": [c.to_dict() for c in self.cases],
                "acceptance": self.acceptance}

    @classmethod
    def from_dict(cls, data):
        cases = [BenchmarkCaseSpec.from_dict(c) for c in data["cases"]]
        ids = [c.case_id for c in cases]
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", case_id) for case_id in ids):
            raise ValueError("Invalid case ID")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate case IDs")
        return cls(data["benchmark_version"], data["created_at"], data["description"],
                   data["rule_families"], cases, data.get("acceptance", {}))


@dataclass
class EvaluationResult:
    case_id: str
    rule_id: str
    tier: DifficultyTier
    mode: str
    initial_violations: dict[str, int] | None
    final_violations: dict[str, int] | None
    initial_total: int | None
    final_total: int | None
    verdict: BenchmarkVerdict
    area_added_um2: float | None
    area_removed_um2: float | None
    execution_time_s: float
    error_message: str | None = None
    run_dir: str | None = None
    schema_version: int = 2
    actual_mode: str | None = None
    pipeline_verdict: str | None = None
    failure_stage: str | None = None
    validation: dict | None = None
    marker_comparison: dict | None = None
    initially_clean: bool = False
    duplicate_group: str | None = None
    validation_level: str = "not_run"

    def to_dict(self):
        data = asdict(self)
        data.update(tier=self.tier.value, verdict=self.verdict.value)
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(**{**{k: v for k, v in data.items() if k in cls.__dataclass_fields__},
                      "tier": DifficultyTier(data["tier"]), "verdict": BenchmarkVerdict(data["verdict"])})


@dataclass
class BenchmarkSummary:
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
    tier_breakdown: dict
    rule_breakdown: dict
    results: list[EvaluationResult] = field(default_factory=list)
    dirty_cases: int = 0
    clean_controls: int = 0
    verdict_counts: dict = field(default_factory=dict)
    duplicate_groups: dict = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data.update(schema_version=2, validation_level="geometry_only",
                    results=[r.to_dict() for r in self.results])
        return data
