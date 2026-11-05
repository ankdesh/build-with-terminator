"""Empty stage contexts and partial execution do not bypass release validation."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.chat_store import context_for, review_changes
from backend.services.project_jobs import ProjectEvents, ProjectJobs
from backend.services.project_service import ProjectService
from backend.services.workspace_service import Workspaces
from pipeline_core.engine import PipelineEngine
from pipeline_core.partial import PartialRevision, execution_plan
from pipeline_core.workspace import WorkspaceDocument
from tests.test_projects import saved_project


def test_empty_cleaning_context_allows_only_connected_edits(simple_revision):
    document = WorkspaceDocument.from_revision(simple_revision)
    document.steps = []
    document.dashboard.widgets = []
    before = document.model_dump()
    assert context_for(before, 'category:cleaning')['label'].startswith('Data cleaning')
    document.steps = [simple_revision.steps[0]]
    review = review_changes(before, document.model_dump(), 'category:cleaning', {})
    assert review['changes'][0]['stage_id'] == 'step:cleanup'
    document.title = 'Unrelated rename'
    with pytest.raises(ValueError, match='Unrelated'):
        review_changes(before, document.model_dump(), 'category:cleaning', {})
    with pytest.raises(ValueError, match='no longer exists'):
        context_for(before, 'category:unknown')


def test_partial_plan_runs_cleanup_and_blocks_missing_dependency(simple_revision, tmp_path):
    document = WorkspaceDocument.from_revision(simple_revision)
    document.steps[1].inputs = ['missing']
    revision, blocked = execution_plan(document)
    assert isinstance(revision, PartialRevision)
    assert [s.id for s in revision.steps] == ['cleanup']
    assert blocked[0]['step_id'] == 'totals'
    source = tmp_path/'input.csv'
    source.write_text('zone,value\nA,10\nA,20\n')
    first = PipelineEngine().execute(revision, source, {}, tmp_path/'one')
    second = PipelineEngine().execute(revision, source, {}, tmp_path/'two', tmp_path/'one')
    assert first['steps'][-1]['status'] == 'succeeded'
    assert second['steps'][-1]['cached']
    with pytest.raises(ValueError):
        document.compile()


def test_analysis_only_and_input_only_snapshots(simple_revision):
    document = WorkspaceDocument.from_revision(simple_revision)
    document.steps = [document.steps[1]]
    document.steps[0].inputs = ['data']
    document.parameters = []
    revision, blocked = execution_plan(document)
    assert len(revision.steps) == 1 and not blocked
    document.steps = []
    revision, blocked = execution_plan(document)
    assert not revision.steps and not revision.dashboard.widgets


@pytest.mark.asyncio
async def test_partial_worker_and_job_reuse_without_dashboard_promotion(saved_project):
    store, pid, full_run = saved_project
    workspace = Workspaces(store)
    current = workspace.get(pid)
    document = WorkspaceDocument.model_validate(current['document'])
    document.steps = document.steps[:1]
    document.dashboard.widgets = []
    workspace.write(pid, current['version'], document, trusted=True)
    targets = SimpleNamespace(sync=AsyncMock())
    jobs = ProjectJobs(store, ProjectService(store), targets, ProjectEvents())
    try:
        job = jobs.create(pid, workspace.get(pid)['version'], {})
        await jobs.tasks[job['id']]
        completed = jobs.get(pid, job['id'])
        assert completed['status'] == 'succeeded', completed
        assert completed['partial']
        run = store.run(pid, completed['run_id'])
        assert run.validation_mode == 'partial'
        assert store.get(pid)['display_run_id'] == full_run.run_id
        assert store.view(pid)['partial_run']['run_id'] == run.run_id
        targets.sync.assert_not_called()
        with pytest.raises(ValueError, match='Partial runs'):
            store.accept(pid, run.run_id, True)
        job2 = jobs.create(pid, workspace.get(pid)['version'], {})
        await jobs.tasks[job2['id']]
        assert store.run(pid, jobs.get(pid, job2['id'])['run_id']).result['steps'][-1]['cached']
    finally:
        await jobs.close()


@pytest.mark.asyncio
async def test_clear_partial_results_preserves_dashboard_and_removes_downloads(saved_project, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from backend.app import app
    from backend.routes import project_routes as routes
    store, pid, full_run = saved_project
    workspace = Workspaces(store)
    current = workspace.get(pid)
    document = WorkspaceDocument.model_validate(current['document'])
    document.steps = document.steps[:1]
    document.dashboard.widgets = []
    workspace.write(pid, current['version'], document, trusted=True)
    jobs = ProjectJobs(store, ProjectService(store), SimpleNamespace(sync=AsyncMock()), ProjectEvents())
    for name, value in [('store', store), ('jobs', jobs)]:
        monkeypatch.setattr(routes, name, value)
    try:
        job = jobs.create(pid, workspace.get(pid)['version'], {})
        await jobs.tasks[job['id']]
        run = store.partial_run(pid)
        assert run is not None
        async with AsyncClient(transport=ASGITransport(app), base_url='http://localhost') as client:
            path = f'/api/projects/{pid}/runs/{run.run_id}/tables/cleaned'
            assert (await client.get(path)).status_code == 200
            response = await client.delete(f'/api/projects/{pid}/temporary-results')
            assert response.status_code == 200
            assert response.json()['partial_run'] is None
            assert (await client.get(path)).status_code == 404
        assert store.get(pid)['display_run_id'] == full_run.run_id
        assert (store.run_dir(pid, full_run.run_id)/'output'/'cache.json').exists()
        assert (store.run_dir(pid, run.run_id)/'request.json').exists()
    finally:
        await jobs.close()
