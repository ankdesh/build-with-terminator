"""Durable chat work, question cards, explicit rules and temporary evidence."""
from __future__ import annotations
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import WorkspaceConflict
from pipeline_core.models import now
from pipeline_core.engine import fingerprint
from config import config

TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


def public_turn(turn: dict | None) -> dict | None:
    if turn is None: return None
    return {key:turn[key] for key in ['id','request_id','status','context','error','clarification_id',
        'model_steps','active_seconds','created_at','updated_at','result'] if key in turn}


class AgentStore:
    def __init__(self, store: ProjectStore):
        self.store = store

    def get(self, project_id: str, turn_id: str) -> dict:
        with self.store.connect() as db:
            row = db.execute('SELECT record FROM agent_turns WHERE id=? AND project_id=?', (turn_id,project_id)).fetchone()
        if row is None: raise KeyError('Chat request not found')
        return dict(json.loads(row['record']))

    def active(self, project_id: str) -> dict | None:
        with self.store.connect() as db:
            rows = db.execute('SELECT record FROM agent_turns WHERE project_id=? ORDER BY rowid DESC', (project_id,)).fetchall()
        return next((json.loads(row['record']) for row in rows if json.loads(row['record'])['status'] not in TERMINAL),None)

    def create(self, project_id: str, query: str, context: dict, workspace: dict, input_hash: str | None,
               request_id: str | None = None, page_context: str | None = None, proposal_id: str | None = None) -> tuple[dict,bool]:
        request_id = request_id or str(uuid4())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT record FROM agent_turns WHERE project_id=? AND request_id=?', (project_id,request_id)).fetchone()
            if old: return json.loads(old['record']),False
            for row in db.execute('SELECT record FROM agent_turns WHERE project_id=?', (project_id,)):
                if json.loads(row['record'])['status'] not in TERMINAL:
                    raise WorkspaceConflict('Chat already has an active request. Answer its questions or cancel it first.')
            turn = {'id':str(uuid4()),'project_id':project_id,'request_id':request_id,'query':query,'context':context,
                'workspace_version':workspace['version'],'input_hash':input_hash,'status':'queued','answers':[],
                'scope_approved':False,'raw_approved':False,'clarification_rounds':0,'page_context':page_context,
                'proposal_id':proposal_id,'trace':[],'model_steps':0,'created_at':now(),'updated_at':now()}
            db.execute('INSERT INTO agent_turns VALUES(?,?,?,?)',(turn['id'],project_id,request_id,json.dumps(turn)))
        return turn,True

    def put(self, turn: dict) -> None:
        turn['updated_at'] = now()
        with self.store.connect() as db:
            # Cancellation is monotonic, including while a provider request finishes.
            row = db.execute('SELECT record FROM agent_turns WHERE id=?', (turn['id'],)).fetchone()
            if row and json.loads(row['record'])['status'] == 'cancelled': turn['status'] = 'cancelled'
            db.execute('UPDATE agent_turns SET record=? WHERE id=? AND project_id=?', (json.dumps(turn),turn['id'],turn['project_id']))

    def event(self, turn: dict, event: dict) -> dict:
        from backend.services.llm_gateway import redact_credentials
        event = json.loads(redact_credentials(json.dumps(event,default=str),config.openai_api_key))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            sequence = db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE turn_id=?',(turn['id'],)).fetchone()[0]
            event = {**event,'turn_id':turn['id'],'sequence':sequence}
            db.execute('INSERT INTO agent_events VALUES(?,?,?)',(turn['id'],sequence,json.dumps(event)))
        return event

    def events(self, project_id: str, turn_id: str, after: int = 0) -> list[dict]:
        self.get(project_id,turn_id)
        with self.store.connect() as db:
            return [json.loads(r['record']) for r in db.execute('SELECT record FROM agent_events WHERE turn_id=? AND sequence>? ORDER BY sequence',(turn_id,after))]

    def schema_hash(self, project_id: str) -> str:
        project = self.store.get(project_id)
        columns = [{'name':c['name'],'type':c['data_type']} for c in (project['profile'] or {}).get('columns',[])]
        return hashlib.sha256(json.dumps(columns,sort_keys=True).encode()).hexdigest()

    def rules(self, project_id: str) -> list[dict]:
        schema_hash = self.schema_hash(project_id)
        with self.store.connect() as db:
            return [{**json.loads(r['record']),'needs_review':json.loads(r['record'])['schema_hash'] != schema_hash}
                for r in db.execute('SELECT record FROM project_rules WHERE project_id=? ORDER BY rowid',(project_id,))]

    def save_rule(self, project_id: str, text: str, identifier: str | None = None) -> dict:
        if not text.strip() or len(text)>4000: raise ValueError('A project rule needs 1–4000 characters')
        identifier = identifier or str(uuid4())
        rule = {'id':identifier,'text':text.strip(),'schema_hash':self.schema_hash(project_id),'updated_at':now()}
        with self.store.connect() as db:
            existing = db.execute('SELECT project_id FROM project_rules WHERE id=?',(identifier,)).fetchone()
            if existing and existing['project_id'] != project_id: raise KeyError('Rule not found in this project')
            db.execute('INSERT INTO project_rules VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record',(identifier,project_id,json.dumps(rule)))
        return rule

    def delete_rule(self, project_id: str, identifier: str) -> None:
        with self.store.connect() as db:
            if db.execute('DELETE FROM project_rules WHERE id=? AND project_id=?',(identifier,project_id)).rowcount != 1:
                raise KeyError('Rule not found')

    def rules_version(self, project_id: str) -> str:
        return hashlib.sha256(json.dumps(self.rules(project_id),sort_keys=True).encode()).hexdigest()

    def artifact(self, project_id: str, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute('SELECT record FROM analysis_artifacts WHERE id=? AND project_id=?',(identifier,project_id)).fetchone()
        if not row: raise KeyError('Analysis artifact not found')
        return dict(json.loads(row['record']))

    def add_artifact(self, project_id: str, directory: Path, result: dict, provenance: dict) -> dict:
        identifier = directory.parent.name
        root = self.store.project_dir(project_id).resolve()
        if not directory.resolve().is_relative_to(root) or any(path.is_symlink() for path in directory.iterdir()):
            raise ValueError('Invalid analysis artifact directory')
        files = {p.name:fingerprint(p) for p in directory.glob('*') if p.is_file() and p.name not in {'worker.log'}}
        record = {'id':identifier,'directory':str(directory.resolve().relative_to(root)), 'result':result,
            'files':files,'provenance':provenance,'created_at':now(),'expired':False}
        with self.store.connect() as db:
            db.execute('INSERT INTO analysis_artifacts VALUES(?,?,?)',(identifier,project_id,json.dumps(record)))
        self.prune(project_id)
        return record

    def cached_artifact(self, project_id: str, analysis_key: str) -> dict | None:
        self.prune(project_id)
        with self.store.connect() as db:
            records = [json.loads(row['record']) for row in db.execute(
                'SELECT record FROM analysis_artifacts WHERE project_id=? ORDER BY rowid DESC',(project_id,))]
        for record in records:
            if record['expired'] or record['provenance'].get('analysis_key')!=analysis_key: continue
            try:
                for filename in record['files']: self.artifact_file(project_id,record['id'],filename)
            except (OSError,ValueError): continue
            return cast(dict,record)
        return None

    def artifact_file(self, project_id: str, identifier: str, filename: str) -> Path:
        self.prune(project_id)
        record = self.artifact(project_id,identifier)
        if record['expired']: raise ValueError('These temporary files expired. Ask to calculate the result again.')
        root = self.store.project_dir(project_id).resolve()
        candidate = root/record['directory']/filename
        if candidate.is_symlink(): raise ValueError('Analysis artifact integrity check failed')
        path = candidate.resolve()
        if (Path(filename).name != filename or filename not in record['files'] or not path.is_relative_to(root)
                or not path.is_file() or path.is_symlink() or fingerprint(path) != record['files'][filename]):
            raise ValueError('Analysis artifact integrity check failed')
        return cast(Path, path)

    def prune(self, project_id: str, clear: bool = False) -> None:
        active = self.active(project_id)
        with self.store.connect() as db:
            records = [json.loads(r['record']) for r in db.execute('SELECT record FROM analysis_artifacts WHERE project_id=? ORDER BY rowid DESC',(project_id,))]
            pending = [json.loads(r['record']) for r in db.execute('SELECT record FROM chat_items WHERE project_id=?',(project_id,))]
        proposal_artifacts = {item.get('analysis_artifact_id') for item in pending if item.get('status')=='pending'}
        total = 0
        cutoff = datetime.now(timezone.utc)-timedelta(days=config.agent_artifact_retention_days)
        root = self.store.project_dir(project_id).resolve()
        for record in records:
            directory = (root/record['directory']).resolve()
            if not directory.is_relative_to(root) or record['expired']: continue
            total += sum(p.stat().st_size for p in directory.glob('*') if p.is_file())
            pinned = (active and (active['id'] == record['provenance'].get('turn_id') or active.get('artifact_id')==record['id'])) or record['id'] in proposal_artifacts
            if not pinned and (clear or datetime.fromisoformat(record['created_at'])<cutoff or total>config.agent_artifact_limit_mb*1024**2):
                shutil.rmtree(directory,ignore_errors=True)
                record['expired'] = True
                with self.store.connect() as db:
                    db.execute('UPDATE analysis_artifacts SET record=? WHERE id=? AND project_id=?',(json.dumps(record),record['id'],project_id))
