"""Project persistence, authoring repair, acceptance, and export gates."""

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest

from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.export_service import ExportService
from pipeline_core import RUNTIME_ABI, RUNTIME_VERSION
from pipeline_core.bundle import installed_versions, inventory, load_bundle
from pipeline_core.engine import PipelineEngine, fingerprint
from pipeline_core.models import ProjectRevision, RunRecord, now


def successful_run(store, project_id, revision, input_csv, parameters=None):
    record = RunRecord(revision_id=revision.revision_id, dataset_name="source.csv", input_hash=fingerprint(input_csv), parameters=parameters or revision.default_parameters())
    store.put_run(project_id, record)
    record.result = PipelineEngine().execute(revision, input_csv, record.parameters, store.run_dir(project_id, record.run_id) / "output")
    record.status, record.finished_at = "succeeded", now()
    store.put_run(project_id, record)
    return record


@pytest.fixture
def saved_project(tmp_path, input_csv, simple_revision):
    store = ProjectStore(tmp_path / "projects")
    project = store.create()
    store.save_dataset(project["id"], input_csv, "source.csv", {}, "")
    store.save_revision(project["id"], simple_revision)
    record = successful_run(store, project["id"], simple_revision, input_csv)
    return store, project["id"], record


def test_acceptance_is_explicit_and_immutable(saved_project, simple_revision):
    store, project_id, run = saved_project
    with pytest.raises(ValueError, match="Confirm"): store.accept(project_id, run.run_id, False)
    store.accept(project_id, run.run_id, True)
    with pytest.raises(ValueError, match="immutable"): store.save_revision(project_id, simple_revision)
    restarted = ProjectStore(store.root)
    assert restarted.get(project_id)["accepted_id"] == simple_revision.revision_id


def test_failure_does_not_replace_accepted_or_display(saved_project, simple_revision):
    store, project_id, good = saved_project
    store.accept(project_id, good.run_id, True)
    payload = simple_revision.model_dump(); payload.update(revision_id=str(uuid4()), parent_revision_id=simple_revision.revision_id)
    draft = ProjectRevision.model_validate(payload)
    store.save_revision(project_id, draft)
    failed = RunRecord(revision_id=draft.revision_id, dataset_name="bad.csv", input_hash="bad", parameters=draft.default_parameters(), status="failed", error="Bad input")
    store.put_run(project_id, failed)
    assert store.get(project_id)["display_run_id"] == good.run_id
    assert store.get(project_id)["accepted_id"] == simple_revision.revision_id
    store.rollback(project_id, simple_revision.revision_id)
    assert store.get(project_id)["draft_id"] == simple_revision.revision_id
    assert store.view(project_id)["display_revision"]["revision_id"] == good.revision_id


def test_changed_input_invalidates_acceptance(saved_project, tmp_path):
    store, project_id, run = saved_project
    replacement = tmp_path / "replacement.csv"; replacement.write_text("zone,value\nA,99\n")
    store.save_dataset(project_id, replacement, "replacement.csv", {}, "")
    with pytest.raises(ValueError, match="input or draft changed"): store.accept(project_id, run.run_id, True)


def fake_runtime(tmp_path):
    root = tmp_path / "runtime"; (root / "static").mkdir(parents=True)
    (root / "WPSAnalysis.exe").write_bytes(b"release-test-fixture")
    (root / "static/index.html").write_text("<html>Offline dashboard</html>")
    metadata = {"runtime_abi": RUNTIME_ABI, "runtime_version": RUNTIME_VERSION, "platform": "windows-x64", "entrypoint": "WPSAnalysis.exe", "versions": installed_versions(), "files": inventory(root)}
    (root / "runtime.json").write_text(json.dumps(metadata))
    path = tmp_path / "runtime.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for file in root.rglob("*"):
            if file.is_file(): archive.write(file, file.relative_to(root))
    return path


def test_export_gates_and_integrity(saved_project, tmp_path, simple_revision):
    store, project_id, run = saved_project
    with pytest.raises(ValueError, match="Accept"): ExportService(store).export(project_id)
    store.accept(project_id, run.run_id, True)
    with pytest.raises(ValueError, match="not available"): ExportService(store, tmp_path / "missing.zip").export(project_id)
    archive = ExportService(store, fake_runtime(tmp_path)).export(project_id)
    package = tmp_path / "application"
    with zipfile.ZipFile(archive) as stream: stream.extractall(package)
    revision, manifest = load_bundle(package)
    assert revision.revision_id == simple_revision.revision_id
    assert manifest["include_data"]
    assert (package / "input/data.csv").is_file()
    (package / "project/steps/cleanup.py").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"): load_bundle(package)


def test_export_rejects_archive_traversal(saved_project, tmp_path):
    store, project_id, run = saved_project; store.accept(project_id, run.run_id, True)
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as stream: stream.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="Invalid runtime archive"): ExportService(store, archive).export(project_id)
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.asyncio
async def test_agent_saves_without_running_and_repairs_only_schema_errors(saved_project, simple_revision):
    from backend.services.project_agent import ProposalValidationError
    store, project_id, original_run = saved_project
    payload = simple_revision.model_dump(); payload["revision_id"] = str(uuid4())
    proposal = ProjectRevision.model_validate(payload)
    agent = AsyncMock()
    agent.propose.side_effect = [ProposalValidationError("Invalid widget binding", payload), proposal]
    runner = AsyncMock()
    service = ProjectService(store, agent=agent, runner=runner)
    import threading
    events = []
    await service.build(project_id, "Refine the dashboard", events.append, threading.Event())
    assert agent.propose.await_count == 2
    runner.run.assert_not_awaited()
    assert store.view(project_id)["display_run"]["run_id"] == original_run.run_id
    assert store.get(project_id)["draft_id"] == proposal.revision_id


@pytest.mark.asyncio
async def test_malformed_model_patch_is_repaired_without_losing_working_revision(saved_project, simple_revision):
    store, project_id, original_run = saved_project
    payload = simple_revision.model_dump()
    payload["revision_id"] = str(uuid4())
    payload["dashboard"]["title"] = "Repaired title"
    proposal = ProjectRevision.model_validate(payload)
    agent = AsyncMock()
    agent.propose.side_effect = [json.JSONDecodeError("Invalid patch value_json", "", 0), proposal]
    runner = AsyncMock()
    import threading
    await ProjectService(store, agent=agent, runner=runner).build(project_id, "Rename dashboard", lambda _: None, threading.Event())
    assert agent.propose.await_count == 2
    second = agent.propose.await_args_list[1].args
    assert "Invalid model proposal" in second[4]
    assert second[5] is None  # A malformed patch is not a complete revision.
    runner.run.assert_not_awaited()
    view = store.view(project_id)
    assert view["workspace"]["document"]["dashboard"]["title"] == "Repaired title"
    assert view["display_run"]["validation_mode"] == "presentation"
    assert view["display_run"]["source_run_id"] == original_run.run_id

@pytest.mark.asyncio
async def test_workspace_conflict_does_not_retry_model(saved_project, simple_revision, monkeypatch):
    from backend.services.workspace_service import Workspaces, WorkspaceConflict
    store, project_id, _ = saved_project
    agent = AsyncMock()
    agent.propose.return_value = simple_revision
    def conflict(*args, **kwargs):
        raise WorkspaceConflict("Concurrent workspace edit")
    monkeypatch.setattr(Workspaces, "write", conflict)
    import threading
    with pytest.raises(WorkspaceConflict):
        await ProjectService(store, agent=agent).build(project_id, "Rename dashboard", lambda _: None, threading.Event())
    agent.propose.assert_awaited_once()

@pytest.mark.asyncio
async def test_project_api_pipeline_and_full_csv(saved_project, monkeypatch):
    from backend.app import app
    from backend.routes import project_routes
    store, project_id, record = saved_project
    monkeypatch.setattr(project_routes, "store", store)
    monkeypatch.setattr(project_routes, "service", ProjectService(store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.get(f"/api/projects/{project_id}")).status_code == 200
        blocked = await client.post(f"/api/projects/{project_id}/accept", json={"run_id": record.run_id})
        assert blocked.status_code == 422
        accepted = await client.post(f"/api/projects/{project_id}/accept", json={"run_id": record.run_id, "cleanup_confirmed": True})
        assert accepted.status_code == 200
        table = await client.get(f"/api/projects/{project_id}/runs/{record.run_id}/tables/records")
        assert "A,10" in table.text and "B,20" in table.text
        assert (await client.post(f"/api/projects/{project_id}/accept", json={}, headers={"Origin": "https://untrusted.example"})).status_code == 403
        assert (await client.post('/api/sessions/legacy/chat', json={"query": "unsafe"})).status_code in (404, 405)
        assert (await client.get('/health', headers={'Host': 'untrusted.example'})).status_code == 400


def test_export_pins_the_accepted_input_after_builder_replacement(saved_project, tmp_path):
    store, project_id, record = saved_project
    store.accept(project_id, record.run_id, True)
    replacement = tmp_path / "new.csv"
    replacement.write_text("zone,value\nZ,99\n")
    store.save_dataset(project_id, replacement, "new.csv", {}, "")
    archive = ExportService(store, fake_runtime(tmp_path)).export(project_id)
    with zipfile.ZipFile(archive) as package:
        assert package.read("input/data.csv").startswith(b"zone,value\nA,10")
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["dataset_name"] == record.dataset_name
