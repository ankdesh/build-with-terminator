"""Assemble accepted projects with a verified prebuilt Windows runtime."""

import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from uuid import uuid4
import zipfile

from backend.services.project_store import ProjectStore
from pipeline_core import RUNTIME_ABI, RUNTIME_VERSION
from pipeline_core.bundle import installed_versions, inventory, verify_inventory
from pipeline_core.engine import fingerprint


class ExportService:
    def __init__(self, store: ProjectStore, runtime_archive: Path | None = None) -> None:
        self.store = store
        configured = os.environ.get("WPS_WINDOWS_RUNTIME")
        self.runtime_archive = runtime_archive or (Path(configured) if configured else Path("runtime_cache/windows-x64.zip"))

    def export(self, project_id: str, include_data: bool = True) -> Path:
        project = self.store.get(project_id)
        if not project["accepted_id"]:
            raise ValueError("Accept a validated revision before export")
        if not self.runtime_archive.is_file():
            raise ValueError("The prebuilt Windows runtime is not available. Build it with scripts/build_windows_runtime.py on Windows, then set WPS_WINDOWS_RUNTIME to its ZIP file.")
        revision = self.store.revision(project_id, project["accepted_id"])
        with self.store.connect() as db:
            rows = db.execute("SELECT record FROM runs WHERE project_id=? AND revision_id=? ORDER BY started_at DESC", (project_id, revision.revision_id)).fetchall()
        validations = [json.loads(row["record"]) for row in rows]
        validation = next((r for r in validations if r["status"] == "succeeded" and r["parameters"] == revision.default_parameters()), None)
        if not validation:
            raise ValueError("Accepted revision has no successful validation at default parameters")
        if include_data and validation["input_hash"] != project["dataset_hash"]:
            raise ValueError("Validate and accept this revision on the current CSV before including that CSV")
        export_dir = self.store.project_dir(project_id) / "exports"
        export_dir.mkdir(exist_ok=True)
        destination = export_dir / f"analysis-{revision.revision_id[:8]}-{uuid4().hex[:8]}.zip"
        with tempfile.TemporaryDirectory(dir=export_dir) as temporary:
            root = Path(temporary) / "application"
            root.mkdir()
            self._extract_runtime(root)
            if not (root / "runtime.json").is_file():
                raise ValueError("Windows runtime archive is missing runtime.json")
            metadata = json.loads((root / "runtime.json").read_text())
            if metadata.get("runtime_abi") != RUNTIME_ABI or metadata.get("runtime_version") != RUNTIME_VERSION or metadata.get("platform") != "windows-x64":
                raise ValueError("Windows runtime version or platform is incompatible")
            if metadata.get("versions") != installed_versions():
                raise ValueError("Windows runtime dependency versions must match the builder. Install requirements-runtime.txt in both environments.")
            verify_inventory(root, metadata["files"])
            if set(inventory(root)) - {"runtime.json"} != set(metadata["files"]):
                raise ValueError("Unexpected files in Windows runtime archive")
            if metadata.get("entrypoint") != "WPSAnalysis.exe" or not (root / "WPSAnalysis.exe").is_file() or not (root / "static" / "index.html").is_file():
                raise ValueError("Windows runtime is missing its launcher or compiled dashboard")
            project_dir = root / "project"
            (project_dir / "steps").mkdir(parents=True)
            (project_dir / "revision.json").write_text(revision.model_dump_json(indent=2))
            for step in revision.steps:
                (project_dir / "steps" / f"{step.id}.py").write_text(step.code)
            if include_data:
                (root / "input").mkdir()
                shutil.copyfile(self.store.dataset_path(project_id), root / "input" / "data.csv")
            (root / "validation.json").write_text(json.dumps({
                "revision_id": revision.revision_id, "input_hash": validation["input_hash"],
                "parameters": validation["parameters"], "status": "succeeded",
                "steps": validation["result"]["steps"],
                "cleanup_impacts": validation["result"]["cleanup_impacts"],
                "runtime_versions": installed_versions(),
            }, indent=2))
            (root / "README.txt").write_text(
                "Saved Data Analysis Application\n\n"
                "Extract the complete ZIP to a writable directory on Windows 11 x64.\n"
                "Run WPSAnalysis.exe. It opens a dashboard on localhost in your browser.\n"
                "Python, Node.js, internet access and model credentials are not required.\n"
                "Use Upload CSV to replace input; Apply controls reruns saved calculations.\n"
                "A failed refresh retains the last successful dashboard.\n"
                "Use only application packages from a trusted author. Pipeline Python is executable application code.\n"
                "Application state is stored in LOCALAPPDATA/WPSAnalysis outside this package.\n"
                "To update logic, refine the source project in the builder and export a new package.\n"
            )
            manifest = {"schema_version": 1, "runtime_abi": RUNTIME_ABI, "runtime_version": RUNTIME_VERSION,
                "target": "windows-x64", "revision_id": revision.revision_id, "versions": installed_versions(),
                "dataset_name": project["dataset_name"] if include_data else None,
                "include_data": include_data, "files": inventory(root)}
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
            with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in root.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(root).as_posix())
        destination.with_suffix(".zip.sha256").write_text(f"{fingerprint(destination)}  {destination.name}\n")
        return destination

    def _extract_runtime(self, root: Path) -> None:
        total = 0
        with zipfile.ZipFile(self.runtime_archive) as archive:
            for member in archive.infolist():
                target = (root / member.filename).resolve()
                total += member.file_size
                if "\\" in member.filename or ":" in member.filename or not target.is_relative_to(root.resolve()) or stat.S_ISLNK(member.external_attr >> 16) or total > 2 * 1024 ** 3:
                    raise ValueError("Invalid runtime archive path, link, or size")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
