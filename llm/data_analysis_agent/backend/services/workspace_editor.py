"""Translate stable-ID edit plans into candidate workspace documents."""
import ast
import json
from typing import Any
from backend.services.agent_calls import structured
from backend.services.agent_contracts import EditPlan, StepSource, Question
from backend.services import agent_prompts as prompts
from pipeline_core.workspace import WorkspaceDocument
from pipeline_core.models import InputContract, ParameterSpec, PipelineStep, Widget


class NeedsClarification(ValueError):
    def __init__(self, questions: list[Question], message: str = 'Please clarify the analysis.', phase: str | None = None):
        super().__init__(message)
        self.questions = questions
        self.phase = phase


def validate_generated_source(code: str, function: str) -> None:
    from pipeline_core.validation import validate_source
    validate_source(code,function)
    allowed = {'pandas','numpy','scipy','statsmodels','math','datetime','re','statistics','collections',
        'itertools','functools','decimal','typing','json','pipeline_core.statistics','pipeline_core.analysis_tools'}
    forbidden = {'open','exec','eval','compile','__import__','getattr','setattr','delattr','globals','locals','vars',
        'read_csv','read_json','read_pickle','read_excel','to_pickle','to_csv','to_json','save','load','system','popen'}
    for node in ast.walk(ast.parse(code)):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            modules = [n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or '']
            if any(not any(m == a or m.startswith(a+'.') for a in allowed) for m in modules):
                raise ValueError('Generated source imports an unsupported module')
            if isinstance(node,ast.ImportFrom) and node.level: raise ValueError('Relative imports are not supported')
        if isinstance(node,ast.Attribute) and node.attr.startswith('__'): raise ValueError('Reflection is not supported')
        if isinstance(node,ast.Call):
            name = node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            if name in forbidden: raise ValueError('Generated calculations must use supplied inputs, not '+name)


async def edit_workspace(gateway: Any, project: dict, current: WorkspaceDocument, request: str,
                         chat_context: dict, history: list[dict], diagnostics: dict,
                         failed: dict | None, error: str | None, details: dict) -> WorkspaceDocument:
    base = {k:v for k,v in (failed or current.model_dump()).items() if k in WorkspaceDocument.model_fields}
    scope = chat_context.get('stage_id') or ''
    prompt = prompts.INPUT if scope in {'input:data','category:input'} else prompts.VISUALIZATION if scope.startswith(('widget:','category:visualization')) else prompts.EDIT
    planning_document = json.loads(json.dumps(base))
    for step in planning_document['steps']:
        if 'code' in step and scope != 'step:'+step['id'] and not (error and step['id'] in error):
            step['code']='[Source retained. The step writer receives the complete source if this step needs an edit.]'
    step_shape = PipelineStep.model_json_schema()
    step_shape['properties'].pop('code',None)
    step_shape['required'] = [name for name in step_shape.get('required',[]) if name!='code']
    evidence = {'request':request,'selected_context':chat_context,'workspace':planning_document,
        'supported_entity_schemas':{'input_contract':InputContract.model_json_schema(),'step':step_shape,
            'control':ParameterSpec.model_json_schema(),'widget':Widget.model_json_schema()},
        'profile':project.get('profile'),'description':project.get('description'),
        'confirmed_rules':project.get('analysis_rules',[]),'confirmed_answers':project.get('confirmed_answers',[]),
        'recent_conversation':history[-6:],'run_diagnostics':diagnostics,'validation_error':error,
        'repairing_candidate':bool(failed),'repair_instruction':'The workspace is the exact partial candidate from the last attempt. Existing IDs must use update, not add. Keep successful source. Use unset_fields to remove invalid fields; do not recreate the plan from the original workspace.' if failed else ''}
    plan = await structured(gateway,prompt,evidence,EditPlan,'edit_plan',8192)
    if plan.questions: raise NeedsClarification(plan.questions,plan.summary)
    document = json.loads(json.dumps(base))
    details['candidate'] = document
    reasons: dict[str,str] = {}
    writes: dict[str,str] = {}
    for operation in plan.operations:
        fields = json.loads(operation.fields_json)
        if not isinstance(fields,dict): raise ValueError('Operation fields_json must encode an object')
        identifier = operation.target_id.removeprefix({'step':'step:','widget':'widget:','control':'control:'}.get(operation.kind,'\0'))
        if 'code' in fields:
            existing = next((step for step in document['steps'] if step['id']==identifier),None)
            if operation.kind=='step' and existing and fields['code']==existing.get('code'):
                fields.pop('code')
            else:
                raise ValueError('Exclude code from fields_json. Use code_request to ask the separate step writer for a source change.')
        if operation.kind in {'input','project','dashboard'}:
            allowed = {'input':{'input_contract','input_enabled'},'project':{'title','seed','dependencies'},'dashboard':{'title','subtitle'}}[operation.kind]
            if not set(fields)<=allowed or operation.op=='remove': raise ValueError('Invalid settings operation: '+operation.kind+' fields must be '+', '.join(sorted(allowed)))
            target = document['dashboard'] if operation.kind=='dashboard' else document
            target.update(fields)
            key = {'input':'input:data','project':'project:settings','dashboard':'dashboard:settings'}[operation.kind]
        else:
            collection = document['dashboard']['widgets'] if operation.kind=='widget' else document['parameters'] if operation.kind=='control' else document['steps']
            found = next((i for i,item in enumerate(collection) if item['id']==identifier),None)
            if operation.op=='remove':
                if found is None: raise ValueError('Cannot remove a missing '+operation.kind)
                collection.pop(found)
                if operation.kind=='step': writes.pop(identifier,None)
            else:
                if operation.op=='add' and found is not None: raise ValueError('Identifier already exists: '+identifier)
                if operation.op=='update' and found is None: raise ValueError('Identifier does not exist: '+identifier)
                if fields.get('id',identifier)!=identifier: raise ValueError('An operation cannot change identity')
                item = {**(collection[found] if found is not None else {}),**fields,'id':identifier}
                if 'id' in operation.unset_fields: raise ValueError('An operation cannot remove identity')
                for field in operation.unset_fields: item.pop(field,None)
                if operation.kind=='step':
                    if operation.code_request: writes[identifier]=operation.code_request
                    elif 'code' not in item and identifier not in writes: raise ValueError('New steps require a code_request')
                if found is None: collection.append(item)
                else: collection[found] = item
            key = {'step':'step:','widget':'widget:','control':'control:'}[operation.kind]+identifier
        if operation.linked_reason: reasons[key] = operation.linked_reason
    # Complete the graph and bindings first. Writers need the actual output kinds,
    # parameter IDs and upstream source, including metadata added later in the plan.
    for item in document['steps']:
        if item['id'] in writes:
            source = await structured(gateway,prompts.REPAIR if error else prompts.CODE,
                {'instruction':writes[item['id']],'original_request':request,'step':item,
                 'output_bindings':[widget for widget in document['dashboard']['widgets'] if widget.get('output') in item.get('outputs',[])],
                 'parameter_specs':document['parameters'],'profile':project.get('profile'),'input_contract':document['input_contract'],
                 'upstream_steps':[{k:v for k,v in upstream.items() if k!='code' or set(upstream.get('outputs',[])) & set(item.get('inputs',[]))}
                     for upstream in document['steps']],
                 'validation_error':error,'run_diagnostics':diagnostics,'confirmed_answers':project.get('confirmed_answers',[]),
                 'rules':project.get('analysis_rules',[])},StepSource,'repair_step' if error else 'write_step',16384)
            item['code'] = source.code
        try:
            validate_generated_source(item['code'],item['function'])
        except (ValueError,SyntaxError,KeyError) as exc:
            from backend.services.project_agent import ProposalValidationError
            raise ProposalValidationError(str(exc),document) from exc
    document['summary'] = plan.summary
    details['linked_reasons'] = reasons
    try:
        return WorkspaceDocument.model_validate(document)
    except ValueError as exc:
        from backend.services.project_agent import ProposalValidationError
        raise ProposalValidationError(str(exc),document) from exc
