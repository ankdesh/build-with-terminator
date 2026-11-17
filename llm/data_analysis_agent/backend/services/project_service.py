"""Build, execute, validate, accept, and refine persistent analysis projects."""

import asyncio
import json
import threading
import shutil
from pathlib import Path
from typing import Any, Callable

from backend.services.project_agent import ProjectAgent, ProposalValidationError, ModelUnavailableError
from backend.services.chat_store import ChatStore, context_for, review_changes, public_item
from backend.services.project_store import ProjectStore
from backend.services.run_diagnostics import collect_run_diagnostics
from config import config
from pipeline_core.engine import fingerprint
from pipeline_core.models import ProjectRevision, RunRecord, DashboardSpec, now
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.validation import validate_parameters
from backend.services.workspace_service import Workspaces
from pipeline_core.workspace import WorkspaceDocument
from backend.services.llm_gateway import LLMGateway
from backend.services.agent_runner import AgentRunner
from backend.services.workspace_editor import edit_workspace, NeedsClarification
from backend.services.agent_contracts import Question


class ProjectService:
    def __init__(self, store: ProjectStore, agent: ProjectAgent | None = None, runner: ProcessRunner | None = None) -> None:
        self.store = store
        self.agent = agent or ProjectAgent()
        self.runner = runner or ProcessRunner()
        self.lock = asyncio.Lock()
        self.authoring_locks: dict[str, asyncio.Lock] = {}
        self.cancellations: dict[str, threading.Event] = {}
        self.validation_runner = AgentRunner()
        self.chat_tasks: dict[str, asyncio.Task] = {}
        self.chat_cancellations: dict[str, threading.Event] = {}
        self.closing = False

    async def validate_candidate(self, revision: Any, source: Path, parameters: dict,
                                 directory: Path, cancel: threading.Event) -> dict:
        try:
            return await self.validation_runner.run(revision,source,parameters,directory,cancel)
        finally:
            await asyncio.to_thread(shutil.rmtree,directory,ignore_errors=True)

    async def execute(self, project_id: str, revision: ProjectRevision, parameters: dict,
                      emit: Callable[[dict], None], cancel: threading.Event,
                      input_path: Path | None = None, dataset_name: str | None = None,
                      workspace_version: int | None = None) -> RunRecord:
        project = self.store.get(project_id)
        input_path = input_path or self.store.dataset_path(project_id)
        from pipeline_core.partial import PartialRevision
        partial = isinstance(revision, PartialRevision)
        run = RunRecord(validation_mode="partial" if partial else "execution", revision_id=revision.revision_id, dataset_name=dataset_name or project["dataset_name"],
                        input_hash=fingerprint(input_path), parameters=validate_parameters(revision, parameters),
                        workspace_version=workspace_version or Workspaces(self.store).get(project_id)["version"])
        self.store.put_run(project_id, run)
        self.cancellations[run.run_id] = cancel
        emit({"event": "run_started", "run_id": run.run_id})
        previous = project["display_run_id"]
        # Prefer the latest retained execution cache, including a partial run.
        with self.store.connect() as db:
            rows = db.execute("SELECT record FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT 100", (project_id,)).fetchall()
        for row in rows:
            candidate = json.loads(row["record"])
            directory = self.store.run_dir(project_id, candidate["run_id"]) / "output"
            if candidate["status"] == "succeeded" and (directory / "cache.json").exists():
                previous = candidate["run_id"]
                break
        cache = self.store.run_dir(project_id, previous) / "output" if previous else None
        loop = asyncio.get_running_loop()
        def relay(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(emit, event)
        try:
            emit({"event": "status", "message": "Waiting for the execution slot"})
            response: dict[str, Any]
            async with self.lock:
                if cancel.is_set():
                    response = {"success": False, "cancelled": True, "error": "Run cancelled"}
                else:
                    emit({"event": "worker_started", "message": "Running saved pipeline"})
                    response = await self.runner.run(revision, input_path, run.parameters,
                        self.store.run_dir(project_id, run.run_id), cancel, cache, relay)
            run.status = "succeeded" if response["success"] else "cancelled" if response.get("cancelled") else "failed"
            run.result = response.get("result")
            run.error = response.get("error")
            run.finished_at = now()
            self.store.put_run(project_id, run)
            emit({"event": "run", "run": run.model_dump()})
            return run
        except asyncio.CancelledError:
            cancel.set()
            run.status, run.finished_at, run.error = "cancelled", now(), "Run cancelled"
            self.store.put_run(project_id, run)
            raise
        except Exception as exc:
            run.status, run.finished_at, run.error = "failed", now(), str(exc)
            self.store.put_run(project_id, run)
            emit({"event": "run", "run": run.model_dump()})
            return run
        finally:
            self.cancellations.pop(run.run_id, None)

    async def build(self, project_id: str, query: str, emit: Callable[[dict], None], cancel: threading.Event,
                    stage_id: str | None = None, expected_version: int | None = None,
                    record_user: bool = True, agent_context: dict | None = None) -> dict:
        async with self.authoring_locks.setdefault(project_id, asyncio.Lock()):
            self.store.dataset_path(project_id)
            project = self.store.get(project_id)
            workspace = Workspaces(self.store)
            base = workspace.get(project_id)
            run_diagnostics = await asyncio.to_thread(collect_run_diagnostics, self.store, project_id,
                                                     query, config.openai_api_key)
            from backend.services.workspace_service import WorkspaceConflict
            if expected_version is not None and base['version'] != expected_version:
                raise WorkspaceConflict('The workspace changed. Reload before requesting changes.')
            chat_context = context_for(base['document'], stage_id, bool(project['dataset_hash']))
            if record_user:
                self.store.message(project_id, 'user', query, {'context': chat_context})
            document = WorkspaceDocument.model_validate(base["document"])
            agent_context = agent_context or {}
            project['confirmed_answers'] = agent_context.get('answers',[])
            from backend.services.agent_store import AgentStore
            project['analysis_rules'] = [r for r in AgentStore(self.store).rules(project_id) if not r['needs_review']]
            pending_proposal = None
            if agent_context.get('proposal_id'):
                pending_proposal = ChatStore(self.store).get(project_id,agent_context['proposal_id'])
                if pending_proposal['status']!='pending' or pending_proposal['kind']!='proposal':
                    raise ValueError('This proposal is no longer pending')
                if pending_proposal['version']!=base['version'] or pending_proposal['input_hash']!=project['dataset_hash']:
                    raise WorkspaceConflict('The proposal is stale. Request a fresh proposal.')
                document = WorkspaceDocument.model_validate(pending_proposal['document'])
            use_jobs = isinstance(self.agent.llm,LLMGateway)
            current = None
            if document.input_contract or document.steps or document.dashboard.widgets:
                # Agent context can include an incomplete graph. Only the proposal is compiled.
                context = {field: getattr(document, field) for field in ProjectRevision.model_fields if hasattr(document, field)}
                context["dashboard"] = DashboardSpec.model_construct(title=document.dashboard.title,
                    subtitle=document.dashboard.subtitle, widgets=document.dashboard.widgets)
                current = ProjectRevision.model_construct(**context,
                    revision_id=project["draft_id"] or "workspace", schema_version=2)
            error = None
            failed = agent_context.get('candidate')
            for attempt in range((config.agent_max_repairs if use_jobs else config.max_retries) + 1):
                if cancel.is_set():
                    raise ValueError("Build cancelled")
                emit({"event": "status", "message": "Preparing changes for review" if attempt == 0 else f"Repairing proposal ({attempt}/{config.agent_max_repairs if use_jobs else config.max_retries})"})
                try:
                    details: dict = {}
                    revision: ProjectRevision | WorkspaceDocument
                    try:
                        if use_jobs:
                            revision = await edit_workspace(self.agent.llm,project,document,query,chat_context,
                                self.store.messages(project_id),run_diagnostics,failed,error,details)
                        else:
                            revision = await self.agent.propose(project, current, query, self.store.messages(project_id), error, failed,
                                run_diagnostics=run_diagnostics, chat_context=chat_context, proposal_details=details)
                    except NeedsClarification:
                        raise
                    except (ProposalValidationError, ModelUnavailableError):
                        raise
                    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
                        # A malformed patch belongs to proposal repair. Preserve
                        # the complete working revision, not the patch payload.
                        error = f"Invalid model proposal: {exc}"
                        failed = details.get('candidate',failed)
                        agent_context['candidate'] = failed
                        continue
                    if cancel.is_set():
                        raise ValueError("Build cancelled")
                    proposed_document = revision if isinstance(revision, WorkspaceDocument) else WorkspaceDocument.from_revision(revision)
                    failed = proposed_document.model_dump()
                    agent_context['candidate'] = failed
                    try:
                        # Check new edits against this turn, then the complete replacement against its original scope.
                        if pending_proposal:
                            review_changes(document.model_dump(),proposed_document.model_dump(),stage_id,details.get('linked_reasons',{}))
                            details['linked_reasons'] = {**pending_proposal.get('linked_reasons',{}),**details.get('linked_reasons',{})}
                            if pending_proposal['context']['stage_id']!=stage_id and stage_id is not None:
                                raise ValueError('Unrelated edits require Project scope to refine this proposal.')
                        review = review_changes(base['document'], proposed_document.model_dump(),
                            stage_id, details.get('linked_reasons', {}))
                    except ValueError as exc:
                        if use_jobs and 'Unrelated edits' in str(exc):
                            raise NeedsClarification([Question(question='May this request use Project edit scope?',
                                reason=str(exc),choices=['Use Project scope','Keep selected scope','Cancel'])]) from exc
                        error = str(exc)
                        continue
                    if not review['changes']:
                        self.store.message(project_id, 'assistant', revision.summary or 'No changes are needed.',
                            {'context': chat_context, 'kind': 'answer'})
                        return {'kind': 'answer', 'message': revision.summary or 'No changes are needed.'}
                    validation: dict = {'status':'not_run','checks':['schema','source','scope']}
                    if use_jobs:
                        from backend.services.chat_store import validate_draft
                        try:
                            validate_draft(proposed_document)
                        except ValueError as exc:
                            error = str(exc)
                            continue
                        from pipeline_core.partial import execution_plan
                        if proposed_document.input_contract:
                            try:
                                snapshot,blocked = execution_plan(proposed_document)
                            except (ValueError,SyntaxError) as exc:
                                error = str(exc)
                                continue
                            from uuid import uuid4
                            validation_dir = self.store.project_dir(project_id)/'validation'/str(uuid4())
                            emit({'event':'status','message':'Checking the candidate against the current dataset in the worker process'})
                            async with self.lock:
                                response = await self.validate_candidate(snapshot,self.store.dataset_path(project_id),
                                    snapshot.default_parameters(),validation_dir,cancel)
                            if response['success'] and response['result']['input_hash']!=project['dataset_hash']:
                                raise WorkspaceConflict('The CSV changed before validation. Request a fresh proposal.')
                            validation = {'status':'blocked' if blocked else 'passed','checks':['schema','source','scope','execution'],
                                'blocked':blocked,'input_hash':project['dataset_hash'],'step_count':len(snapshot.steps)}
                            if not response['success']:
                                error = response.get('error','Candidate execution failed')
                                run_diagnostics['candidate_validation'] = {k:response[k] for k in ['error','traceback','stdout'] if k in response}
                                continue
                            # Check actual analysis code on an empty selection without changing the saved candidate.
                            if any(s.stage=='analysis' for s in snapshot.steps):
                                import copy
                                from pipeline_core.partial import PartialRevision
                                probe = copy.deepcopy(snapshot.model_dump())
                                cleanup_outputs = {name for step in snapshot.steps if step.stage=='cleanup' for name in step.outputs}
                                frames = {name:value for name,value in response['result']['outputs'].items() if name in cleanup_outputs and value.get('kind')=='table' and value.get('columns')}
                                source_name = next(iter(frames),None)
                                if source_name:
                                    probe['parameters'].append({'id':'agent_empty_'+uuid4().hex[:12],'label':'Validation empty selection','kind':'select',
                                        'default':'__wps_empty_'+uuid4().hex,'filter_artifact':source_name,'filter_column':frames[source_name]['columns'][0]})
                                    try:
                                        empty = PartialRevision.model_validate(probe)
                                    except ValueError as exc:
                                        error = str(exc)
                                        continue
                                    async with self.lock:
                                        empty_result = await self.validate_candidate(empty,self.store.dataset_path(project_id),
                                            empty.default_parameters(),validation_dir/'empty',cancel)
                                    if not empty_result['success']:
                                        error = 'Empty selection failed: '+empty_result.get('error','Unknown error')
                                        run_diagnostics['candidate_validation'] = {k:empty_result[k] for k in ['error','traceback'] if k in empty_result}
                                        continue
                                    validation['checks'].append('empty_selection')
                        else:
                            validation.update(status='blocked',blocked=['Define the input contract before execution checks'])
                    if cancel.is_set(): raise ValueError('Build cancelled')
                    if workspace.get(project_id)['version']!=base['version'] or self.store.get(project_id)['dataset_hash']!=project['dataset_hash']:
                        raise WorkspaceConflict('The workspace or CSV changed during validation. Request a fresh proposal.')
                    if agent_context.get('rules_version') and AgentStore(self.store).rules_version(project_id)!=agent_context['rules_version']:
                        raise WorkspaceConflict('Project rules changed. Request a fresh proposal.')
                    item = ChatStore(self.store).create(project_id, 'proposal', query, chat_context, base['version'],
                        project['dataset_hash'], revision=revision.model_dump() if isinstance(revision, ProjectRevision) else None,
                        document=proposed_document.model_dump(), issues=proposed_document.issues(), message=revision.summary,
                        validation=validation, analysis_artifact_id=agent_context.get('artifact_id'),
                        supersedes=pending_proposal['id'] if pending_proposal else None, **review)
                    if pending_proposal:
                        pending_proposal['status']='superseded'
                        ChatStore(self.store).put(project_id,pending_proposal)
                    self.store.message(project_id, 'assistant', revision.summary or 'Changes are ready for review.',
                        {'context': chat_context, 'kind': 'proposal', 'item_id': item['id']})
                    emit({'event': 'proposal', 'item': public_item(item)})
                    return item
                except ProposalValidationError as exc:
                    failed, error = exc.proposal, str(exc)
                    agent_context['candidate'] = failed
                except ModelUnavailableError as exc:
                    error = str(exc)
                    break
            self.store.message(project_id, "assistant", f"Proposal failed: {error}", {"context": chat_context, "kind": "error"})
            raise ValueError(error or "Proposal validation failed")

    async def rerun(self, project_id: str, revision_id: str, parameters: dict,
                    emit: Callable[[dict], None], cancel: threading.Event) -> None:
        await self.execute(project_id, self.store.revision(project_id, revision_id), parameters, emit, cancel)
