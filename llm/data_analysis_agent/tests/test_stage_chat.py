"""Questions are read-only; only reviewed, version-bound changes can be applied."""
import asyncio
import json
import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.services.chat_service import ChatService
from backend.services.chat_store import ChatStore, review_changes
from backend.services.project_agent import ProjectAgent
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from pipeline_core.workspace import WorkspaceDocument
from tests.test_projects import saved_project


def chat_service(store, outputs):
    agent = ProjectAgent()
    agent.llm = SimpleNamespace(complete=AsyncMock(side_effect=[json.dumps(value) for value in outputs]))
    return ChatService(ProjectService(store, agent=agent))


@pytest.mark.asyncio
async def test_question_preserves_workspace_revisions_description_and_results(saved_project):
    store, pid, run = saved_project
    before = store.view(pid)
    chat = chat_service(store, [{'kind': 'answer', 'message': 'The cleanup removes duplicate rows and missing readings.'}])
    await chat.respond(pid, 'What does this stage do?', 'step:cleanup', before['workspace']['version'], lambda _: None, threading.Event())
    after = store.view(pid)
    assert after['workspace'] == before['workspace']
    assert after['revisions'] == before['revisions']
    assert after['project']['description'] == before['project']['description']
    assert after['display_run']['run_id'] == run.run_id
    assert after['chat_items'] == []
    assert after['messages'][-1]['metadata']['context']['stage_id'] == 'step:cleanup'
    assert after['messages'][-1]['metadata']['run_id'] == run.run_id
    evidence = json.loads(chat.service.agent.llm.complete.await_args.args[0][1]['content'])
    assert evidence['saved_results']['outputs']['total']['value'] == 30
    assert evidence['selected_context']['stage_id'] == 'step:cleanup'


@pytest.mark.asyncio
async def test_proposal_requires_apply_and_is_idempotent_and_undoable(saved_project):
    store, pid, _ = saved_project
    before = Workspaces(store).get(pid)
    chat = chat_service(store, [{'kind': 'proposal', 'message': 'Rename this chart.'},
        {'summary': 'Rename the metric', 'changes': [{'op': 'replace', 'path': '/dashboard/widgets/0/title', 'value': 'Reviewed total'}]}])
    item = await chat.respond(pid, 'Rename to Reviewed total', 'widget:total', before['version'], lambda _: None, threading.Event())
    assert Workspaces(store).get(pid) == before
    assert store.view(pid)['chat_items'][0]['status'] == 'pending'
    assert ProjectStore(store.root).view(pid)['chat_items'][0]['status'] == 'pending'
    reviews = ChatStore(store)
    applied = reviews.apply(pid, item['id'])
    current = Workspaces(store).get(pid)
    assert current['version'] == before['version']+1
    assert current['document']['dashboard']['widgets'][0]['title'] == 'Reviewed total'
    assert reviews.apply(pid, item['id']) == applied
    assert Workspaces(store).get(pid)['version'] == current['version']
    Workspaces(store).write(pid, current['version'], WorkspaceDocument.model_validate(current['document']), action='undo')
    assert Workspaces(store).get(pid)['document'] == before['document']


@pytest.mark.asyncio
async def test_linked_producer_edits_need_reasons_and_reject_unrelated_globals(saved_project):
    store, pid, _ = saved_project
    base = Workspaces(store).get(pid)['document']
    changed = json.loads(json.dumps(base))
    changed['steps'][1]['title'] = 'Explained calculation'
    with pytest.raises(ValueError, match='Explain each related'):
        review_changes(base, changed, 'widget:total', {})
    review = review_changes(base, changed, 'widget:total', {'step:totals': 'The metric is computed by this producer.'})
    assert 'step:totals' in review['affected'] and 'widget:total' in review['affected']
    changed['title'] = 'Unrelated project rename'
    with pytest.raises(ValueError, match='Unrelated edits'):
        review_changes(base, changed, 'widget:total', {})


def test_sibling_analysis_is_not_in_selected_stage_scope(simple_revision):
    base = WorkspaceDocument.from_revision(simple_revision).model_dump()
    sibling = {**base['steps'][1], 'id': 'sibling', 'outputs': ['another'],
        'code': "def calculate(inputs, parameters, context):\n    return {'another': 1}\n"}
    base['steps'].append(sibling)
    changed = json.loads(json.dumps(base))
    changed['steps'][2]['title'] = 'Do not change a sibling'
    with pytest.raises(ValueError, match='Unrelated edits'):
        review_changes(base, changed, 'step:totals', {'step:sibling': 'Both share cleaned data'})


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['workspace', 'input'])
async def test_stale_proposal_never_applies(saved_project, tmp_path, change):
    store, pid, _ = saved_project
    chat = chat_service(store, [{'kind': 'proposal', 'message': 'Rename metric'},
        {'summary': 'Rename metric', 'changes': [{'op': 'replace', 'path': '/dashboard/widgets/0/title', 'value': 'New'}]}])
    item = await chat.respond(pid, 'Rename', 'widget:total', None, lambda _: None, threading.Event())
    workspace = Workspaces(store)
    current = workspace.get(pid)
    if change == 'workspace':
        document = WorkspaceDocument.model_validate(current['document']); document.title = 'Concurrent edit'
        workspace.write(pid, current['version'], document)
    else:
        source = tmp_path/'replacement.csv'; source.write_text('zone,value\nA,999\n')
        store.save_dataset(pid, source, source.name, {}, '')
    with pytest.raises(WorkspaceConflict): ChatStore(store).apply(pid, item['id'])
    assert workspace.get(pid)['document']['dashboard']['widgets'][0]['title'] != 'New'
    assert store.view(pid)['chat_items'][0]['stale']


@pytest.mark.asyncio
async def test_incomplete_input_only_proposal_does_not_create_pipeline(tmp_path):
    store = ProjectStore(tmp_path/'projects'); pid = store.create()['id']
    source = tmp_path/'data.csv'; source.write_text('zone,value\nA,10\n')
    store.save_dataset(pid, source, source.name, {}, '')
    document = Workspaces(store).get(pid)['document']
    document['input_contract'] = {'columns': [{'name': 'zone', 'dtype': 'string'}, {'name': 'value', 'dtype': 'number'}]}
    chat = chat_service(store, [{'kind': 'proposal', 'message': 'Define only input types.'}, document])
    item = await chat.respond(pid, 'Define these input types only', 'input:data', None, lambda _: None, threading.Event())
    assert item['issues']
    ChatStore(store).apply(pid, item['id'])
    current = Workspaces(store).get(pid)
    assert current['document']['steps'] == [] and current['document']['dashboard']['widgets'] == []
    with pytest.raises(ValueError): Workspaces(store).compile(pid, current['version'])


@pytest.mark.asyncio
async def test_discard_leaves_workspace_unchanged(saved_project):
    store, pid, _ = saved_project
    before = Workspaces(store).get(pid)
    chat = chat_service(store, [{'kind': 'needs_run', 'message': 'Run the current calculations to get fresh results.'}])
    await chat.respond(pid, 'What are current totals?', None, None, lambda _: None, threading.Event())
    item = store.view(pid)['chat_items'][0]
    ChatStore(store).discard(pid, item['id'])
    assert Workspaces(store).get(pid) == before
    assert store.view(pid)['chat_items'][0]['status'] == 'discarded'


@pytest.mark.asyncio
async def test_api_run_and_reask_runs_once_and_followup_is_answer_only(saved_project, monkeypatch):
    from backend.app import app
    from backend.routes import project_routes as routes
    from backend.services.project_jobs import ProjectEvents, ProjectJobs
    store, pid, _ = saved_project
    chat = chat_service(store, [{'kind': 'needs_run', 'message': 'A fresh run is required.'},
        {'kind': 'answer', 'message': 'The saved total is 30.'}])
    targets = SimpleNamespace(sync=AsyncMock())
    events = ProjectEvents()
    jobs = ProjectJobs(store, chat.service, targets, events)
    for name, value in [('store', store), ('service', chat.service), ('jobs', jobs), ('events', events), ('targets', targets)]:
        monkeypatch.setattr(routes, name, value)
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url='http://localhost') as client:
            response = await client.post(f'/api/projects/{pid}/chat', json={'query': 'What is the total?', 'stage_id': 'step:totals', 'description': 'Must not overwrite description'})
            assert response.status_code == 200
            item = store.view(pid)['chat_items'][0]
            response = await client.post(f'/api/projects/{pid}/chat/items/{item["id"]}/run')
            assert response.status_code == 202, response.text
            duplicate = await client.post(f'/api/projects/{pid}/chat/items/{item["id"]}/run')
            assert duplicate.json()['id'] == response.json()['id']
            await asyncio.gather(*list(jobs.tasks.values()))
            await asyncio.gather(*list(routes.chat_followups.values()))
        result = ChatStore(store).get(pid, item['id'])
        assert result['run_status'] == 'answered', result
        assert chat.service.agent.llm.complete.await_count == 2
        evidence = json.loads(chat.service.agent.llm.complete.await_args.args[0][1]['content'])
        assert evidence['answer_only'] is True
        assert store.messages(pid)[-1]['metadata']['kind'] == 'answer'
        assert store.get(pid)['description'] != 'Must not overwrite description'
        assert len(jobs.list(pid)) == 1
    finally:
        await jobs.close()


@pytest.mark.asyncio
async def test_inspector_gated_and_widget_links_to_producer(saved_project, monkeypatch):
    from backend.app import app
    from backend.routes import project_routes as routes
    store, pid, _ = saved_project
    monkeypatch.setattr(routes, 'store', store)
    async with AsyncClient(transport=ASGITransport(app), base_url='http://localhost') as client:
        monkeypatch.delenv('WPS_DEVELOPER_MODE', raising=False)
        assert (await client.get(f'/api/projects/{pid}/stages/widget:total/inspect')).status_code == 404
        assert not (await client.get('/api/capabilities')).json()['developer_mode']
        monkeypatch.setenv('WPS_DEVELOPER_MODE', '1')
        widget = (await client.get(f'/api/projects/{pid}/stages/widget:total/inspect')).json()
        assert widget['source'] is None and widget['dependencies'] == ['step:totals']
        step = (await client.get(f'/api/projects/{pid}/stages/step:totals/inspect')).json()
        assert 'def calculate' in step['source']
        attachment = await client.get(f'/api/projects/{pid}/stages/step:totals/inspect.json')
        assert attachment.status_code == 200 and 'attachment' in attachment.headers['content-disposition']
        assert attachment.json()['source'] == step['source']
        assert (await client.get('/api/capabilities')).json()['developer_mode']


def test_legacy_messages_migrate_with_project_context_default(tmp_path):
    root = tmp_path/'projects'; root.mkdir()
    with sqlite3.connect(root/'projects.sqlite3') as db:
        db.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,project_id TEXT,role TEXT,content TEXT,created_at TEXT)')
        db.execute("INSERT INTO messages VALUES(1,'legacy','user','Historical question','old')")
    store = ProjectStore(root)
    message = store.messages('legacy')[0]
    assert message['content'] == 'Historical question' and message['metadata'] == {}


def test_title_only_review_does_not_claim_entire_stage_changed(simple_revision):
    base = WorkspaceDocument.from_revision(simple_revision).model_dump()
    changed = json.loads(json.dumps(base)); changed['steps'][1]['title'] = 'New title'
    review = review_changes(base, changed, 'step:totals', {})
    assert [(c['stage_id'], c['field']) for c in review['changes']] == [('step:totals', 'title')]


@pytest.mark.asyncio
async def test_answer_only_followup_rejects_edit_or_run_requests(saved_project):
    store, pid, _ = saved_project
    before = Workspaces(store).get(pid)
    chat = chat_service(store, [{'kind': 'proposal', 'message': 'Not allowed'}]*3)
    with pytest.raises(ValueError, match='valid chat response'):
        await chat.respond(pid, 'Original question', 'step:totals', None, lambda _: None, threading.Event(), answer_only=True)
    assert Workspaces(store).get(pid) == before and store.view(pid)['chat_items'] == []


@pytest.mark.asyncio
async def test_skip_after_apply_and_stage_context_survives_rename(saved_project):
    store, pid, _ = saved_project
    chat = chat_service(store, [{'kind': 'proposal', 'message': 'Rename stage'},
        {'summary': 'Stage renamed', 'changes': [{'op': 'replace', 'path': '/steps/1/title', 'value': 'New title'}]}])
    item = await chat.respond(pid, 'Rename stage', 'step:totals', None, lambda _: None, threading.Event())
    ChatStore(store).apply(pid, item['id'])
    ChatStore(store).discard(pid, item['id'])
    assert ChatStore(store).get(pid, item['id'])['run_skipped']
    assert store.messages(pid)[-1]['metadata']['context']['label'] == 'Analysis · Totals'
    assert Workspaces(store).get(pid)['document']['steps'][1]['title'] == 'New title'


@pytest.mark.asyncio
async def test_run_job_rejects_changed_input_identity(saved_project):
    from backend.services.project_jobs import ProjectEvents, ProjectJobs
    store, pid, _ = saved_project
    service = ProjectService(store)
    jobs = ProjectJobs(store, service, SimpleNamespace(sync=AsyncMock()), ProjectEvents())
    with pytest.raises(WorkspaceConflict, match='input changed'):
        jobs.create(pid, Workspaces(store).get(pid)['version'], {}, expected_input_hash='old-input-hash')
    assert jobs.list(pid) == []


def test_shared_control_lists_all_consumers(simple_revision):
    base = WorkspaceDocument.from_revision(simple_revision).model_dump()
    changed = json.loads(json.dumps(base)); changed['parameters'][1]['default'] = 2
    review = review_changes(base, changed, 'step:totals', {'control:multiplier': 'The selected calculation uses this multiplier.'})
    assert {'control:multiplier', 'step:totals', 'widget:total'} <= set(review['affected'])


@pytest.mark.asyncio
async def test_chat_reads_verified_unbound_scalar_artifacts(saved_project):
    from backend.services.chat_service import results_preview
    from pipeline_core.models import ProjectRevision
    store, pid, _ = saved_project
    payload = store.view(pid)['draft']
    payload['steps'][1]['outputs'].append('count')
    payload['steps'][1]['code'] = payload['steps'][1]['code'].replace("'total': total,", "'total': total, 'count': len(df),")
    from uuid import uuid4
    payload.update(parent_revision_id=payload['revision_id'], revision_id=str(uuid4()))
    revision = ProjectRevision.model_validate(payload)
    store.save_revision(pid, revision)
    run = await ProjectService(store).execute(pid, revision, {}, lambda _: None, threading.Event())
    assert run.status == 'succeeded'
    assert 'count' not in run.result['outputs']
    preview = results_preview(run.model_dump(), store, pid)
    assert preview['outputs']['count']['value'] == 2
    path = store.run_dir(pid, run.run_id)/'output/count.json'
    path.write_text('999')
    assert 'count' not in results_preview(run.model_dump(), store, pid)['outputs']
