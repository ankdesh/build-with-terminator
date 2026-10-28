"""Benchmark manifest manager for reading, writing, filtering, and verifying test cases.

Provides cryptographic integrity checks, metadata indexing, and query filtering
for the ASAP7 synthetic benchmark suite.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from klayout_drc.benchmark.types import (
    BenchmarkCaseSpec,
    BenchmarkManifest,
    DifficultyTier,
)
from klayout_drc.config import DRCConfigurationError


class BenchmarkManifestManager:
    """Manages serialization, filtering, and integrity verification of the benchmark manifest."""

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute the hex-encoded SHA-256 hash of a file."""
        if not file_path.exists():
            raise DRCConfigurationError(f"Target file for SHA-256 hashing does not exist: {file_path}")
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, manifest_path: Path) -> BenchmarkManifest:
        """Load and parse a benchmark manifest from a JSON file.

        Args:
            manifest_path: Path to the manifest.json file.

        Returns:
            Strongly typed BenchmarkManifest.

        Raises:
            DRCConfigurationError: If the manifest does not exist or JSON parsing fails.
        """
        if not manifest_path.exists():
            raise DRCConfigurationError(f"Benchmark manifest not found at: {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return BenchmarkManifest.from_dict(raw_data)
        except json.JSONDecodeError as exc:
            raise DRCConfigurationError(f"Failed to parse benchmark manifest JSON from {manifest_path}: {exc}") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise DRCConfigurationError(f"Missing required field in benchmark manifest {manifest_path}: {exc}") from exc

    @classmethod
    def save(cls, manifest: BenchmarkManifest, manifest_path: Path) -> None:
        """Save a benchmark manifest to a JSON file with deterministic formatting.

        Args:
            manifest: The BenchmarkManifest instance to save.
            manifest_path: Destination path.
        """
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def filter_cases(
        cls,
        manifest: BenchmarkManifest,
        rules: Optional[List[str]] = None,
        tiers: Optional[List[DifficultyTier]] = None,
        limit: Optional[int] = None,
    ) -> List[BenchmarkCaseSpec]:
        """Filter benchmark cases based on rule families, difficulty tiers, and count limit.

        Args:
            manifest: Loaded benchmark manifest.
            rules: Optional list of rule IDs to include (e.g. ['M1.W.1', 'V1.W.1']).
            tiers: Optional list of difficulty tiers to include.
            limit: Optional maximum number of cases to return.

        Returns:
            Filtered list of BenchmarkCaseSpec.
        """
        filtered = manifest.cases

        if rules is not None and len(rules) > 0:
            rule_set = {r.strip() for r in rules}
            filtered = [c for c in filtered if c.rule_id in rule_set]

        if tiers is not None and len(tiers) > 0:
            tier_set = set(tiers)
            filtered = [c for c in filtered if c.tier in tier_set]

        if limit is not None and limit < 0:
            raise DRCConfigurationError("Limit must be nonnegative")
        if limit is not None:
            filtered = filtered[:limit]

        return filtered

    @classmethod
    def verify_integrity(
        cls,
        manifest: BenchmarkManifest,
        base_dir: Path,
    ) -> Dict[str, bool]:
        """Verify the presence and cryptographic SHA-256 hash of each case GDS file.

        Args:
            manifest: Loaded benchmark manifest.
            base_dir: Base directory against which relative GDS paths are resolved.

        Returns:
            Mapping of case_id -> boolean indicating whether the file matches expected hash.
        """
        verification_results: Dict[str, bool] = {}

        for case in manifest.cases:
            gds_path = base_dir / case.gds_rel_path
            if not gds_path.exists():
                verification_results[case.case_id] = False
                continue

            current_hash = cls.compute_sha256(gds_path)
            verification_results[case.case_id] = (current_hash == case.sha256)

        return verification_results
