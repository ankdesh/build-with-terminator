"""Development state, manual execution, runtime updates, and revision provenance."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import shutil
import threading
from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest

from backend.services.project_jobs import ProjectEvents, ProjectJobs
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.target_manager import TargetManager
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from pipeline_core.engine import PipelineEngine, fingerprint
from pipeline_core.models import ProjectRevision, GridPosition
from pipeline_core.runtime import RuntimeApplication
from pipeline_core.runtime_http import create_runtime_app
from pipeline_core.workspace import WorkspaceDocument
from tests.test_projects import saved_project


class ReferenceRunner:
    """Run trusted test fixtures; production uses the separate ProcessRunner."""
    def __init__(self, delay=0):
        self.calls = 0
        self.active = 0
        self.maximum = 0
        self.delay = delay

    async def run(self, revision, input_path, parameters, job_dir, cancel, cache_dir=None, on_event=None):
        self.calls += 1
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            await asyncio.sleep(self.delay)
            if cancel.is_set():
                return {"success": False, "cancelled": True, "error": "Run cancelled"}
            result = PipelineEngine().execute(revision, input_path, parameters, job_dir / 'output', cache_dir, on_event)
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            self.active -= 1


def test_four_stage_types_deletion_and_undo(saved_project):
    store, project, run = saved_project
    workspaces = Workspaces(store)
    before = workspaces.get(project)
    assert {s['type'] for s in before['stages']} == {'input', 'cleaning', 'analysis', 'visualization'}
    preview = workspaces.delete(project, 'step:cleanup', before['version'], False)
    assert {s['id'] for s in preview['affected']} == {'step:cleanup', 'step:totals', 'widget:total', 'widget:table', 'widget:finding'}
    assert workspaces.get(project)['version'] == before['version']
    deleted = workspaces.delete(project, 'step:cleanup', before['version'], True)
    assert deleted['issues']
    assert deleted['document']['steps'] == []
    assert deleted['validated_run_id'] is None
    assert store.run(project, run.run_id).status == 'succeeded'
    restored = workspaces.write(project, deleted['version'], WorkspaceDocument.model_validate(deleted['document']), 'undo')
    assert restored['document'] == before['document']
    assert restored['can_redo']
    redone = workspaces.write(project, restored['version'], WorkspaceDocument.model_validate(restored['document']), 'redo')
    assert redone['document'] == deleted['document']


def test_version_conflict_and_code_changes_are_rejected(saved_project):
    store, project, _ = saved_project
    workspaces = Workspaces(store)
    before = workspaces.get(project)
    document = WorkspaceDocument.model_validate(before['document'])
    document.dashboard.title = 'New title'
    workspaces.write(project, before['version'], document)
    with pytest.raises(WorkspaceConflict):
        workspaces.write(project, before['version'], document)
    current = workspaces.get(project)
    document.steps[0].code += '\n# manual source edit'
    with pytest.raises(ValueError, match='Use chat'):
        workspaces.write(project, current['version'], document)


def test_presentation_validation_reuses_complete_artifacts(saved_project, monkeypatch):
    store, project, original = saved_project
    workspaces = Workspaces(store)
    before = workspaces.get(project)
    document = WorkspaceDocument.model_validate(before['document'])
    document.dashboard.title = 'Live title'
    document.dashboard.widgets[0].unit = 'kWh'
    document.dashboard.widgets[0].layout = GridPosition(x=0, y=0, w=3, h=5)
    original_result_file = store.run_dir(project, original.run_id) / 'output/result.json'
    original_bytes = original_result_file.read_bytes()
    workspaces.write(project, before['version'], document)
    monkeypatch.setattr(PipelineEngine, 'execute', lambda *args: pytest.fail('Presentation must not execute calculation code'))
    monkeypatch.setattr(PipelineEngine, '_load', lambda *args: pytest.fail('Layout and labels must not reload large tables'))
    assert workspaces.validate_presentation(project)
    current = workspaces.get(project)
    record = store.run(project, current['validated_run_id'])
    assert record.validation_mode == 'presentation'
    assert record.source_run_id == original.run_id
    assert record.result['outputs']['total']['value'] == 30
    assert original_result_file.read_bytes() == original_bytes
    assert 'A,10' in (store.run_dir(project, record.run_id) / 'output/records.csv').read_text()
    store.accept(project, record.run_id, True)
    assert store.get(project)['accepted_id'] == record.revision_id


def test_calculation_change_stays_pending_and_blocks_acceptance(saved_project):
    store, project, original = saved_project
    workspaces = Workspaces(store)
    before = workspaces.get(project)
    document = WorkspaceDocument.model_validate(before['document'])
    document.parameters[1].default = 2
    workspaces.write(project, before['version'], document)
    assert not workspaces.validate_presentation(project)
    assert workspaces.get(project)['calculation_pending']
    with pytest.raises(ValueError, match='workspace changed'):
        store.accept(project, original.run_id, True)


def test_legacy_revision_is_read_without_rewriting(saved_project):
    store, project, original = saved_project
    path = store.project_dir(project) / 'revisions' / f'{original.revision_id}.json'
    legacy = json.loads(path.read_text())
    legacy['schema_version'] = 1
    for widget in legacy['dashboard']['widgets']:
        for key in ('layout', 'unit', 'description'):
            widget.pop(key, None)
    path.write_text(json.dumps(legacy))
    before = path.read_bytes()
    assert store.revision(project, original.revision_id).schema_version == 1
    assert store.view(project)['workspace']['stages']
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_durable_jobs_pin_workspace_and_serialize_workers(saved_project):
    store, project, _ = saved_project
    runner = ReferenceRunner(delay=.05)
    service = ProjectService(store, runner=runner)
    targets = TargetManager(store)
    jobs = ProjectJobs(store, service, targets, ProjectEvents())
    version = Workspaces(store).get(project)['version']
    job = jobs.create(project, version, {})
    workspace = Workspaces(store).get(project)
    document = WorkspaceDocument.model_validate(workspace['document'])
    document.parameters[1].default = 3
    Workspaces(store).write(project, workspace['version'], document)
    await asyncio.gather(*list(jobs.tasks.values()))
    completed = jobs.get(project, job['id'])
    assert completed['status'] == 'succeeded'
    assert completed['workspace_version'] == version
    assert store.run(project, completed['run_id']).result['outputs']['total']['value'] == 30
    assert Workspaces(store).get(project)['validated_run_id'] is None
    assert Workspaces(store).get(project)['calculation_pending']
    revision = store.revision(project, completed['revision_id'])
    await asyncio.gather(*(service.execute(project, revision, {}, lambda e: None, threading.Event()) for _ in range(2)))
    assert runner.maximum == 1


@pytest.mark.asyncio
async def test_queued_cancellation_does_not_start_worker(saved_project):
    store, project, _ = saved_project
    runner = ReferenceRunner()
    service = ProjectService(store, runner=runner)
    jobs = ProjectJobs(store, service, TargetManager(store), ProjectEvents())
    await service.lock.acquire()
    job = jobs.create(project, Workspaces(store).get(project)['version'], {})
    await asyncio.sleep(0)
    assert jobs.cancel(project, job['id'])['cancel_requested']
    try:
        await asyncio.wait_for(asyncio.gather(*list(jobs.tasks.values()), return_exceptions=True), 1)
    finally:
        service.lock.release()
    assert jobs.get(project, job['id'])['status'] == 'cancelled'
    assert runner.calls == 0


async def apply_snapshot(application, revision, source, key):
    directory = application.root / 'builder-input'
    directory.mkdir(exist_ok=True)
    digest = fingerprint(source)
    shutil.copyfile(source, directory / f'{digest}.csv')
    await application.update({'presentation': {'title': revision.title, 'dashboard': revision.dashboard.model_dump()},
        'pending': False, 'revision': revision.model_dump(), 'input_hash': digest, 'dataset_name': 'builder.csv', 'key': key})
    if application.tasks:
        await asyncio.gather(*list(application.tasks))


@pytest.mark.asyncio
async def test_live_target_input_is_separate_and_failed_update_retains_revision(tmp_path, simple_revision, input_csv):
    application = RuntimeApplication(tmp_path / 'target', runner=ReferenceRunner(), live=True)
    await apply_snapshot(application, simple_revision, input_csv, 'first')
    assert application.state['display_run']['result']['outputs']['total']['value'] == 30
    app = create_runtime_app(application, tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost') as client:
        changed = await client.post('/api/runtime/upload', files={'csv_file': ('replacement.csv', b'zone,value\nZ,99\n')})
        assert changed.json()['state']['input_mode'] == 'replacement'
        assert changed.json()['run']['result']['outputs']['total']['value'] == 99
        assert input_csv.read_text().startswith('zone,value\nA,10')
        broken = simple_revision.model_dump()
        broken['revision_id'] = str(uuid4())
        broken['steps'][1]['code'] = broken['steps'][1]['code'].replace("df['value']", "df['new_column']")
        await apply_snapshot(application, ProjectRevision.model_validate(broken), input_csv, 'broken')
        assert application.revision.revision_id == simple_revision.revision_id
        assert application.state['display_run']['result']['outputs']['total']['value'] == 99
        assert application.state['last_error']
        assert (await client.get('/api/projects')).status_code == 404
        assert (await client.post('/api/runtime/run', json={}, headers={'Origin': 'https://untrusted.example'})).status_code == 403
    await application.close()


@pytest.mark.asyncio
async def test_runtime_presentation_update_does_not_run_again(tmp_path, simple_revision, input_csv):
    runner = ReferenceRunner()
    application = RuntimeApplication(tmp_path / 'target', runner=runner, live=True)
    await apply_snapshot(application, simple_revision, input_csv, 'first')
    changed = simple_revision.model_dump()
    changed['revision_id'] = str(uuid4())
    changed['dashboard']['title'] = 'Presentation only'
    await apply_snapshot(application, ProjectRevision.model_validate(changed), input_csv, 'second')
    assert runner.calls == 1
    assert application.revision.dashboard.title == 'Presentation only'
    assert application.state['display_run']['validation_mode'] == 'presentation'
    await application.close()


@pytest.mark.asyncio
async def test_workspace_api_conflict_and_target_auth(saved_project, monkeypatch):
    from backend.app import app
    from backend.routes import project_routes as routes
    store, project, _ = saved_project
    runner = ReferenceRunner()
    service = ProjectService(store, runner=runner)
    targets = TargetManager(store)
    events = ProjectEvents()
    for name, value in {'store': store, 'service': service, 'targets': targets, 'events': events,
                        'jobs': ProjectJobs(store, service, targets, events)}.items():
        monkeypatch.setattr(routes, name, value)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost') as client:
        workspace = (await client.get(f'/api/projects/{project}/workspace')).json()
        document = deepcopy(workspace['document'])
        document['dashboard']['title'] = 'Saved over API'
        body = {'expected_version': workspace['version'], 'document': document}
        response = await client.patch(f'/api/projects/{project}/workspace', json=body)
        assert response.status_code == 200, response.text
        assert response.json()['workspace']['validated_run_id']
        assert runner.calls == 0
        assert (await client.patch(f'/api/projects/{project}/workspace', json=body)).status_code == 409
        response = await client.post(f'/api/internal/targets/{project}/execute', json={
            'revision_id': 'unknown', 'input': '../../secret', 'run_id': str(uuid4()), 'parameters': {}})
        assert response.status_code == 403
        workspace = (await client.get(f'/api/projects/{project}/workspace')).json()
        job = (await client.post(f'/api/projects/{project}/run', json={'expected_version': workspace['version']})).json()
        await asyncio.gather(*list(routes.jobs.tasks.values()))
        assert (await client.get(f'/api/projects/{project}/jobs/{job["id"]}')).json()['status'] == 'succeeded'


@pytest.mark.asyncio
async def test_target_port_collision_and_clean_lifecycle(tmp_path, monkeypatch):
    import socket
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        port = occupied.getsockname()[1]
        monkeypatch.setenv('WPS_TARGET_PORT_START', str(port))
        monkeypatch.setenv('WPS_TARGET_PORT_END', str(port + 3))
        monkeypatch.setenv('OPENAI_API_KEY', 'private-test-key')
        store = ProjectStore(tmp_path / 'projects')
        first, second = store.create(), store.create()
        manager = TargetManager(store)
        try:
            a = await manager.start(first['id'], 'http://127.0.0.1:9')
            b = await manager.start(second['id'], 'http://127.0.0.1:9')
            assert a['port'] != b['port']
            assert a['port'] != port and b['port'] != port
            assert manager.status(first['id'])['status'] == 'running'
            process = manager.targets[first['id']].process
            if Path('/proc').exists():
                assert b'OPENAI_API_KEY=' not in Path(f'/proc/{process.pid}/environ').read_bytes()
            await manager.stop(first['id'])
            assert process.poll() is not None
            assert manager.status(first['id'])['status'] == 'stopped'
        finally:
            await manager.close()


def test_older_completion_does_not_replace_newer_display(saved_project):
    store, project, original = saved_project
    newer = original.model_copy(deep=True)
    newer.run_id = str(uuid4())
    newer.started_at = '2099-01-01T00:00:00+00:00'
    store.put_run(project, newer)
    store.put_run(project, original)
    assert store.get(project)['display_run_id'] == newer.run_id


@pytest.mark.asyncio
async def test_superseded_target_update_does_not_promote_old_result(tmp_path, simple_revision, input_csv):
    application = RuntimeApplication(tmp_path / 'target', runner=ReferenceRunner(delay=.05), live=True)
    directory = application.root / 'builder-input'
    directory.mkdir()
    digest = fingerprint(input_csv)
    shutil.copyfile(input_csv, directory / f'{digest}.csv')
    def snapshot(revision, key):
        return {'presentation': {'title': revision.title, 'dashboard': revision.dashboard.model_dump()}, 'pending': False,
            'revision': revision.model_dump(), 'input_hash': digest, 'dataset_name': 'data.csv', 'key': key}
    await application.update(snapshot(simple_revision, 'old'))
    await asyncio.sleep(.01)
    changed = simple_revision.model_dump()
    changed['revision_id'] = str(uuid4())
    changed['parameters'][1]['default'] = 2
    newest = ProjectRevision.model_validate(changed)
    await application.update(snapshot(newest, 'new'))
    await asyncio.gather(*list(application.tasks))
    assert application.revision.revision_id == newest.revision_id
    assert application.state['applied_snapshot'] == 'new'
    assert application.state['display_run']['result']['outputs']['total']['value'] == 60
    await application.close()


@pytest.mark.asyncio
async def test_target_cancellation_does_not_wait_for_execution_slot(saved_project, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.app import app
    from backend.routes import project_routes as routes
    store, project, record = saved_project
    service = ProjectService(store, runner=AsyncMock())
    target_root = tmp_path / 'target'
    target_root.mkdir()
    shutil.copyfile(store.dataset_path(project), target_root / 'input.csv')
    targets = TargetManager(store)
    monkeypatch.setattr(targets, 'authorize', lambda *args: SimpleNamespace(root=target_root))
    monkeypatch.setattr(routes, 'store', store)
    monkeypatch.setattr(routes, 'service', service)
    monkeypatch.setattr(routes, 'targets', targets)
    run_id = str(uuid4())
    await service.lock.acquire()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost') as client:
            pending = asyncio.create_task(client.post(f'/api/internal/targets/{project}/execute', json={
                'revision_id': record.revision_id, 'run_id': run_id, 'input': 'input.csv', 'parameters': {}}))
            for _ in range(50):
                if (project, run_id) in routes.target_tasks:
                    break
                await asyncio.sleep(.01)
            response = await client.post(f'/api/internal/targets/{project}/cancel/{run_id}', json={})
            assert response.json()['cancel_requested']
            result = await asyncio.wait_for(pending, 1)
            assert json.loads(result.text.strip().splitlines()[-1])['response']['cancelled']
            service.runner.run.assert_not_awaited()
    finally:
        service.lock.release()
