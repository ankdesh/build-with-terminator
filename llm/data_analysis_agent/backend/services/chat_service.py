"""Answer questions without editing; prepare changes only for explicit review."""
from __future__ import annotations

import json
from typing import Any
from backend.services.run_diagnostics import read_object, inside_file
from backend.services.project_store import ProjectStore
from pipeline_core.engine import fingerprint
from backend.services.llm_gateway import redact_credentials
from backend.services.agent_controller import AgentController
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


class ChatService(AgentController):
    """Compatibility name for the durable agent controller."""
