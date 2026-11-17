"""Temporary analysis uses a normal worker process and never promotes a saved run."""
from __future__ import annotations
import json
import hashlib
import shutil
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4
from backend.services.agent_contracts import AnalysisPlan, Question
from backend.services.agent_store import AgentStore
from backend.services.agent_runner import AgentRunner
from backend.services.workspace_editor import NeedsClarification, validate_generated_source
from pipeline_core.engine import PipelineEngine, chart_from_frame, fingerprint, safe_json, validate_chart
from pipeline_core.models import ChartBinding, InputContract, PipelineStep
from pipeline_core.partial import PartialRevision
from pipeline_core.validation import validate_parameters
from pipeline_core.bundle import installed_versions
from pipeline_core.workspace import WorkspaceDocument, calculation_hash


def inferred_contract(project: dict, path: Path) -> InputContract:
    encoding = 'utf-8-sig'
    try:
        with path.open(encoding=encoding) as stream:
            while stream.read(65536): pass
    except UnicodeDecodeError: encoding = 'latin1'
    columns = []
    for column in (project.get('profile') or {}).get('columns',[]):
        dtype = column['data_type']
        kind = 'integer' if 'int' in dtype.lower() else 'number' if 'float' in dtype.lower() else 'boolean' if 'bool' in dtype.lower() else 'string'
        columns.append({'name':column['name'],'dtype':kind})
    if not columns:
        import pandas as pd
        columns = [{'name':str(name),'dtype':'string'} for name in pd.read_csv(path,nrows=0,encoding=encoding).columns]
    return InputContract(columns=columns,encoding=encoding)


def analysis_snapshot(document: WorkspaceDocument, project: dict, path: Path, source: str,
                      selected: str | None = None) -> tuple[PartialRevision,str,str]:
    data = document.model_dump()
    data['input_contract'] = (document.input_contract or inferred_contract(project,path)).model_dump()
    cleanups = [step for step in document.steps if step.stage=='cleanup']
    owners = {name:step for step in cleanups for name in step.outputs}
    if source in {'auto','cleaned'}:
        candidates = set(owners)-{name for step in cleanups for name in step.inputs}
        selected_step = next((s for s in document.steps if 'step:'+s.id==selected),None)
        if selected_step:
            preferred = [name for name in selected_step.outputs if name in owners] or [name for name in selected_step.inputs if name in owners]
            if len(preferred)==1: candidates = set(preferred)
        if len(candidates)>1:
            raise NeedsClarification([Question(question='Which cleaned dataset should this analysis use?',
                reason='The project has several independent cleaning outputs. Choose one or enter another exact output name.',choices=sorted(candidates)[:6])],phase='dataset')
        source = next(iter(candidates)) if candidates else 'data'
        if cleanups and source=='data': raise ValueError('Cleaning has no available terminal output')
    if source=='raw': source='data'
    if source!='data' and source not in owners:
        raise NeedsClarification([Question(question='The requested data source is unavailable. Which source should be used?',choices=['raw',*sorted(owners)[:5]])],phase='dataset')
    needed: set[str] = set()
    pending = [source]
    while pending:
        name = pending.pop()
        if name in owners and owners[name].id not in needed:
            step = owners[name]; needed.add(step.id); pending.extend(step.inputs)
    data['steps'] = [s.model_dump() for s in cleanups if s.id in needed]
    data['dashboard']['widgets'] = []
    available = {'data',*(name for s in cleanups if s.id in needed for name in s.outputs)}
    for parameter in data['parameters']:
        if parameter.get('filter_column') and parameter['filter_artifact'] not in available:
            if parameter['default'] is not None:
                raise NeedsClarification([Question(question=f"How should the {parameter['label']} filter apply to this data source?",
                    reason='Its saved filter source is not available for the selected data.')])
            parameter['filter_column'] = None
    return PartialRevision.model_validate({k:v for k,v in data.items() if k!='input_enabled'}),source,('raw' if source=='data' else 'draft cleaning: '+source)


class TemporaryAnalysis:
    def __init__(self, service: Any):
        self.service = service
        self.store = service.store
        self.runner = AgentRunner()

    async def execute(self, project_id: str, plan: AnalysisPlan, turn: dict, cancel: threading.Event) -> dict:
        project = self.store.get(project_id)
        from backend.services.workspace_service import Workspaces, WorkspaceConflict
        workspace = Workspaces(self.store).get(project_id)
        if workspace['version']!=turn['workspace_version'] or project['dataset_hash']!=turn['input_hash']:
            raise WorkspaceConflict('The input or workspace changed. Ask the question again.')
        document = WorkspaceDocument.model_validate(workspace['document'])
        snapshot,source,label = analysis_snapshot(document,project,self.store.dataset_path(project_id),
            'raw' if turn.get('raw_approved') else plan.source,turn['context']['stage_id'])
        output_name = 'chat_result_'+uuid4().hex[:12]
        if plan.kind=='query':
            operations = json.dumps([op.model_dump() for op in plan.operations])
            body = "from pipeline_core.analysis_tools import query_frame\nimport json\ndef analyze(inputs, parameters, context):\n    return {'result': query_frame(inputs['data'], json.loads("+repr(operations)+"))}\n"
        else:
            body = plan.code
        validate_generated_source(body,'analyze')
        parameters = validate_parameters(snapshot,{})
        state = AgentStore(self.store)
        rules_version = state.rules_version(project_id)
        if turn.get('rules_version',rules_version)!=rules_version:
            raise WorkspaceConflict('Project rules changed during analysis. Ask the question again.')
        runtime_root = Path(__file__).resolve().parents[2]/'pipeline_core'
        runtime_identity = {'packages':installed_versions(),'source':{path.name:fingerprint(path) for path in sorted(runtime_root.glob('*.py'))}}
        analysis_key = hashlib.sha256(json.dumps({'input_hash':turn['input_hash'],'runtime':runtime_identity,
            'calculation':calculation_hash(snapshot.model_dump()),'source':source,'parameters':parameters,
            'plan':plan.model_dump(exclude={'message','questions'}),'rules_version':rules_version},sort_keys=True).encode()).hexdigest()
        cached = state.cached_artifact(project_id,analysis_key)
        if cached:
            turn.update(analysis_plan=plan.model_dump(),artifact_id=cached['id'])
            return {**cached,'cache_hit':True}
        wrapper = body+f"\ndef chat_calculate(inputs, parameters, context):\n    produced = analyze({{'data': inputs[{source!r}]}}, parameters, context)\n    if not isinstance(produced, dict) or set(produced) != {{'result'}}:\n        raise ValueError('Temporary analysis must return exactly result')\n    return {{{output_name!r}: produced['result']}}\n"
        step = PipelineStep(id=output_name,title='Temporary analysis',stage='analysis',function='chat_calculate',
            code=wrapper,inputs=[source],outputs=[output_name])
        snapshot = PartialRevision.model_validate({**snapshot.model_dump(),'steps':[*[s.model_dump() for s in snapshot.steps],step.model_dump()]})
        directory = self.store.project_dir(project_id)/'analysis'/str(uuid4())
        async with self.service.lock:
            response = await self.runner.run(snapshot,self.store.dataset_path(project_id),parameters,directory,cancel)
        if not response['success']:
            error = response.get('error','Temporary analysis failed')
            # Keep the exact failure for the repair writer, without exposing source in normal UI.
            turn['analysis_failure'] = {'plan':plan.model_dump(),'error':error,'traceback':response.get('traceback','')[-8000:]}
            shutil.rmtree(directory,ignore_errors=True)
            last_step = next((event.get('step_id') for event in reversed(response.get('execution_events',[])) if event.get('event')=='step'),None)
            if snapshot.steps[:-1] and last_step != output_name:
                raise NeedsClarification([Question(question='The current cleaning could not run. How should this question continue?',
                    reason=error[:1500],choices=['Repair the cleaning stages','Use raw data for this request','Cancel'])],error,phase='source')
            raise ValueError(error)
        current = Workspaces(self.store).get(project_id)
        if cancel.is_set(): raise ValueError('Chat cancelled')
        if (current['version']!=turn['workspace_version'] or self.store.get(project_id)['dataset_hash']!=turn['input_hash']
                or response['result']['input_hash']!=turn['input_hash'] or state.rules_version(project_id)!=rules_version):
            raise WorkspaceConflict('The workspace or CSV changed during calculation. Ask the question again.')
        output = directory/'output'
        cache = json.loads((output/'cache.json').read_text())
        record = cache[step.id]['outputs'][output_name]
        value_path = output/record['file']
        if value_path.name!=record['file'] or value_path.is_symlink() or fingerprint(value_path)!=record['sha256']: raise ValueError('Invalid temporary output')
        value = PipelineEngine._load(value_path,record['kind'])
        import pandas as pd
        if isinstance(value,pd.DataFrame):
            result: dict[str,Any] = {'kind':'table','columns':list(value.columns[:20]),
                'rows':safe_json(value.iloc[:100,:20].to_dict('records')),'total_rows':len(value),'csv_file':output_name+'.csv'}
            if plan.chart_kind!='none':
                result['chart'] = chart_from_frame(value,ChartBinding(kind=plan.chart_kind,x=plan.chart_x,y=plan.chart_y))
                validate_chart(result['chart']['option'])
        elif isinstance(value,dict) and 'option' in value:
            validate_chart(value['option']); result = {'kind':'chart','chart':value}
        elif value is None or isinstance(value,(str,int,float,bool)):
            result = {'kind':'text' if isinstance(value,str) else 'metric','value':safe_json(value)}
        else: raise ValueError('Return a scalar, text, DataFrame or ECharts option object')
        # Keep result files only; cleanup checkpoints are disposable worker data.
        retained = {record['file'],result.get('csv_file')}
        for path in output.iterdir():
            if path.is_file() and path.name not in retained: path.unlink()
        provenance = {'turn_id':turn['id'],'input_hash':turn['input_hash'],'dataset_name':project['dataset_name'],
            'workspace_version':workspace['version'],'calculation_hash':calculation_hash(document.model_dump()),
            'parameters':parameters,'source':label,'rules_version':rules_version,'analysis_key':analysis_key,
            'runtime_packages':runtime_identity['packages']}
        artifact = AgentStore(self.store).add_artifact(project_id,output,result,provenance)
        turn['analysis_plan'] = plan.model_dump()
        turn['artifact_id'] = artifact['id']
        return artifact
