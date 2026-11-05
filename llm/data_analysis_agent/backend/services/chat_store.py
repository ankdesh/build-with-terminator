"""Persistent reviewed chat edits and server-side scope checks."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING, cast
from uuid import uuid4

from backend.services.workspace_service import Workspaces, WorkspaceConflict
from pipeline_core.models import ProjectRevision, now
from pipeline_core.workspace import WorkspaceDocument, calculation_hash, stages

if TYPE_CHECKING:
    from backend.services.project_store import ProjectStore


STAGE_CATEGORIES = {
    "category:input": "Data input", "category:cleaning": "Data cleaning",
    "category:analysis": "Analysis", "category:visualization": "Visualization",
}


def context_for(document: dict, stage_id: str | None, has_input: bool = True) -> dict:
    if stage_id is None:
        return {'stage_id': None, 'label': 'Project'}
    if stage_id in STAGE_CATEGORIES:
        return {'stage_id': stage_id, 'label': STAGE_CATEGORIES[stage_id] + ' · Create or edit stages'}
    stage = next((s for s in stages(WorkspaceDocument.model_validate(document), has_input) if s['id'] == stage_id), None)
    if not stage:
        raise ValueError('The selected stage no longer exists. Select a stage or clear the chat context.')
    label = {'input': 'Data input', 'cleaning': 'Data cleaning', 'analysis': 'Analysis', 'visualization': 'Visualization'}[stage['type']]
    return {'stage_id': stage_id, 'label': f"{label} · {stage['title']}"}


def entities(document: dict) -> dict[str, dict]:
    return {'input:data': {'input_contract': document['input_contract'], 'input_enabled': document['input_enabled']},
        **{f"step:{s['id']}": s for s in document['steps']},
        **{f"widget:{w['id']}": w for w in document['dashboard']['widgets']},
        **{f"control:{p['id']}": p for p in document['parameters']},
        'dashboard:settings': {k: v for k, v in document['dashboard'].items() if k != 'widgets'},
        'project:settings': {k: document[k] for k in ['title', 'seed', 'dependencies']}}


def review_changes(before: dict, after: dict, selected: str | None, reasons: dict[str, str]) -> dict:
    if not isinstance(reasons, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in reasons.items()):
        raise ValueError('linked_reasons must map stage IDs to plain-language reasons')
    old, new = entities(before), entities(after)
    changes: list[dict] = []
    for identifier in sorted(old.keys() | new.keys()):
        left, right = old.get(identifier, {}), new.get(identifier, {})
        fields: list[str | None] = list(sorted(left.keys() | right.keys())) if left and right else [None]
        for field in fields:
            a, b = (old.get(identifier), new.get(identifier)) if field is None else (left.get(field), right.get(field))
            if a != b:
                changes.append({'stage_id': identifier, 'title': right.get('title', left.get('title', identifier)),
                    'field': field or 'stage', 'before': a, 'after': b})
    for key, order_before, order_after in [('step_order', [s['id'] for s in before['steps']], [s['id'] for s in after['steps']]),
            ('widget_order', [w['id'] for w in before['dashboard']['widgets']], [w['id'] for w in after['dashboard']['widgets']]),
            ('control_order', [p['id'] for p in before['parameters']], [p['id'] for p in after['parameters']])]:
        if order_before != order_after and set(order_before) == set(order_after):
            changes.append({'stage_id': 'project:settings', 'title': 'Project ordering', 'field': key, 'before': order_before, 'after': order_after})
    changed = {c['stage_id'] for c in changes}
    graph: dict[str, set[str]] = {}
    children: dict[str, set[str]] = {}
    for document in [before, after]:
        owners = {'data': 'input:data', **{o: f"step:{s['id']}" for s in document['steps'] for o in s['outputs']}}
        for identifier in entities(document):
            graph.setdefault(identifier, set())
        def edge(a: str, b: str) -> None:
            graph.setdefault(a, set()).add(b)
            children.setdefault(b, set()).add(a)
        for stage in stages(WorkspaceDocument.model_validate(document), True):
            for dependency in stage['dependencies']:
                edge(stage['id'], dependency)
        for parameter in document['parameters']:
            pid = f"control:{parameter['id']}"
            if parameter.get('filter_column'):
                edge(pid, owners.get(parameter.get('filter_artifact', 'cleaned'), 'input:data'))
                for step in document['steps']:
                    if step['stage'] == 'analysis':
                        edge(pid, f"step:{step['id']}")
            for step in document['steps']:
                if step.get('parameters_used') is None or parameter['id'] in step['parameters_used']:
                    edge(pid, f"step:{step['id']}")
    primary = {selected} if selected else set(graph)
    if selected in STAGE_CATEGORIES:
        category = selected.split(":", 1)[1]
        primary = {s["id"] for document in [before, after]
            for s in stages(WorkspaceDocument.model_validate(document), True) if s["type"] == category}
    connected: set[str] = set()
    for direction in [graph, children]:
        visited = set(primary)
        pending = list(visited)
        while pending:
            for adjacent in direction.get(pending.pop(), set()) - visited:
                visited.add(adjacent)
                pending.append(adjacent)
        connected.update(visited)
    linked = changed - primary if selected else set()
    if selected and changed - connected:
        raise ValueError('Unrelated edits are not allowed in stage context. Use Project context for: '+', '.join(sorted(changed-connected)))
    if selected and any(not reasons.get(identifier, '').strip() for identifier in linked):
        raise ValueError('Explain each related-stage or shared-control edit in linked_reasons, keyed by its stage ID.')
    # Include downstream consumers even when their saved source/configuration is unchanged.
    impacted = set(changed)
    for document in [before, after]:
        stage_list = stages(WorkspaceDocument.model_validate(document), True)
        again = True
        while again:
            again = False
            for stage in stage_list:
                if stage['id'] not in impacted and any(d in impacted for d in stage['dependencies']):
                    impacted.add(stage['id']); again = True
            for parameter in document['parameters']:
                if f"control:{parameter['id']}" in changed:
                    for step in document['steps']:
                        if parameter.get('filter_column') or step.get('parameters_used') is None or parameter['id'] in step['parameters_used']:
                            if f"step:{step['id']}" not in impacted:
                                impacted.add(f"step:{step['id']}"); again = True
    return {'changes': changes, 'affected': sorted(impacted), 'linked_reasons': reasons,
        'calculation_changed': calculation_hash(before) != calculation_hash(after)}


def validate_draft(document: WorkspaceDocument) -> None:
    from pipeline_core.validation import validate_source
    for identifiers, label in [([v.id for v in document.steps], 'step'), ([v.id for v in document.parameters], 'parameter'), ([v.id for v in document.dashboard.widgets], 'widget')]:
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f'Duplicate {label} identifiers')
    outputs = [output for step in document.steps for output in step.outputs]
    if len(set(outputs)) != len(outputs) or 'data' in outputs:
        raise ValueError('Output names must be unique and cannot replace data')
    for step in document.steps:
        validate_source(step.code, step.function)


def public_item(record: dict, developer: bool = False) -> dict:
    result = {k: v for k, v in record.items() if k not in {'revision', 'document'}}
    if developer:
        return result
    def hide(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: 'Python source (Inspect in developer mode)' if k == 'code' else hide(v) for k, v in value.items()}
        if isinstance(value, list):
            return [hide(v) for v in value]
        return value
    result = hide(result)
    for change in result.get('changes', []):
        if change['field'] == 'code':
            change['before'] = 'Existing Python source'
            change['after'] = 'Python source updated; review the explanation and affected stages.'
    return cast(dict, result)


class ChatStore:
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def put(self, project_id: str, record: dict) -> dict:
        with self.store.connect() as db:
            db.execute('INSERT INTO chat_items(id,project_id,record) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record',
                (record['id'], project_id, json.dumps(record)))
        return cast(dict, record)

    def get(self, project_id: str, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute('SELECT record FROM chat_items WHERE id=? AND project_id=?', (identifier, project_id)).fetchone()
        if row is None:
            raise KeyError('Chat review not found in this project')
        return dict(json.loads(row['record']))

    def list(self, project_id: str) -> list[dict]:
        workspace = Workspaces(self.store).get(project_id)
        project = self.store.get(project_id)
        with self.store.connect() as db:
            records = db.execute('SELECT record FROM chat_items WHERE project_id=? ORDER BY rowid', (project_id,)).fetchall()
        result = []
        for row in records:
            record = json.loads(row['record'])
            record['stale'] = (record.get('applied_version', record['version']) != workspace['version']
                or record['input_hash'] != project['dataset_hash'])
            result.append(public_item(record))
        return result

    def create(self, project_id: str, kind: str, query: str, context: dict, version: int, input_hash: str | None, **values: Any) -> dict:
        return self.put(project_id, {'id': str(uuid4()), 'kind': kind, 'query': query, 'context': context,
            'version': version, 'input_hash': input_hash, 'status': 'pending', 'created_at': now(), **values})

    def discard(self, project_id: str, identifier: str) -> dict:
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record FROM chat_items WHERE id=? AND project_id=?', (identifier, project_id)).fetchone()
            if row is None: raise KeyError('Chat review not found')
            record = json.loads(row['record'])
            if record['status'] == 'applied' and not record.get('job_id'):
                record['run_skipped'] = True
                db.execute('UPDATE chat_items SET record=? WHERE id=?', (json.dumps(record), identifier))
            if record['status'] == 'pending' and not record.get('job_id'):
                record['status'] = 'discarded'
                db.execute('UPDATE chat_items SET record=? WHERE id=?', (json.dumps(record), identifier))
        return cast(dict, record)

    def apply(self, project_id: str, identifier: str) -> dict:
        # Files are immutable. A failed transaction may leave an unreferenced file, never a partial workspace.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = db.execute('SELECT record FROM chat_items WHERE id=? AND project_id=?', (identifier, project_id)).fetchone()
            if item is None: raise KeyError('Chat review not found')
            record = json.loads(item['record'])
            if record['status'] == 'applied': return cast(dict, record)
            if record['kind'] != 'proposal' or record['status'] != 'pending':
                raise ValueError('This proposal cannot be applied')
            project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            workspace = db.execute('SELECT * FROM workspaces WHERE project_id=?', (project_id,)).fetchone()
            assert project and workspace
            if workspace['version'] != record['version'] or project['dataset_hash'] != record['input_hash']:
                raise WorkspaceConflict('The workspace or CSV changed. Request a fresh proposal before applying.')
            document = WorkspaceDocument.model_validate(record['document'])
            validate_draft(document)
            revision = ProjectRevision.model_validate(record['revision']) if record.get('revision') else None
            review_changes(json.loads(workspace['document']), document.model_dump(), record['context']['stage_id'], record['linked_reasons'])
            if revision:
                directory = self.store.root / project_id / 'revisions'
                directory.mkdir(exist_ok=True)
                path = directory / f'{revision.revision_id}.json'
                if path.exists(): raise ValueError('Revision identity already exists')
                path.write_text(revision.model_dump_json(indent=2))
            history = [*json.loads(workspace['history']), json.loads(workspace['document'])][-50:]
            db.execute("UPDATE workspaces SET version=version+1,document=?,history=?,future='[]' WHERE project_id=?",
                (document.model_dump_json(), json.dumps(history), project_id))
            if revision:
                db.execute('INSERT INTO revisions(id,project_id,parent_id,created_at,summary) VALUES(?,?,?,?,?)',
                    (revision.revision_id, project_id, project['draft_id'], revision.created_at, revision.summary))
                db.execute('UPDATE projects SET draft_id=?,title=?,updated_at=? WHERE id=?', (revision.revision_id, document.title, now(), project_id))
            else:
                db.execute('UPDATE projects SET title=?,updated_at=? WHERE id=?', (document.title, now(), project_id))
            record.update(status='applied', applied_version=workspace['version']+1)
            db.execute('UPDATE chat_items SET record=? WHERE id=?', (json.dumps(record), identifier))
            db.execute('INSERT INTO messages(project_id,role,content,created_at,metadata) VALUES(?,?,?,?,?)',
                (project_id, 'assistant', 'Changes applied. '+('Select Run to update calculations.' if record['calculation_changed'] else 'Presentation changes saved.'), now(),
                 json.dumps({'context': record['context'], 'kind': 'applied', 'item_id': identifier})))
        return cast(dict, record)
