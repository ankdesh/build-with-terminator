"""SQLite metadata with immutable revision, dataset, and run files."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from pipeline_core.engine import fingerprint
from pipeline_core.models import ProjectRevision, RunRecord, now


class ProjectStore:
    """Persist project identity and atomically promote accepted revisions."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "projects.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, dataset_hash TEXT, dataset_name TEXT,
                    description TEXT NOT NULL DEFAULT '', profile TEXT,
                    draft_id TEXT, accepted_id TEXT, display_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, parent_id TEXT,
                    created_at TEXT NOT NULL, summary TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision_id TEXT NOT NULL,
                    started_at TEXT NOT NULL, record TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, role TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    project_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                    document TEXT NOT NULL, history TEXT NOT NULL DEFAULT '[]',
                    future TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS target_preferences (
                    project_id TEXT PRIMARY KEY, port INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, record TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS acceptances (
                    revision_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, accepted_at TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(messages)")}
            if "metadata" not in columns:
                db.execute("ALTER TABLE messages ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
            db.execute("CREATE TABLE IF NOT EXISTS chat_items (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, record TEXT NOT NULL)")
            for item in db.execute("SELECT id,record FROM chat_items").fetchall():
                record = json.loads(item["record"])
                if record.get("run_status") in {"queued", "answering"}:
                    record.update(run_status="interrupted", run_error="Builder stopped. No automatic retry was started.")
                    db.execute("UPDATE chat_items SET record=? WHERE id=?", (json.dumps(record), item["id"]))
            for row in db.execute("SELECT id,record FROM jobs").fetchall():
                job = json.loads(row["record"])
                if job["status"] in {"running", "queued"}:
                    job.update(status="interrupted", error="Builder stopped before this job completed")
                    db.execute("UPDATE jobs SET record=? WHERE id=?", (json.dumps(job), row["id"]))
            # A terminated API process cannot leave a live worker-owned run.
            for row in db.execute("SELECT id,record FROM runs").fetchall():
                record = json.loads(row["record"])
                if record["status"] == "running":
                    record.update(status="interrupted", finished_at=now(), error="Application stopped before this run completed")
                    db.execute("UPDATE runs SET record=? WHERE id=?", (json.dumps(record), row["id"]))

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, title: str = "New analysis") -> dict[str, Any]:
        identifier, timestamp = str(uuid4()), now()
        with self.connect() as db:
            db.execute("INSERT INTO projects(id,title,created_at,updated_at) VALUES(?,?,?,?)", (identifier, title, timestamp, timestamp))
        (self.root / identifier).mkdir()
        return self.get(identifier)

    def get(self, project_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            acceptance = db.execute("SELECT run_id FROM acceptances WHERE revision_id=(SELECT accepted_id FROM projects WHERE id=?)", (project_id,)).fetchone()
        if row is None:
            raise KeyError("Project not found")
        result = dict(row)
        result["accepted_run_id"] = acceptance["run_id"] if acceptance else None
        result["profile"] = json.loads(result["profile"]) if result["profile"] else None
        return result

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,title,created_at,updated_at,dataset_name,draft_id,accepted_id FROM projects ORDER BY updated_at DESC")]

    def project_dir(self, project_id: str) -> Path:
        self.get(project_id)
        return self.root / project_id

    def save_dataset(self, project_id: str, source: Path, name: str, profile: dict, description: str) -> None:
        directory = self.project_dir(project_id) / "datasets"
        directory.mkdir(exist_ok=True)
        digest = fingerprint(source)
        destination = directory / f"{digest}.csv"
        if not destination.exists():
            import shutil
            shutil.copyfile(source, destination)
        with self.connect() as db:
            db.execute("UPDATE projects SET dataset_hash=?,dataset_name=?,profile=?,description=?,updated_at=? WHERE id=?",
                (digest, name, json.dumps(profile), description, now(), project_id))

    def describe(self, project_id: str, description: str) -> None:
        self.get(project_id)
        with self.connect() as db:
            db.execute("UPDATE projects SET description=?,updated_at=? WHERE id=?", (description, now(), project_id))

    def dataset_path(self, project_id: str) -> Path:
        project = self.get(project_id)
        if not project["dataset_hash"]:
            raise ValueError("Upload a CSV before building a pipeline")
        return self.root / project_id / "datasets" / f"{project['dataset_hash']}.csv"

    def save_revision(self, project_id: str, revision: ProjectRevision, sync_workspace: bool = True,
                      expected_workspace_version: int | None = None) -> None:
        directory = self.project_dir(project_id) / "revisions"
        directory.mkdir(exist_ok=True)
        path = directory / f"{revision.revision_id}.json"
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if expected_workspace_version is not None:
                row = db.execute("SELECT version FROM workspaces WHERE project_id=?", (project_id,)).fetchone()
                if not row or row["version"] != expected_workspace_version:
                    from backend.services.workspace_service import WorkspaceConflict
                    raise WorkspaceConflict("The workspace changed during presentation validation")
            if path.exists():
                raise ValueError("Revisions are immutable; create a new revision")
            path.write_text(revision.model_dump_json(indent=2))
            db.execute("INSERT INTO revisions(id,project_id,parent_id,created_at,summary) VALUES(?,?,?,?,?)",
                (revision.revision_id, project_id, revision.parent_revision_id, revision.created_at, revision.summary))
            db.execute("UPDATE projects SET draft_id=?,title=?,updated_at=? WHERE id=?",
                (revision.revision_id, revision.title, now(), project_id))
        if sync_workspace:
            from backend.services.workspace_service import Workspaces
            Workspaces(self).from_revision(project_id, revision)

    def revision(self, project_id: str, revision_id: str) -> ProjectRevision:
        with self.connect() as db:
            row = db.execute("SELECT id FROM revisions WHERE id=? AND project_id=?", (revision_id, project_id)).fetchone()
        if not row:
            raise KeyError("Revision not found in this project")
        return ProjectRevision.model_validate_json((self.root / project_id / "revisions" / f"{revision_id}.json").read_text())

    def revisions(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM revisions WHERE project_id=? ORDER BY created_at DESC", (project_id,))]

    def put_run(self, project_id: str, run: RunRecord) -> None:
        self.get(project_id)
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,project_id,revision_id,started_at,record) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record",
                (run.run_id, project_id, run.revision_id, run.started_at, run.model_dump_json()))
            if run.status == "succeeded" and run.validation_mode != "partial":
                previous = db.execute("SELECT record FROM runs WHERE id=(SELECT display_run_id FROM projects WHERE id=?)", (project_id,)).fetchone()
                if not previous or json.loads(previous["record"])["started_at"] <= run.started_at:
                    db.execute("UPDATE projects SET display_run_id=?,updated_at=? WHERE id=?", (run.run_id, now(), project_id))

    def run(self, project_id: str, run_id: str) -> RunRecord:
        with self.connect() as db:
            row = db.execute("SELECT record FROM runs WHERE id=? AND project_id=?", (run_id, project_id)).fetchone()
        if not row:
            raise KeyError("Run not found in this project")
        return RunRecord.model_validate_json(row["record"])

    def run_dir(self, project_id: str, run_id: str) -> Path:
        run = self.run(project_id, run_id)
        return self.root / project_id / "runs" / run.run_id

    def accept(self, project_id: str, run_id: str, cleanup_confirmed: bool) -> None:
        run = self.run(project_id, run_id)
        if run.validation_mode == "partial":
            raise ValueError("Partial runs cannot be accepted. Complete the dashboard first.")
        revision = self.revision(project_id, run.revision_id)
        if run.status != "succeeded" or run.result is None:
            raise ValueError("Only a successful, validated run can be accepted")
        if run.parameters != revision.default_parameters():
            raise ValueError("Reset dashboard controls and validate the default parameters before acceptance")
        from backend.services.workspace_service import Workspaces
        from pipeline_core.workspace import WorkspaceDocument
        workspace = Workspaces(self).get(project_id)
        if WorkspaceDocument.from_revision(revision).model_dump() != workspace["document"]:
            raise ValueError("The workspace changed; run or validate the current workspace before acceptance")
        impacts = run.result.get("cleanup_impacts", [])
        if any(item["requires_confirmation"] for item in impacts) and not cleanup_confirmed:
            raise ValueError("Confirm the cleanup rules and their impact before acceptance")
        with self.connect() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if project["dataset_hash"] != run.input_hash or project["draft_id"] != run.revision_id:
                raise ValueError("The input or draft changed; validate the current draft again")
            db.execute("UPDATE revisions SET accepted=1 WHERE id=?", (run.revision_id,))
            db.execute("INSERT INTO acceptances(revision_id,project_id,run_id,accepted_at) VALUES(?,?,?,?) ON CONFLICT(revision_id) DO UPDATE SET run_id=excluded.run_id,accepted_at=excluded.accepted_at",
                (run.revision_id, project_id, run.run_id, now()))
            db.execute("UPDATE projects SET accepted_id=?,updated_at=? WHERE id=?", (run.revision_id, now(), project_id))

    def rollback(self, project_id: str, revision_id: str) -> None:
        revision = self.revision(project_id, revision_id)
        with self.connect() as db:
            row = db.execute("SELECT accepted FROM revisions WHERE id=?", (revision_id,)).fetchone()
            if not row["accepted"]:
                raise ValueError("Rollback requires a previously accepted revision")
            # Keep accepted identity; its dashboard will update only after rerun.
            db.execute("UPDATE projects SET accepted_id=?,draft_id=?,title=?,updated_at=? WHERE id=?",
                (revision_id, revision_id, revision.title, now(), project_id))
        from backend.services.workspace_service import Workspaces
        Workspaces(self).from_revision(project_id, revision)

    def message(self, project_id: str, role: str, content: str, metadata: dict | None = None) -> int:
        self.get(project_id)
        with self.connect() as db:
            cursor = db.execute("INSERT INTO messages(project_id,role,content,created_at,metadata) VALUES(?,?,?,?,?)",
                (project_id, role, content, now(), json.dumps(metadata or {})))
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def messages(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [{**dict(r), "metadata": json.loads(r["metadata"])} for r in db.execute(
                "SELECT id,role,content,created_at,metadata FROM messages WHERE project_id=? ORDER BY id", (project_id,))]

    def partial_run(self, project_id: str) -> RunRecord | None:
        """Return retained partial evidence without promoting it to the dashboard."""
        with self.connect() as db:
            rows = db.execute("SELECT record FROM runs WHERE project_id=? ORDER BY started_at DESC", (project_id,)).fetchall()
        for row in rows:
            record = RunRecord.model_validate_json(row['record'])
            if record.validation_mode == 'partial' and record.status == 'succeeded' and record.result is not None:
                return record
        return None

    def view(self, project_id: str) -> dict[str, Any]:
        project = self.get(project_id)
        display = self.run(project_id, project["display_run_id"]) if project["display_run_id"] else None
        from backend.services.workspace_service import Workspaces
        from backend.services.chat_store import ChatStore
        return {"project": project, "workspace": Workspaces(self).get(project_id), "chat_items": ChatStore(self).list(project_id),
            "revisions": self.revisions(project_id), "messages": self.messages(project_id),
            "draft": self.revision(project_id, project["draft_id"]).model_dump() if project["draft_id"] else None,
            "partial_run": partial.model_dump() if (partial := self.partial_run(project_id)) else None,
            "display_run": display.model_dump() if display else None,
            "display_revision": self.revision(project_id, display.revision_id).model_dump() if display else None}
