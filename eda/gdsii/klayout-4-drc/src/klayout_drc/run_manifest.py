"""Run specification and manifest manager for single-shot DRC evaluation.

Provides immutable input snapshotting, SHA-256 file hashing, environment capture,
and isolated run directory creation under reports/runs/<run_id>/.
"""

from dataclasses import dataclass, field
import hashlib
import json
import re
import klayout.db as db
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

    expected_counts: dict[str, int] | None = None
    expected_markers: list | None = None
    preservation: dict = field(default_factory=dict)
    edit_policy: dict | None = None

    def validate(self) -> None:
        """Validate input paths and options."""
        if self.run_id and not re.fullmatch(r"[A-Za-z0-9_-]+", self.run_id):
            raise DRCConfigurationError("Run ID must be a single safe name")
        if self.candidate_mode not in ("agent", "heuristic", "script_file"):
            raise DRCConfigurationError("Unknown candidate mode")
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
    run_manifest_json: Path


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
            run_manifest_json=self.run_dir / "run_manifest.json",
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
        self.run_dir.mkdir(parents=True, exist_ok=False)

        # Snapshot immutable input GDS
        shutil.copy2(self.spec.input_gds, self.paths.input_gds)

        deck_snapshot = self.run_dir / ("deck" + self.spec.drc_script.suffix)
        shutil.copy2(self.spec.drc_script, deck_snapshot)

        input_gds_hash = self.compute_sha256(self.paths.input_gds)
        drc_script_hash = self.compute_sha256(self.spec.drc_script)

        model_config = None
        if self.spec.candidate_mode == 'agent':
            script = Path(__file__).resolve().parents[2]/'harness/scripts/model-config.mjs'
            model_config = json.loads(subprocess.check_output(['node', str(script)], text=True, timeout=10))

        manifest_data: dict[str, Any] = {
            "run_id": self.run_id,
            "case_name": self.spec.case_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": {
                "python_version": sys.version,
                "klayout_version": db.__version__,
                "node_version": self._command_version(["node", "--version"]),
                "checker_cli_version": self._command_version(["klayout", "-b", "-v"]),
                "harness_packages": self._harness_versions(),
                "model_requested": model_config['model'] if model_config else None,
                "model_config": model_config,
                "git_commit": self._get_git_commit(),
            },
            "spec": {
                "original_input_gds": str(self.spec.input_gds.resolve()),
                "drc_script": str(self.spec.drc_script.resolve()),
                "profile_name": self.spec.profile_name,
                "candidate_mode": self.spec.candidate_mode,
                "top_cell": self.spec.top_cell,
                "edit_policy": self.spec.edit_policy,
            },
            "schema_version": 2,
            "deck_snapshot": str(deck_snapshot),
            "source_hashes": self._source_hashes(),
            "limits": {"wall_seconds": 120, "cpu_seconds": 120, "memory_bytes": 2147483648, "processes": 64, "output_bytes": 67108864, "log_bytes": 1048576},
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

    @staticmethod
    def _command_version(command):
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return None

    def _source_hashes(self):
        root = Path(__file__).resolve().parents[2]
        paths = list((root / "src").rglob("*.py"))
        for directory, pattern in (("harness/lib", "*.js"), ("harness/src", "*.ts"), ("harness/scripts", "*.mjs"),
                                   ("harness/profile", "*"), ("knowledge", "*.md")):
            paths.extend(p for p in (root / directory).rglob(pattern) if p.is_file())
        paths.extend(root / p for p in ("pyproject.toml", "uv.lock", "harness/package.json", "harness/tsconfig.json") if (root/p).exists())
        return {str(p.relative_to(root)): self.compute_sha256(p) for p in sorted(paths)}

    @staticmethod
    def _harness_versions():
        modules = Path(__file__).resolve().parents[2]/"harness/node_modules/@deepseek-ai"
        versions = {}
        if modules.exists():
            for package in sorted(modules.iterdir()):
                path = package/"package.json"
                if path.is_file():
                    data = json.loads(path.read_text())
                    versions[data["name"]] = data.get("version")
        return versions
