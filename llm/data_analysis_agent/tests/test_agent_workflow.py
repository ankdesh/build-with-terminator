"""Workflow contracts, isolation and numerical evidence use deterministic fixtures."""
import json
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pandas as pd
import pytest
from backend.services.agent_contracts import AnalysisPlan, QueryOperation, Route
from backend.services.agent_controller import AgentController
from backend.services.agent_store import AgentStore
from backend.services.llm_gateway import LLMGateway, ModelRequest, ProviderError, provider_schema
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.temporary_analysis import TemporaryAnalysis, analysis_snapshot
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from pipeline_core.analysis_tools import query_frame
from pipeline_core.workspace import WorkspaceDocument
from config import config
from tests.test_projects import saved_project


def test_provider_schema_preserves_property_names_and_requires_fields():
    schema={'type':'object','properties':{'title':{'type':'string','minLength':1},'default':{'type':'integer','minimum':1}},'title':'Schema'}
    wire=provider_schema(schema)
    assert set(wire['properties'])=={'title','default'}
    assert 'minLength' not in wire['properties']['title']
    assert wire['required']==['title','default']
    assert wire['additionalProperties'] is False


@pytest.mark.asyncio
async def test_bedrock_wire_metadata_and_truncation():
    client=Mock()
    client.converse.return_value={'output':{'message':{'content':[{'text':'{"kind":"answer","message":"OK"}'}]}},
        'stopReason':'end_turn','usage':{'inputTokens':10},'ResponseMetadata':{'RequestId':'request'}}
    gateway=LLMGateway(settings=replace(config,llm_provider='bedrock'),bedrock_client=client)
    result=await gateway.generate(ModelRequest([{'role':'system','content':'Route'},{'role':'user','content':'Hi'}],schema=Route.model_json_schema(),job='route'))
    assert result.provider=='bedrock' and result.request_id=='request'
    options=client.converse.call_args.kwargs
    assert options['system']==[{'text':'Route'}] and options['modelId']==config.bedrock_model_id
    assert options['outputConfig']['textFormat']['type']=='json_schema'
    client.converse.return_value['stopReason']='max_tokens'
    with pytest.raises(ProviderError,match='limit'): await gateway.generate(ModelRequest([{'role':'user','content':'Hi'}]))


def test_query_uses_all_rows_and_literal_filters():
    frame=pd.DataFrame({'group':['A']*200+['B'],'value':[1]*200+[500]})
    result=query_frame(frame,[{'op':'aggregate','column':'value','group_by':['group'],'metric':'sum','alias':'total'},
        {'op':'sort','column':'total'},{'op':'limit','limit':1}])
    assert result.to_dict('records')==[{'group':'B','total':500}]
    assert len(query_frame(pd.DataFrame({'name':['a.b','axb']}),[{'op':'filter','column':'name','operator':'contains','value_json':'"a.b"'}]))==1
    with pytest.raises(ValueError,match='Unknown columns'): query_frame(frame,[{'op':'sort','column':'missing'}])


def test_turns_idempotent_scoped_and_recoverable(saved_project):
    store,pid,_=saved_project;state=AgentStore(store);workspace=Workspaces(store).get(pid)
    turn,created=state.create(pid,'Question',{'stage_id':None,'label':'Project'},workspace,store.get(pid)['dataset_hash'],'request')
    assert created
    assert state.create(pid,'Question',turn['context'],workspace,turn['input_hash'],'request')[1] is False
    with pytest.raises(WorkspaceConflict): state.create(pid,'Other',turn['context'],workspace,turn['input_hash'])
    other=store.create()['id']
    with pytest.raises(KeyError): state.get(other,turn['id'])
    assert state.event(turn,{'event':'status'})['sequence']==1
    assert state.event(turn,{'event':'status'})['sequence']==2
    turn['status']='awaiting_clarification';state.put(turn);store.recover()
    assert state.get(pid,turn['id'])['status']=='awaiting_clarification'
    turn['status']='routing';state.put(turn);store.recover()
    assert state.get(pid,turn['id'])['status']=='interrupted'


@pytest.mark.asyncio
async def test_clarification_resumes_original_request_without_duplicate_user(saved_project):
    store,pid,_=saved_project
    llm=SimpleNamespace(complete=AsyncMock(side_effect=[json.dumps({'kind':'clarification','message':'Choose a metric','questions':[
        {'question':'Which metric means best?','choices':['Total','Average'],'saveable':True}]}),json.dumps({'kind':'answer','message':'I will use the total.'})]))
    service=ProjectService(store);service.agent.llm=llm;chat=AgentController(service)
    before=Workspaces(store).get(pid)
    result=await chat.respond(pid,'Which zone is best?',None,before['version'],lambda _:None,threading.Event(),request_id='clarify')
    item=chat.items.get(pid,result['id']);turn=chat.answer_questions(pid,item['id'],[{'question_id':item['questions'][0]['id'],'text':'Total','save_as_rule':True}])
    assert not turn.get('selected_source')
    await chat.respond(pid,turn['query'],None,None,lambda _:None,threading.Event(),resume_turn=turn['id'])
    assert chat.state.get(pid,turn['id'])['status']=='completed'
    assert len(chat.state.rules(pid))==1
    assert [m['content'] for m in store.messages(pid)].count('Which zone is best?')==1
    assert Workspaces(store).get(pid)==before
    evidence=json.loads(llm.complete.await_args.args[0][1]['content'])
    assert evidence['request']=='Which zone is best?' and evidence['confirmed_answers'][0]['answer']=='Total'


@pytest.mark.asyncio
async def test_temporary_analysis_isolated_and_no_saved_state_change(saved_project):
    store,pid,_=saved_project;service=ProjectService(store);before=store.view(pid)
    state=AgentStore(store);turn,_=state.create(pid,'Sum?',{'stage_id':None,'label':'Project'},before['workspace'],store.get(pid)['dataset_hash'])
    plan=AnalysisPlan(kind='query',message='Sum',operations=[QueryOperation(op='aggregate',column='value',metric='sum',alias='total')])
    artifact=await TemporaryAnalysis(service).execute(pid,plan,turn,threading.Event())
    assert artifact['result']['rows']==[{'total':30.0}]
    assert artifact['provenance']['source']=='draft cleaning: cleaned'
    assert state.artifact_file(pid,artifact['id'],artifact['result']['csv_file']).is_file()
    after=store.view(pid)
    assert after['workspace']==before['workspace'] and after['display_run']==before['display_run'] and after['revisions']==before['revisions']
    with pytest.raises(ValueError): state.artifact_file(pid,artifact['id'],'../input.csv')
    turn['status']='completed';state.put(turn);state.prune(pid,clear=True)
    assert state.artifact(pid,artifact['id'])['expired']

class ScriptedGateway(LLMGateway):
    def __init__(self, responses):
        super().__init__(settings=replace(config,llm_provider='bedrock'),bedrock_client=Mock())
        self.responses=iter(responses);self.requests=[]
    async def generate(self, request):
        from backend.services.llm_gateway import ModelResponse
        self.requests.append(request)
        try: value=next(self.responses)
        except StopIteration: raise AssertionError('Unexpected model call: '+request.messages[1]['content'])
        return ModelResponse(json.dumps(value),'bedrock','fixture')


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_code',[
 "def calculate(inputs, parameters, context):\n    return {'total': missing_variable, 'records': inputs['cleaned']}\n",
 "def calculate(inputs, parameters, context):\n    return {'total': ( , 'records': inputs['cleaned']}\n",
])
async def test_exact_failed_candidate_is_repaired_before_review(saved_project,bad_code):
    store,pid,_=saved_project;before=store.view(pid)
    edit={'summary':'Use mean','operations':[{'op':'update','kind':'step','target_id':'totals','code_request':'Calculate mean, retaining records.'}]}
    good="def calculate(inputs, parameters, context):\n    df=inputs['cleaned'].copy()\n    return {'total': float(df['value'].mean()) if len(df) else None, 'records': df, 'finding': 'Mean unavailable' if not len(df) else str(df['value'].mean())}\n"
    llm=ScriptedGateway([{'kind':'proposal','message':'Prepare the mean calculation.'},edit,{'code':bad_code},edit,{'code':good}])
    service=ProjectService(store);service.agent.llm=llm;chat=AgentController(service)
    result=await chat.respond(pid,'Change sum to mean, retaining the outputs.', 'step:totals',before['workspace']['version'],lambda _:None,threading.Event())
    assert result['kind']=='proposal' and result['validation']['status']=='passed'
    assert 'empty_selection' in result['validation']['checks']
    second_plan=json.loads(llm.requests[3].messages[1]['content'])
    assert second_plan['workspace']['steps'][1]['code']==bad_code
    assert second_plan['validation_error']
    assert Workspaces(store).get(pid)==before['workspace']
    assert chat.items.get(pid,result['id'])['document']['steps'][1]['code']==good


@pytest.mark.asyncio
async def test_scope_confirmation_resumes_without_silent_expansion(saved_project):
    store,pid,_=saved_project;before=store.view(pid)
    llm=ScriptedGateway([{'kind':'proposal','message':'Change project title.','requested_scope':'project'},
        {'summary':'Rename project','operations':[{'op':'update','kind':'project','target_id':'settings','fields_json':'{"title":"Approved title"}'}]}])
    service=ProjectService(store);service.agent.llm=llm;chat=AgentController(service)
    result=await chat.respond(pid,'Rename the project.', 'widget:total',before['workspace']['version'],lambda _:None,threading.Event())
    item=chat.items.get(pid,result['id']);assert item['phase']=='scope'
    assert len(llm.requests)==1
    turn=chat.answer_questions(pid,item['id'],[{'question_id':item['questions'][0]['id'],'text':'Use Project scope'}])
    result=await chat.respond(pid,turn['query'],None,None,lambda _:None,threading.Event(),resume_turn=turn['id'])
    assert result['context']['stage_id'] is None and result['kind']=='proposal'
    assert Workspaces(store).get(pid)==before['workspace']


@pytest.mark.asyncio
async def test_stale_clarification_requires_explicit_context_refresh(saved_project):
    store,pid,_=saved_project;service=ProjectService(store)
    service.agent.llm=ScriptedGateway([{'kind':'clarification','message':'Which measure?','questions':[{'question':'Which measure?'}]}])
    chat=AgentController(service);result=await chat.respond(pid,'Best?',None,None,lambda _:None,threading.Event())
    item=chat.items.get(pid,result['id']);workspace=Workspaces(store).get(pid);document=WorkspaceDocument.model_validate(workspace['document']);document.title='Changed'
    Workspaces(store).write(pid,workspace['version'],document)
    answers=[{'question_id':item['questions'][0]['id'],'text':'Mean'}]
    with pytest.raises(WorkspaceConflict): chat.answer_questions(pid,item['id'],answers)
    turn=chat.answer_questions(pid,item['id'],answers,refresh_context=True)
    assert turn['workspace_version']==workspace['version']+1 and turn['resume_phase']=='routing'
    assert not turn.get('route')


def test_rules_require_review_when_input_columns_change(saved_project,tmp_path):
    store,pid,_=saved_project;state=AgentStore(store);rule=state.save_rule(pid,'Best means highest mean value')
    assert state.rules(pid)[0]['needs_review'] is False
    path=tmp_path/'changed.csv';path.write_text('zone,other\nA,1\n')
    store.save_dataset(pid,path,'changed.csv',{'columns':[{'name':'other','data_type':'float'}]},'')
    assert state.rules(pid)[0]['needs_review'] is True
    state.save_rule(pid,rule['text'],rule['id'])
    assert state.rules(pid)[0]['needs_review'] is False
    other=store.create()['id']
    with pytest.raises(KeyError): state.delete_rule(other,rule['id'])


@pytest.mark.asyncio
async def test_cancel_paused_request_is_monotonic_and_frees_project(saved_project):
    store,pid,_=saved_project;service=ProjectService(store);service.agent.llm=ScriptedGateway([{'kind':'clarification','message':'Choose','questions':[{'question':'Which measure?'}]}])
    chat=AgentController(service);result=await chat.respond(pid,'Best?',None,None,lambda _:None,threading.Event())
    item=chat.items.get(pid,result['id']);turn=chat.cancel(pid,item['turn_id'])
    assert turn['status']=='cancelled' and chat.state.active(pid) is None
    assert chat.items.get(pid,item['id'])['status']=='discarded'
    turn['status']='completed';chat.state.put(turn)
    assert chat.state.get(pid,turn['id'])['status']=='cancelled'


@pytest.mark.asyncio
async def test_analysis_failure_does_not_misreport_cleaning_failure(saved_project):
    store,pid,_=saved_project;service=ProjectService(store);before=store.view(pid);state=AgentStore(store)
    turn,_=state.create(pid,'Bad analysis',{'stage_id':None,'label':'Project'},before['workspace'],store.get(pid)['dataset_hash'])
    plan=AnalysisPlan(kind='python',message='Fail analysis',code="def analyze(inputs, parameters, context):\n    raise ValueError('analysis failure')\n")
    from backend.services.workspace_editor import NeedsClarification
    with pytest.raises(ValueError,match='analysis failure') as error:
        await TemporaryAnalysis(service).execute(pid,plan,turn,threading.Event())
    assert not isinstance(error.value,NeedsClarification)


@pytest.mark.asyncio
async def test_cleaning_failure_asks_before_raw_fallback(saved_project):
    store,pid,_=saved_project;workspace=Workspaces(store).get(pid);document=WorkspaceDocument.model_validate(workspace['document']);document.steps[0].code="def clean(inputs, parameters, context):\n    raise ValueError('broken cleaning')\n"
    Workspaces(store).write(pid,workspace['version'],document,trusted=True);workspace=Workspaces(store).get(pid);state=AgentStore(store)
    turn,_=state.create(pid,'Sum?',{'stage_id':None,'label':'Project'},workspace,store.get(pid)['dataset_hash'])
    from backend.services.workspace_editor import NeedsClarification
    with pytest.raises(NeedsClarification) as error:
        await TemporaryAnalysis(ProjectService(store)).execute(pid,AnalysisPlan(kind='query',message='Count'),turn,threading.Event())
    assert error.value.phase=='source' and 'Use raw data for this request' in error.value.questions[0].choices


def test_aggregate_cannot_silently_ignore_filter_predicate():
    with pytest.raises(ValueError,match='separate filter'):
        QueryOperation(op='aggregate',operator='is_null',metric='count')


@pytest.mark.asyncio
async def test_matching_temporary_result_reused_and_tampered_result_recomputed(saved_project):
    store,pid,_=saved_project;service=ProjectService(store);workspace=Workspaces(store).get(pid);state=AgentStore(store)
    turn,_=state.create(pid,'Sum?',{'stage_id':None,'label':'Project'},workspace,store.get(pid)['dataset_hash'])
    plan=AnalysisPlan(kind='query',message='Sum',operations=[QueryOperation(op='aggregate',column='value',metric='sum')])
    runner=TemporaryAnalysis(service)
    first=await runner.execute(pid,plan,turn,threading.Event())
    second=await runner.execute(pid,plan,turn,threading.Event())
    assert second['id']==first['id'] and second['cache_hit']
    path=state.artifact_file(pid,first['id'],first['result']['csv_file']);path.write_text('tampered')
    third=await runner.execute(pid,plan,turn,threading.Event())
    assert third['id']!=first['id'] and third['result']['rows']==[{'value':30.0}]


@pytest.mark.asyncio
async def test_sandbox_hides_host_files_and_credentials(tmp_path, simple_revision, input_csv,monkeypatch):
    from backend.services.sandbox_runner import SandboxRunner
    from pipeline_core.partial import PartialRevision
    secret=tmp_path/'host-secret';secret.write_text('not visible to worker')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','not-visible')
    payload=simple_revision.model_dump();payload['parameters']=[];payload['dashboard']['widgets']=[]
    payload['steps']=[{'id':'probe','title':'Probe','stage':'analysis','function':'probe','inputs':['data'],'outputs':['check'],
        'code':f"import os\ndef probe(inputs, parameters, context):\n    return {{'check': os.path.exists({str(secret)!r}) or bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))}}\n"}]
    result=await SandboxRunner().run(PartialRevision.model_validate(payload),input_csv,{},tmp_path/'isolated',threading.Event())
    assert result['success'] and result['result']['outputs']['check']['value'] is False
    assert not (tmp_path/'isolated'/'input.csv').exists()


@pytest.mark.asyncio
async def test_schema_repair_updates_existing_ids_and_removes_invalid_fields(saved_project):
    store,pid,_=saved_project;service=ProjectService(store)
    llm=ScriptedGateway([{'kind':'proposal','message':'Prepare widget'},
        {'summary':'Add metric','operations':[{'op':'add','kind':'widget','target_id':'reviewed','fields_json':json.dumps({'kind':'metric','type':'metric','title':'Reviewed','output':'total'})}]},
        {'summary':'Repair metric fields','operations':[{'op':'update','kind':'widget','target_id':'reviewed','fields_json':'{}','unset_fields':['type']}]}])
    service.agent.llm=llm;chat=AgentController(service)
    result=await chat.respond(pid,'Add a second metric titled Reviewed.',None,None,lambda _:None,threading.Event())
    assert result['kind']=='proposal' and result['validation']['status']=='passed'
    context=json.loads(llm.requests[2].messages[1]['content'])
    assert context['repairing_candidate'] and context['supported_entity_schemas']['widget']
    assert context['workspace']['dashboard']['widgets'][-1]['type']=='metric'
    document=chat.items.get(pid,result['id'])['document']
    assert document['dashboard']['widgets'][-1]['id']=='reviewed' and 'type' not in document['dashboard']['widgets'][-1]


@pytest.mark.asyncio
async def test_redundant_source_echo_does_not_trigger_generation(saved_project):
    store,pid,_=saved_project;workspace=Workspaces(store).get(pid);code=workspace['document']['steps'][0]['code']
    llm=ScriptedGateway([{'kind':'proposal','message':'Rename'}, {'summary':'Rename cleaning','operations':[
        {'op':'update','kind':'step','target_id':'cleanup','fields_json':json.dumps({'title':'Reviewed cleaning','code':code})}]}])
    service=ProjectService(store);service.agent.llm=llm
    result=await AgentController(service).respond(pid,'Rename this stage to Reviewed cleaning.', 'step:cleanup',None,lambda _:None,threading.Event())
    assert result['kind']=='proposal' and [request.job for request in llm.requests]==['route_request','edit_plan']
    assert all(change['field']!='code' for change in result['changes'])
    context=json.loads(llm.requests[1].messages[1]['content'])
    assert 'code' not in context['supported_entity_schemas']['step']['properties']

