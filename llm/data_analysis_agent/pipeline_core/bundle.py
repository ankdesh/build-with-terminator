"""Version checks and file integrity for portable application packages."""

import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

from pipeline_core import RUNTIME_ABI, RUNTIME_VERSION
from pipeline_core.engine import fingerprint
from pipeline_core.models import ProjectRevision

PACKAGES = ("pandas", "numpy", "scipy", "statsmodels", "patsy", "python-dateutil", "tzdata", "pytz",
    "pydantic", "pydantic-core", "fastapi", "starlette", "uvicorn", "python-multipart")


def installed_versions() -> dict[str, str]:
    return {"python": f"{sys.version_info.major}.{sys.version_info.minor}",
        **{name: importlib.metadata.version(name) for name in PACKAGES}}


def inventory(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): fingerprint(p) for p in sorted(root.rglob("*"))
            if p.is_file() and p.name != "manifest.json"}


def verify_inventory(root: Path, files: dict[str, str]) -> None:
    for name, digest in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or invalid bundle file: {name}")
        if fingerprint(path) != digest:
            raise ValueError(f"Bundle integrity check failed: {name}")


def load_bundle(root: Path) -> tuple[ProjectRevision, dict[str, Any]]:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != 1 or manifest.get("runtime_abi") != RUNTIME_ABI or manifest.get("runtime_version") != RUNTIME_VERSION:
        raise ValueError("Unsupported bundle or runtime version")
    verify_inventory(root, manifest["files"])
    if set(inventory(root)) != set(manifest["files"]):
        raise ValueError("Bundle contains unexpected files")
    if manifest["versions"] != installed_versions():
        raise ValueError("The bundle requires different runtime dependency versions")
    revision = ProjectRevision.model_validate_json((root / "project" / "revision.json").read_text())
    if revision.revision_id != manifest["revision_id"]:
        raise ValueError("Bundle revision identity mismatch")
    for step in revision.steps:
        if (root / "project" / "steps" / f"{step.id}.py").read_text() != step.code:
            raise ValueError("Pipeline source and revision disagree")
    return revision, manifest
