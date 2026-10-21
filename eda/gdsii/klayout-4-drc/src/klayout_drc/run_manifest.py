"""Run specification and manifest manager for single-shot DRC evaluation.

Provides immutable input snapshotting, SHA-256 file hashing, environment capture,
and isolated run directory creation under reports/runs/<run_id>/.
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any

from .config import (
    DEFAULT_RUNS_DIR,
    DRCConfigurationError,
)


@dataclass(frozen=True)
class RunSpec:
    """Input specifications for an evaluation run."""

    case_name: str
    input_gds: Path
    drc_script: Path
    profile_name: str = "legacy_mini"
    candidate_mode: str = "heuristic"
    candidate_script: Path | None = None
    top_cell: str | None = None
    run_id: str | None = None
    output_root: Path = DEFAULT_RUNS_DIR

    def validate(self) -> None:
        """Validate input paths and options."""
        if not self.input_gds.exists():
            raise DRCConfigurationError(f"Input GDS does not exist: {self.input_gds}")
        if not self.drc_script.exists():
            raise DRCConfigurationError(f"DRC script does not exist: {self.drc_script}")
        if self.candidate_mode == "script_file" and (
            not self.candidate_script or not self.candidate_script.exists()
        ):
            raise DRCConfigurationError(
                f"Candidate script file not provided or does not exist: {self.candidate_script}"
            )


@dataclass(frozen=True)
class RunPaths:
    """Canonical file paths within an isolated run bundle directory."""

    run_dir: Path
    input_gds: Path
    before_lyrdb: Path
    candidate_script: Path
    candidate_stdout: Path
    candidate_stderr: Path
    patched_gds: Path
    after_lyrdb: Path
    layout_diff_json: Path
    results_json: Path
    report_md: Path


class RunManifestManager:
    """Creates isolated run directories, snapshots inputs, and writes manifest metadata."""

    def __init__(self, spec: RunSpec) -> None:
        """Initialize with validated RunSpec."""
        spec.validate()
        self.spec = spec
        self.run_id = self._generate_run_id()
        self.run_dir = (self.spec.output_root / self.run_id).resolve()
        self.paths = self._build_paths()

    def _generate_run_id(self) -> str:
        """Generate a run ID matching the agreed pattern: <case_name>_<timestamp>_<short_id>."""
        if self.spec.run_id:
            return self.spec.run_id
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:6]
        safe_case = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.spec.case_name)
        return f"{safe_case}_{timestamp}_{short_id}"

    def _build_paths(self) -> RunPaths:
        """Construct standard canonical paths inside the run directory."""
        return RunPaths(
            run_dir=self.run_dir,
            input_gds=self.run_dir / "input.gds",
            before_lyrdb=self.run_dir / "before.lyrdb",
            candidate_script=self.run_dir / "candidate_fix.py",
            candidate_stdout=self.run_dir / "candidate_stdout.log",
            candidate_stderr=self.run_dir / "candidate_stderr.log",
            patched_gds=self.run_dir / "patched.gds",
            after_lyrdb=self.run_dir / "after.lyrdb",
            layout_diff_json=self.run_dir / "layout_diff.json",
            results_json=self.run_dir / "results.json",
            report_md=self.run_dir / "report.md",
        )

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute the SHA-256 hexadecimal hash of a file."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def _get_git_commit(self) -> str:
        """Retrieve current git HEAD commit SHA if inside a repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def setup_run(self) -> RunPaths:
        """Create the run directory, snapshot immutable inputs, and write initial manifest."""
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot immutable input GDS
        shutil.copy2(self.spec.input_gds, self.paths.input_gds)

        input_gds_hash = self.compute_sha256(self.paths.input_gds)
        drc_script_hash = self.compute_sha256(self.spec.drc_script)

        manifest_data: dict[str, Any] = {
            "run_id": self.run_id,
            "case_name": self.spec.case_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": {
                "python_version": sys.version,
                "git_commit": self._get_git_commit(),
            },
            "spec": {
                "original_input_gds": str(self.spec.input_gds.resolve()),
                "drc_script": str(self.spec.drc_script.resolve()),
                "profile_name": self.spec.profile_name,
                "candidate_mode": self.spec.candidate_mode,
                "top_cell": self.spec.top_cell,
            },
            "hashes": {
                "input_gds_sha256": input_gds_hash,
                "drc_script_sha256": drc_script_hash,
            },
        }

        manifest_file = self.run_dir / "run_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        return self.paths

    def update_manifest(self, updates: dict[str, Any]) -> None:
        """Update the existing run_manifest.json with new metadata."""
        manifest_file = self.run_dir / "run_manifest.json"
        if manifest_file.exists():
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        else:
            data = {}
        data.update(updates)
        manifest_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
