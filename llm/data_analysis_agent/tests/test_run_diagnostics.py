"""Chat receives bounded project-only run evidence and saves requested repairs."""

import json
from pathlib import Path
import threading
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.run_diagnostics import collect_run_diagnostics, MAX_CONTEXT_CHARS
from backend.services.workspace_service import Workspaces
from pipeline_core.engine import fingerprint
from pipeline_core.models import RunRecord, ProjectRevision


def prepare(tmp_path, source, revision):
    store = ProjectStore(tmp_path/'projects')
    pid = store.create()['id']
    store.save_dataset(pid, source, source.name, {}, '')
    store.save_revision(pid, revision)
    return store, pid


def test_diagnostics_include_failure_logs_and_redact_secrets(tmp_path, input_csv, simple_revision):
    store, pid = prepare(tmp_path, input_csv, simple_revision)
    run = RunRecord(revision_id=simple_revision.revision_id, dataset_name='source.csv', input_hash=fingerprint(input_csv), parameters={}, status='failed', error='Wrong datatype')
    store.put_run(pid, run)
    directory = store.run_dir(pid, run.run_id);output=directory/'output';output.mkdir(parents=True)
    (directory/'input.csv').write_bytes(input_csv.read_bytes())
    (output/'diagnostics.json').write_text(json.dumps({'error':'Wrong datatype','traceback':'TypeError: cannot add strings', 'stdout':'custom-key Bearer another-secret sk-private-key'}))
    (output/'events.jsonl').write_text(json.dumps({'event':'step','step_id':'totals','status':'running','data':'must not be sent'})+'\n')
    result=collect_run_diagnostics(store,pid,secret='custom-key')
    found=result['runs'][0]
    assert found['traceback']=='TypeError: cannot add strings'
    assert found['step_events']==[{'event':'step','step_id':'totals','status':'running'}]
    assert found['input_preview']['columns']==['zone','value']
    assert found['current_builder_input']
    encoded=json.dumps(result)
    for secret in ['custom-key','another-secret','sk-private-key','must not be sent']:
        assert secret not in encoded
    assert '[redacted]' in encoded


def test_diagnostics_support_old_responses_and_target_runs(tmp_path, input_csv, simple_revision):
    store,pid=prepare(tmp_path,input_csv,simple_revision)
    run=RunRecord(revision_id=simple_revision.revision_id,dataset_name='replacement.csv',input_hash='different',parameters={},status='failed',error='Missing required columns: value')
    directory=store.project_dir(pid)/'target/runs'/run.run_id;output=directory/'output';output.mkdir(parents=True)
    (directory/'record.json').write_text(run.model_dump_json())
    (directory/'input.csv').write_text('zone,amount\nA,12\n')
    (output/'response.json').write_text(json.dumps({'traceback':'ValueError: Missing required columns: value','stdout':'old worker output'}))
    result=collect_run_diagnostics(store,pid,run.run_id)
    assert result['runs'][0]['source']=='target'
    assert not result['runs'][0]['current_builder_input']
    assert result['runs'][0]['stdout']=='old worker output'
    assert result['runs'][0]['input_preview']['columns']==['zone','amount']


def test_diagnostics_do_not_cross_projects_or_follow_external_log_links(tmp_path,input_csv,simple_revision):
    store,pid=prepare(tmp_path,input_csv,simple_revision)
    other=store.create()['id'];store.save_dataset(other,input_csv,'other.csv',{},'')
    run=RunRecord(revision_id=simple_revision.revision_id,dataset_name='other.csv',input_hash='other',parameters={},status='failed',error='other project private error')
    store.put_run(other,run)
    assert collect_run_diagnostics(store,pid,run.run_id)['runs']==[]
    own=RunRecord(revision_id=simple_revision.revision_id,dataset_name='source.csv',input_hash='own',parameters={},status='failed')
    store.put_run(pid,own);directory=store.run_dir(pid,own.run_id);output=directory/'output';output.mkdir(parents=True)
    private=tmp_path/'private.json';private.write_text('{"traceback":"PRIVATE TEXT"}')
    (output/'diagnostics.json').symlink_to(private)
    assert 'PRIVATE TEXT' not in json.dumps(collect_run_diagnostics(store,pid))


def test_diagnostics_bound_unicode_and_large_artifacts(tmp_path,input_csv,simple_revision):
    store,pid=prepare(tmp_path,input_csv,simple_revision)
    for _ in range(4):
        run=RunRecord(revision_id=simple_revision.revision_id,dataset_name='source.csv',input_hash=fingerprint(input_csv),parameters={},status='failed',error='Error')
        store.put_run(pid,run);directory=store.run_dir(pid,run.run_id);output=directory/'output';output.mkdir(parents=True)
        (output/'diagnostics.json').write_text(json.dumps({'stdout':'測試'*32000,'traceback':'trace'*3200}))
        (output/'response.json').write_text('{"result":"'+('SHOULD_NOT_APPEAR'*100000)+'"}')
    result=collect_run_diagnostics(store,pid)
    assert len(result['runs'])<=3
    assert len(json.dumps(result,ensure_ascii=True))<=MAX_CONTEXT_CHARS
    assert 'SHOULD_NOT_APPEAR' not in json.dumps(result)


@pytest.mark.asyncio
async def test_requested_dtype_repair_uses_real_failed_run_without_running_on_chat(tmp_path, input_csv, simple_revision):
    store,pid=prepare(tmp_path,input_csv,simple_revision)
    service=ProjectService(store)
    good=await service.execute(pid,simple_revision,{},lambda _:None,threading.Event())
    assert good.status=='succeeded'
    replacement=tmp_path/'commas.csv';replacement.write_text('zone,value\nA,"1,200"\nB,300\n')
    store.save_dataset(pid,replacement,'commas.csv',{},'Values allow thousands separators.')
    failed=await service.execute(pid,simple_revision,{},lambda _:None,threading.Event())
    assert failed.status=='failed' and 'Invalid values in column value' in failed.error
    payload=simple_revision.model_dump();payload.update(revision_id=str(uuid4()),parent_revision_id=simple_revision.revision_id)
    payload['input_contract']['columns'][1]['dtype']='string'
    payload['steps'][0]['code']="def clean(inputs, parameters, context):\n    df=inputs['data'].copy()\n    df['value']=pd.to_numeric(df['value'].str.replace(',', '', regex=False), errors='raise')\n    return {'cleaned':df.drop_duplicates().dropna(subset=['value'])}\n"
    repaired=ProjectRevision.model_validate(payload)
    agent=AsyncMock();agent.propose.return_value=repaired
    chat_runner=AsyncMock()
    await ProjectService(store,agent=agent,runner=chat_runner).build(pid,'Fix the latest failed run; values allow thousands separators.',lambda _:None,threading.Event())
    evidence=agent.propose.await_args.kwargs['run_diagnostics']['runs'][0]
    assert evidence['run_id']==failed.run_id
    assert 'read_input' in evidence['traceback']
    assert evidence['input_preview']['rows'][0]['value']=='1,200'
    chat_runner.run.assert_not_awaited()
    assert store.get(pid)['display_run_id']==good.run_id
    workspace=Workspaces(store);state=workspace.get(pid)
    rerun=await service.execute(pid,workspace.compile(pid,state['version']),{},lambda _:None,threading.Event())
    assert rerun.status=='succeeded'
    assert rerun.result['outputs']['total']['value']==1500
    assert replacement.read_text()=='zone,value\nA,"1,200"\nB,300\n'


@pytest.mark.asyncio
async def test_requested_missing_column_repair_uses_failure_and_preserves_csv(tmp_path, input_csv, simple_revision):
    store, pid = prepare(tmp_path, input_csv, simple_revision)
    replacement = tmp_path/'renamed.csv'
    replacement.write_text('zone,amount\nA,20\nB,30\n')
    store.save_dataset(pid, replacement, replacement.name, {}, 'amount replaces value, with the same units.')
    service = ProjectService(store)
    failed = await service.execute(pid, simple_revision, {}, lambda _: None, threading.Event())
    assert failed.status == 'failed' and 'Missing required columns' in failed.error
    payload = simple_revision.model_dump()
    payload.update(revision_id=str(uuid4()), parent_revision_id=simple_revision.revision_id)
    payload['input_contract']['columns'][1]['name'] = 'amount'
    payload['steps'][0]['code'] = "def clean(inputs, parameters, context):\n    df=inputs['data'].rename(columns={'amount':'value'})\n    return {'cleaned':df.drop_duplicates().dropna(subset=['value'])}\n"
    agent = AsyncMock()
    agent.propose.return_value = ProjectRevision.model_validate(payload)
    runner = AsyncMock()
    await ProjectService(store, agent=agent, runner=runner).build(pid,
        'Fix the latest failed run. The supplier renamed value to amount; same units and meaning.',
        lambda _: None, threading.Event())
    evidence = agent.propose.await_args.kwargs['run_diagnostics']['runs'][0]
    assert evidence['run_id'] == failed.run_id
    assert evidence['input_preview']['columns'] == ['zone', 'amount']
    runner.run.assert_not_awaited()
    workspace = Workspaces(store)
    state = workspace.get(pid)
    result = await service.execute(pid, workspace.compile(pid, state['version']), {}, lambda _: None, threading.Event())
    assert result.status == 'succeeded'
    assert result.result['outputs']['total']['value'] == 50
    assert replacement.read_text() == 'zone,amount\nA,20\nB,30\n'


@pytest.mark.asyncio
async def test_worker_preserves_printed_output_when_generated_code_fails(tmp_path, input_csv, simple_revision):
    payload = simple_revision.model_dump()
    payload['steps'][1]['code'] = "def calculate(inputs, parameters, context):\n    print('About to parse the selected data')\n    raise ValueError('Parsing failed here')\n"
    revision = ProjectRevision.model_validate(payload)
    store, pid = prepare(tmp_path, input_csv, revision)
    failed = await ProjectService(store).execute(pid, revision, {}, lambda _: None, threading.Event())
    assert failed.status == 'failed'
    evidence = collect_run_diagnostics(store, pid)['runs'][0]
    assert 'About to parse the selected data' in evidence['stdout']
    assert 'Parsing failed here' in evidence['traceback']
