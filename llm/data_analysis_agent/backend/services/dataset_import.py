"""Use the same CSV checks and workspace updates for uploads and startup."""

from pathlib import Path
import tempfile
from typing import Any

from backend.services.data_profiler import DataProfiler
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import Workspaces
from config import config
from pipeline_core.workspace import WorkspaceDocument


def import_csv(store: ProjectStore, source: Path, project_id: str | None = None,
               name: str | None = None, description: str = "") -> dict[str, Any]:
    """Validate a bounded snapshot before changing or creating a project."""
    filename = Path(name or source.name).name
    with source.open("rb") as stream:
        content = stream.read(config.max_upload_size_bytes + 1)
    if len(content) > config.max_upload_size_bytes:
        raise ValueError("CSV exceeds the configured input size limit")
    if not content:
        raise ValueError("CSV is empty")
    profile = DataProfiler().profile_csv(project_id or "startup", content, filename, description)
    if project_id is None:
        project_id = store.create(Path(filename).stem[:200] or "New analysis")["id"]
        profile = profile.model_copy(update={"session_id": project_id})
    with tempfile.TemporaryDirectory(dir=store.project_dir(project_id)) as directory:
        snapshot = Path(directory) / "input.csv"
        snapshot.write_bytes(content)
        store.save_dataset(project_id, snapshot, filename, profile.model_dump(), description)
    workspaces = Workspaces(store)
    workspace = workspaces.get(project_id)
    document = WorkspaceDocument.model_validate(workspace["document"])
    document.input_enabled = True
    workspaces.write(project_id, workspace["version"], document, trusted=True)
    # A replacement input invalidates an in-flight run even if its schema is unchanged.
    with store.connect() as db:
        db.execute("UPDATE workspaces SET version=version+1 WHERE project_id=?", (project_id,))
    return store.view(project_id)
