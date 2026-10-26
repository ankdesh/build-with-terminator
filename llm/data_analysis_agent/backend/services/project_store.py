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
            """)
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
        if row is None:
            raise KeyError("Project not found")
        result = dict(row)
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

    def save_revision(self, project_id: str, revision: ProjectRevision) -> None:
        directory = self.project_dir(project_id) / "revisions"
        directory.mkdir(exist_ok=True)
        path = directory / f"{revision.revision_id}.json"
        if path.exists():
            raise ValueError("Revisions are immutable; create a new revision")
        path.write_text(revision.model_dump_json(indent=2))
        with self.connect() as db:
            db.execute("INSERT INTO revisions(id,project_id,parent_id,created_at,summary) VALUES(?,?,?,?,?)",
                (revision.revision_id, project_id, revision.parent_revision_id, revision.created_at, revision.summary))
            db.execute("UPDATE projects SET draft_id=?,title=?,updated_at=? WHERE id=?",
                (revision.revision_id, revision.title, now(), project_id))

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
            if run.status == "succeeded":
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
        revision = self.revision(project_id, run.revision_id)
        if run.status != "succeeded" or run.result is None:
            raise ValueError("Only a successful, validated run can be accepted")
        if run.parameters != revision.default_parameters():
            raise ValueError("Reset dashboard controls and validate the default parameters before acceptance")
        impacts = run.result.get("cleanup_impacts", [])
        if any(item["requires_confirmation"] for item in impacts) and not cleanup_confirmed:
            raise ValueError("Confirm the cleanup rules and their impact before acceptance")
        with self.connect() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if project["dataset_hash"] != run.input_hash or project["draft_id"] != run.revision_id:
                raise ValueError("The input or draft changed; validate the current draft again")
            db.execute("UPDATE revisions SET accepted=1 WHERE id=?", (run.revision_id,))
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

    def message(self, project_id: str, role: str, content: str) -> None:
        self.get(project_id)
        with self.connect() as db:
            db.execute("INSERT INTO messages(project_id,role,content,created_at) VALUES(?,?,?,?)", (project_id, role, content, now()))

    def messages(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT role,content,created_at FROM messages WHERE project_id=? ORDER BY id", (project_id,))]

    def view(self, project_id: str) -> dict[str, Any]:
        project = self.get(project_id)
        display = self.run(project_id, project["display_run_id"]) if project["display_run_id"] else None
        return {"project": project, "revisions": self.revisions(project_id), "messages": self.messages(project_id),
            "draft": self.revision(project_id, project["draft_id"]).model_dump() if project["draft_id"] else None,
            "display_run": display.model_dump() if display else None,
            "display_revision": self.revision(project_id, display.revision_id).model_dump() if display else None}
