"""Application-owned chat workflow. Models select tasks, never permissions."""
from __future__ import annotations
import asyncio
import json
import threading
import time
from typing import Any, Callable, cast
from uuid import uuid4
from backend.services.agent_calls import CallBudget, budget, structured
from backend.services.agent_contracts import AnalysisPlan, Answer, Question, Route
from backend.services import agent_prompts as prompts
from backend.services.agent_store import AgentStore, TERMINAL
from backend.services.chat_agent import reply
from backend.services.chat_store import ChatStore, context_for, public_item
from backend.services.run_diagnostics import collect_run_diagnostics
from backend.services.temporary_analysis import TemporaryAnalysis
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from backend.services.workspace_editor import NeedsClarification
from pipeline_core.workspace import calculation_hash
from config import config
from pipeline_core.models import now


class AgentController:
    def __init__(self, service: Any):
        self.service, self.store = service, service.store
        self.items, self.state = ChatStore(self.store), AgentStore(self.store)

    async def respond(self, project_id: str, query: str, stage_id: str | None, expected_version: int | None,
                      emit: Callable[[dict],None], cancel: threading.Event, *, answer_only: bool=False,
                      run_id: str | None=None, captured_context: dict | None=None,
                      request_id: str | None=None, page_context: str | None=None,
                      proposal_id: str | None=None, resume_turn: str | None=None) -> dict:
        workspace = Workspaces(self.store).get(project_id)
        project = self.store.get(project_id)
        if expected_version is not None and workspace['version']!=expected_version:
            raise WorkspaceConflict('The workspace changed. Reload before sending this request.')
        if resume_turn:
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT record FROM agent_turns WHERE id=? AND project_id=?',(resume_turn,project_id)).fetchone()
                if row is None: raise KeyError('Chat request not found')
                turn = json.loads(row['record'])
                if turn['status']!='queued': return {'kind':'turn','turn_id':turn['id'],'status':turn['status']}
                turn['status']='routing'
                db.execute('UPDATE agent_turns SET record=? WHERE id=?',(json.dumps(turn),turn['id']))
        else:
            context = captured_context or context_for(workspace['document'],stage_id,bool(project['dataset_hash']))
            turn,created = self.state.create(project_id,query,context,workspace,project['dataset_hash'],request_id,page_context,proposal_id)
            if not created:
                for event in self.state.events(project_id,turn['id']): emit(event)
                return cast(dict, turn.get('result',{'kind':'turn','turn_id':turn['id'],'status':turn['status']}))
            turn.update(answer_only=answer_only,run_id=run_id,rules_version=self.state.rules_version(project_id))
            self.state.put(turn)
            if not answer_only:
                self.store.message(project_id,'user',query,{'context':context,'workspace_version':workspace['version'],'turn_id':turn['id']})
        return await self._drive(turn,emit,cancel)

    def _evidence(self, turn: dict) -> dict:
        from backend.services.chat_service import results_preview, redact
        pid = turn['project_id']
        project,workspace = self.store.get(pid),Workspaces(self.store).get(pid)
        partial = self.store.partial_run(pid)
        run_id = turn.get('run_id')
        if not run_id and partial and partial.workspace_version==workspace['version'] and partial.input_hash==project['dataset_hash']:
            run_id = partial.run_id
        run_id = run_id or project['display_run_id']
        run = self.store.run(pid,run_id).model_dump() if run_id else None
        compatible = False
        if run and run['status']=='succeeded' and run['input_hash']==project['dataset_hash']:
            if run.get('validation_mode')=='partial': compatible = run.get('workspace_version')==workspace['version']
            else:
                revision = self.store.revision(pid,run['revision_id'])
                compatible = (calculation_hash(revision)==calculation_hash(workspace['document'])
                    and run['parameters']=={p['id']:p['default'] for p in workspace['document']['parameters']})
        # Historical evidence is usable only for a user-selected run or the bounded Run follow-up.
        preview = results_preview(run,self.store,pid) if compatible or turn.get('answer_only') or (run_id and run_id in turn['query']) else {}
        document = json.loads(json.dumps(workspace['document']))
        selected = turn['context']['stage_id'] or ''
        relevant = {selected.removeprefix('step:')}
        query_lower = turn['query'].lower()
        for step in document['steps']:
            if step['id'] in relevant or step['title'].lower() in query_lower or step['id'].lower() in query_lower:
                relevant.add(step['id'])
                relevant.update(s['id'] for s in document['steps'] if set(s['outputs']) & set(step['inputs']))
        for step in document['steps']:
            if len(document['steps'])>6 and step['id'] not in relevant:
                step['code']='[Source omitted; select this stage to inspect its complete calculation.]'
        history = [{**m,'content':m['content'][:3000]} for m in self.store.messages(pid)[-8:]]
        recent_analyses = []
        for message in history:
            identifier = message.get('metadata',{}).get('artifact_id')
            if identifier:
                try:
                    artifact = self.state.artifact(pid,identifier)
                    recent_analyses.append({k:artifact[k] for k in ['id','result','provenance','expired']})
                except KeyError: pass
        pending = [{k:item.get(k) for k in ['id','message','context','stale']} for item in self.items.list(pid)
            if item['kind']=='proposal' and item['status']=='pending'][-3:]
        result = {'request':turn['query'],'selected_context':turn['context'],'page_context':turn.get('page_context'),
            'answer_only':turn.get('answer_only',False),'workspace':{**workspace,'document':document},
            'description':project['description'],'profile':project['profile'],'builder_input_hash':project['dataset_hash'],
            'saved_results':preview,'saved_results_current':compatible,'recent_conversation':history,
            'recent_analyses':recent_analyses,'pending_proposals':pending,'confirmed_answers':turn['answers'],
            'project_rules':[r for r in self.state.rules(pid) if not r['needs_review']]}
        if any(word in query_lower for word in ['error','repair','fail','traceback','fix']):
            result['run_diagnostics'] = collect_run_diagnostics(self.store,pid,turn['query'],config.openai_api_key)
        # Bound context without cutting source or producing invalid JSON.
        if len(json.dumps(result,default=str))>96000:
            result['recent_conversation']=history[-3:];result['recent_analyses']=recent_analyses[-1:]
            result['context_truncated']=True
            for step in document['steps']:
                if step['id'] not in relevant: step['code']='[Source omitted]'
        return cast(dict, redact(result))

    def _ask(self, turn: dict, questions: list[Question], message: str, emit: Callable[[dict],None], phase: str) -> dict:
        if turn['clarification_rounds']>=3: raise ValueError('The request needs more information. Narrow it and start a new request.')
        turn['clarification_rounds']+=1
        if not questions: questions=[Question(question=message)]
        values = [{**q.model_dump(),'id':str(uuid4())} for q in questions[:3]]
        if any('Use Project scope' in q['choices'] for q in values): phase='scope'
        elif any('Use raw data for this request' in q['choices'] for q in values): phase='source'
        item = self.items.create(turn['project_id'],'clarification',turn['query'],turn['context'],turn['workspace_version'],
            turn['input_hash'],message=message,turn_id=turn['id'],questions=values,phase=phase)
        turn.update(status='awaiting_clarification',clarification_id=item['id'],resume_phase=phase)
        self.state.put(turn)
        self.store.message(turn['project_id'],'assistant',message,{'kind':'clarification','context':turn['context'],'item_id':item['id'],'turn_id':turn['id']})
        emit({'event':'clarification','item':public_item(item)})
        return {'kind':'clarification','id':item['id'],'message':message}

    async def _analysis(self, turn: dict, evidence: dict, emit: Callable[[dict],None], cancel: threading.Event) -> dict | None:
        if turn.get('artifact_id'):
            return self.state.artifact(turn['project_id'],turn['artifact_id'])
        error = ''
        for attempt in range(config.agent_max_repairs+1):
            turn['status']='analyzing';self.state.put(turn)
            emit({'event':'status','message':'Planning temporary analysis' if not attempt else 'Repairing the temporary calculation'})
            context = {**evidence,'failed_analysis':turn.get('analysis_failure'),'validation_error':error,
                'source_override':turn.get('selected_source') or ('raw' if turn.get('raw_approved') else None)}
            plan = await structured(self.service.agent.llm,prompts.ANALYST,context,AnalysisPlan,'temporary_analysis',16384)
            if plan.questions or plan.kind=='clarification':
                self._ask(turn,plan.questions,plan.message,emit,'analysis');return None
            if turn.get('selected_source'): plan.source=turn['selected_source']
            turn['analysis_plan']=plan.model_dump()
            try:
                turn['status']='executing';self.state.put(turn)
                emit({'event':'status','message':'Calculating against the full selected dataset in isolation'})
                artifact = await TemporaryAnalysis(self.service).execute(turn['project_id'],plan,turn,cancel)
                emit({'event':'artifact','artifact':{k:artifact[k] for k in ['id','result','provenance','expired']}})
                return artifact
            except NeedsClarification as exc:
                self._ask(turn,exc.questions,str(exc),emit,exc.phase or 'analysis');return None
            except (ValueError, SyntaxError, KeyError, TypeError) as exc:
                if cancel.is_set(): raise
                error=str(exc)
                turn['analysis_failure']={**turn.get('analysis_failure',{}),'plan':plan.model_dump(),'error':error}
                if 'Automatic Python is unavailable' in error or 'deadline' in error: raise
        raise ValueError('Temporary analysis failed after bounded repairs: '+error)

    async def _drive(self, turn: dict, emit_callback: Callable[[dict],None], cancel: threading.Event) -> dict:
        pid=turn['project_id']
        self.service.chat_cancellations[turn['id']]=cancel
        task=asyncio.current_task()
        if task: self.service.chat_tasks[turn['id']]=task
        def emit(event: dict) -> None:
            emit_callback(self.state.event(turn,event))
        def trace(value: dict) -> None:
            turn['trace']=[*turn['trace'],value][-30:]
            turn['model_steps']+=1
            self.state.put(turn)
        elapsed=turn.get('active_seconds',0)
        start=time.monotonic()
        state=CallBudget(count=turn.get('model_steps',0),deadline=start+max(.01,config.agent_turn_timeout_seconds-elapsed),cancelled=cancel.is_set,observe=trace)
        token=budget.set(state)
        try:
            emit({'event':'turn_started','turn_id':turn['id']})
            project,workspace=self.store.get(pid),Workspaces(self.store).get(pid)
            if workspace['version']!=turn['workspace_version'] or project['dataset_hash']!=turn['input_hash']:
                raise WorkspaceConflict('The workspace or input changed. Recheck the request with the current data.')
            if self.state.rules_version(pid)!=turn.get('rules_version',self.state.rules_version(pid)):
                raise WorkspaceConflict('Project rules changed. Start a new request to use the current rules.')
            turn['status']='routing';self.state.put(turn)
            evidence=await asyncio.to_thread(self._evidence,turn)
            emit({'event':'status','message':'Reading the selected context' if turn['context']['stage_id'] else 'Reading the project'})
            if turn.get('route') and turn.get('resume_phase')!='routing': decision=Route.model_validate(turn['route'])
            else: decision=await reply(self.service.agent.llm,evidence)
            if turn.get('intent_override'): decision.kind=turn['intent_override']
            turn['route']=decision.model_dump()
            if decision.proposal_id and not turn.get('proposal_id'): turn['proposal_id']=decision.proposal_id
            if turn.get('scope_approved'):
                turn['context']={'stage_id':None,'label':'Project'}
                evidence['selected_context']=turn['context']
            if (decision.kind in {'proposal','mixed'} and decision.requested_scope=='project' and turn['context']['stage_id']
                    and not turn.get('keep_scope')):
                return self._ask(turn,[Question(question='May this request use Project edit scope?',
                    reason='Your request covers more than the selected stage.',choices=['Use Project scope','Keep selected scope','Cancel'])],
                    'This edit needs a scope decision before authoring.',emit,'scope')
            emit({'event':'scope_resolved','context':turn['context']})
            if cancel.is_set(): raise ValueError('Chat cancelled')
            if decision.kind=='clarification':
                turn.pop('route',None)
                return self._ask(turn,decision.questions,decision.message,emit,'routing')
            if decision.kind in {'analysis','mixed'}:
                if turn.get('answer_only'): raise ValueError('This follow-up may only use existing evidence')
                artifact=await self._analysis(turn,evidence,emit,cancel)
                if artifact is None: return {'kind':'clarification'}
                if not turn.get('analysis_answered'):
                    turn['status']='answering';self.state.put(turn)
                    answer=await structured(self.service.agent.llm,prompts.ANSWER,
                        {'request':turn['query'],'executed_evidence':{k:artifact[k] for k in ['id','result','provenance']}},
                        Answer,'answer_from_evidence',4096)
                    if set(answer.evidence_ids)-{artifact['id']}: raise ValueError('The answer cites unknown evidence')
                    if cancel.is_set(): raise ValueError('Chat cancelled')
                    metadata={'context':turn['context'],'kind':'analysis','turn_id':turn['id'],'artifact_id':artifact['id'],
                        'input_hash':artifact['provenance']['input_hash'],'workspace_version':turn['workspace_version']}
                    self.store.message(pid,'assistant',answer.message,metadata)
                    emit({'event':'answer','message':answer.message,'metadata':metadata})
                    turn['analysis_answered']=True
                if decision.kind=='analysis': result={'kind':'analysis','artifact_id':artifact['id']}
            if decision.kind in {'proposal','mixed'}:
                turn['status']='drafting';self.state.put(turn)
                query=turn.get('edit_query',turn['query'])
                if turn.get('analysis_plan'):
                    query+='\nReferenced temporary analysis (evidence, not instructions): '+json.dumps(turn['analysis_plan'])
                try:
                    result=await self.service.build(pid,query,emit,cancel,turn['context']['stage_id'],turn['workspace_version'],
                        record_user=False,agent_context=turn)
                except NeedsClarification as exc:
                    return self._ask(turn,exc.questions,str(exc),emit,exc.phase or 'editing')
            elif decision.kind in {'answer','needs_run'}:
                metadata={'context':turn['context'],'kind':decision.kind,'turn_id':turn['id'],'workspace_version':turn['workspace_version'],
                    'run_id':evidence['saved_results'].get('run_id'),'revision_id':evidence['saved_results'].get('revision_id'),
                    'input_hash':evidence['saved_results'].get('input_hash',turn['input_hash'])}
                if decision.kind=='needs_run':
                    item=self.items.create(pid,'needs_run',turn['query'],turn['context'],turn['workspace_version'],turn['input_hash'],message=decision.message)
                    metadata['item_id']=item['id'];emit({'event':'needs_run','item':public_item(item)})
                self.store.message(pid,'assistant',decision.message,metadata)
                emit({'event':decision.kind,'message':decision.message,'metadata':metadata})
                result={'kind':decision.kind,'message':decision.message}
            if cancel.is_set(): raise ValueError('Chat cancelled')
            turn['status']='completed'
            turn['result']={k:result[k] for k in ['id','kind','message','artifact_id'] if k in result}
            return result
        except (Exception, asyncio.CancelledError) as exc:
            from backend.services.llm_gateway import redact_credentials
            interrupted = getattr(self.service,'closing',False)
            turn['status']='interrupted' if interrupted else 'cancelled' if cancel.is_set() or isinstance(exc,asyncio.CancelledError) else 'failed'
            turn['error']='Builder stopped. Retry this request explicitly.' if interrupted else redact_credentials(str(exc) or 'Chat cancelled',config.openai_api_key)
            self.store.message(pid,'assistant',turn['error'],{'kind':'error','context':turn['context'],'turn_id':turn['id']})
            emit({'event':'error','message':turn['error'],'kind':getattr(exc,'kind','agent')})
            raise
        finally:
            turn['active_seconds']=elapsed+time.monotonic()-start
            self.state.put(turn)
            emit({'event':'turn_state','status':turn['status']})
            budget.reset(token)
            self.service.chat_cancellations.pop(turn['id'],None)
            self.service.chat_tasks.pop(turn['id'],None)

    def answer_questions(self, project_id: str, item_id: str, answers: list[dict], refresh_context: bool=False) -> dict:
        workspace=Workspaces(self.store).get(project_id)
        project=self.store.get(project_id)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT record FROM chat_items WHERE id=? AND project_id=?',(item_id,project_id)).fetchone()
            if not row: raise KeyError('Question card not found')
            item=json.loads(row['record'])
            if item['kind']!='clarification': raise ValueError('This item is not a question card')
            turn=self.state.get(project_id,item['turn_id'])
            if item['status']=='answered': return turn
            if item['status']!='pending' or turn['status']!='awaiting_clarification': raise WorkspaceConflict('This question is no longer pending')
            if (workspace['version']!=turn['workspace_version'] or project['dataset_hash']!=turn['input_hash']) and not refresh_context:
                raise WorkspaceConflict('The workspace or input changed. Recheck with current data before answering.')
            question_ids={q['id'] for q in item['questions']}
            if len(answers)!=len(question_ids) or {a.get('question_id') for a in answers}!=question_ids:
                raise ValueError('Answer every question exactly once')
            saved=[]
            for question in item['questions']:
                answer=next(a for a in answers if a['question_id']==question['id'])
                text=str(answer.get('text','')).strip()
                if not text or len(text)>4000: raise ValueError('Each answer needs 1–4000 characters')
                if answer.get('save_as_rule') and not question['saveable']: raise ValueError('This question cannot become a project rule')
                saved.append({'question':question['question'],'answer':text})
                if text=='Cancel': turn['status']='cancelled'
                if item['phase']=='scope':
                    if text=='Use Project scope': turn['scope_approved']=True
                    elif text=='Keep selected scope': turn['keep_scope']=True;turn.pop('candidate',None)
                    elif text!='Cancel': raise ValueError('Choose a scope option')
                elif item['phase']=='source':
                    if text=='Use raw data for this request': turn['raw_approved']=True
                    elif text=='Repair the cleaning stages':
                        turn.update(intent_override='proposal',edit_query='Repair the current cleaning failure without changing business rules. '+turn['query'])
                elif item['phase']=='dataset':
                    sources = {'raw','data',*(name for step in workspace['document']['steps'] if step['stage']=='cleanup' for name in step['outputs'])}
                    if text not in sources: raise ValueError('Choose or enter an exact available data output name')
                    turn['selected_source']=text
            item['status']='answered';item['answers']=saved
            turn['answers'].extend(saved)
            if refresh_context:
                turn.update(workspace_version=workspace['version'],input_hash=project['dataset_hash'])
                for key in ['candidate','artifact_id','route']: turn.pop(key,None)
                turn['resume_phase']='routing'
            if turn['status']!='cancelled': turn['status']='queued'
            turn['updated_at']=now()
            db.execute('UPDATE chat_items SET record=? WHERE id=?',(json.dumps(item),item_id))
            db.execute('UPDATE agent_turns SET record=? WHERE id=?',(json.dumps(turn),turn['id']))
        for question in item['questions']:
            answer=next(a for a in answers if a['question_id']==question['id'])
            if answer.get('save_as_rule'):
                self.state.save_rule(project_id,question['question']+' '+str(answer['text']))
        turn['rules_version']=self.state.rules_version(project_id);self.state.put(turn)
        self.store.message(project_id,'user','\n'.join(a['question']+' '+a['answer'] for a in saved),
            {'kind':'clarification_answer','context':turn['context'],'turn_id':turn['id']})
        return turn

    def cancel(self, project_id: str, turn_id: str) -> dict:
        turn=self.state.get(project_id,turn_id)
        if turn['status'] not in TERMINAL:
            turn['status']='cancelled';self.state.put(turn)
            flag=self.service.chat_cancellations.get(turn_id)
            if flag: flag.set()
            task=self.service.chat_tasks.get(turn_id)
            if task: task.cancel()
            if turn.get('clarification_id'):
                item=self.items.get(project_id,turn['clarification_id'])
                if item['status']=='pending': item['status']='discarded';self.items.put(project_id,item)
            self.state.event(turn,{'event':'turn_state','status':'cancelled'})
        return turn
