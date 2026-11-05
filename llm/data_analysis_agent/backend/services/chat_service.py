"""Answer questions without editing; prepare changes only for explicit review."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable

from backend.services.chat_agent import reply
from backend.services.chat_store import ChatStore, context_for, public_item
from backend.services.project_service import ProjectService
from backend.services.run_diagnostics import collect_run_diagnostics, read_object, inside_file
from backend.services.project_store import ProjectStore
from pipeline_core.engine import fingerprint
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from backend.services.llm_gateway import redact_credentials
from config import config


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_credentials(value, config.openai_api_key)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def results_preview(run: dict | None, store: ProjectStore | None = None, project_id: str | None = None) -> dict:
    if not run: return {}
    saved = dict((run.get('result') or {}).get('outputs', {}))
    if store and project_id and run['status'] == 'succeeded':
        directory = store.run_dir(project_id, run['run_id']) / 'output'
        cache = read_object(directory / 'cache.json', directory, limit=1024*1024)
        # Small named scalar artifacts need no dashboard widget to answer a question.
        checked = 0
        for step in list(cache.values())[:40]:
            if not isinstance(step, dict): continue
            artifacts = step.get('outputs', {})
            if not isinstance(artifacts, dict): continue
            for name, artifact in list(artifacts.items())[:80]:
                if checked >= 80: break
                if name in saved or not isinstance(artifact, dict) or artifact.get('kind') != 'json': continue
                checked += 1
                path = directory / str(artifact.get('file', ''))
                if not inside_file(path, directory): continue
                try:
                    if path.stat().st_size > 16000 or fingerprint(path) != artifact.get('sha256'): continue
                    value = json.loads(path.read_text())
                    if value is None or isinstance(value, (str, int, float, bool)):
                        saved[name] = {'kind': 'text' if isinstance(value, str) else 'metric', 'value': value}
                except (OSError, ValueError):
                    continue
    outputs = {}
    budget = 16000
    for name, output in saved.items():
        item = {k: output[k] for k in ['kind', 'total_rows'] if k in output}
        if 'value' in output and not isinstance(output['value'], (dict, list)):
            item['value'] = str(output['value'])[:1000] if isinstance(output['value'], str) else output['value']
        if 'columns' in output:
            item['columns'] = output['columns'][:20]
            item['rows'] = [{key: str(value)[:100] if isinstance(value, str) else value
                for key, value in row.items() if key in item['columns']} for row in output.get('rows', [])[:5]]
            item['preview_only'] = True
        size = len(json.dumps(item))
        if size > budget: continue
        outputs[name] = item
        budget -= size
    return {'run_id': run['run_id'], 'revision_id': run['revision_id'], 'input_hash': run['input_hash'],
        'dataset_name': run['dataset_name'], 'parameters': run['parameters'], 'status': run['status'],
        'outputs': outputs, 'note': 'Bounded saved output previews. Table previews are not complete datasets.'}


class ChatService:
    def __init__(self, service: ProjectService) -> None:
        self.service, self.store = service, service.store
        self.items = ChatStore(self.store)

    async def respond(self, project_id: str, query: str, stage_id: str | None, expected_version: int | None,
                      emit: Callable[[dict], None], cancel: threading.Event, *, answer_only: bool = False,
                      run_id: str | None = None, captured_context: dict | None = None) -> dict:
        project = self.store.get(project_id)
        workspace = Workspaces(self.store).get(project_id)
        if expected_version is not None and workspace['version'] != expected_version:
            raise WorkspaceConflict('The workspace changed. Reload before sending this request.')
        context = captured_context or context_for(workspace['document'], stage_id, bool(project['dataset_hash']))
        if not answer_only:
            self.store.message(project_id, 'user', query, {'context': context, 'workspace_version': workspace['version']})
        run_id = run_id or project['display_run_id']
        run = self.store.run(project_id, run_id).model_dump() if run_id else None
        diagnostics = await asyncio.to_thread(collect_run_diagnostics, self.store, project_id, query, config.openai_api_key)
        evidence = {'request': query, 'selected_context': context, 'answer_only': answer_only,
            'workspace': workspace, 'description': project['description'], 'profile': project['profile'],
            'builder_input_hash': project['dataset_hash'], 'saved_results': results_preview(run, self.store, project_id),
            'run_diagnostics': diagnostics, 'recent_conversation': self.store.messages(project_id)[-12:]}
        emit({'event': 'status', 'message': 'Reading the selected context' if stage_id else 'Reading the project'})
        decision = await reply(self.service.agent.llm, redact(evidence))
        if cancel.is_set(): raise ValueError('Chat cancelled')
        if decision.kind == 'proposal':
            return await self.service.build(project_id, query, emit, cancel, stage_id, workspace['version'], record_user=False)
        metadata: dict = {'context': context, 'kind': decision.kind, 'workspace_version': workspace['version'],
            'run_id': run_id, 'revision_id': run['revision_id'] if run else None,
            'input_hash': run['input_hash'] if run else project['dataset_hash']}
        if decision.kind == 'needs_run':
            item = self.items.create(project_id, 'needs_run', query, context, workspace['version'],
                project['dataset_hash'], message=decision.message)
            metadata['item_id'] = item['id']
            emit({'event': 'needs_run', 'item': public_item(item)})
        self.store.message(project_id, 'assistant', decision.message, metadata)
        emit({'event': decision.kind, 'message': decision.message, 'metadata': metadata})
        return {'kind': decision.kind, 'message': decision.message}
