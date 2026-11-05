"""Durable run jobs and small, reconnectable project event notifications."""

import asyncio
import json
import threading
from typing import Any
from uuid import uuid4

from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.target_manager import TargetManager
from backend.services.workspace_service import Workspaces, WorkspaceConflict
from pipeline_core.models import ProjectRevision, now


class ProjectEvents:
    def __init__(self) -> None:
        self.sequences: dict[str, int] = {}
        self.subscribers: dict[str, set[asyncio.Queue[int]]] = {}

    def publish(self, project_id: str) -> None:
        sequence = self.sequences.get(project_id, 0) + 1
        self.sequences[project_id] = sequence
        for queue in self.subscribers.get(project_id, set()):
            if queue.empty():
                queue.put_nowait(sequence)


class ProjectJobs:
    def __init__(self, store: ProjectStore, service: ProjectService, targets: TargetManager, events: ProjectEvents) -> None:
        self.store, self.service, self.targets, self.events = store, service, targets, events
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.cancellations: dict[str, threading.Event] = {}
        self.closing = False

    def put(self, project_id: str, job: dict[str, Any]) -> None:
        with self.store.connect() as db:
            db.execute("INSERT INTO jobs(id,project_id,record) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record",
                (job["id"], project_id, json.dumps(job)))
        self.events.publish(project_id)

    def get(self, project_id: str, job_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute("SELECT record FROM jobs WHERE id=? AND project_id=?", (job_id, project_id)).fetchone()
        if not row:
            raise KeyError("Job not found")
        return dict(json.loads(row["record"]))

    def list(self, project_id: str) -> list[dict[str, Any]]:
        self.store.get(project_id)
        with self.store.connect() as db:
            rows = db.execute("SELECT record FROM jobs WHERE project_id=? ORDER BY rowid DESC LIMIT 20", (project_id,)).fetchall()
        return [json.loads(row["record"]) for row in rows]

    def create(self, project_id: str, version: int, parameters: dict[str, Any],
               expected_input_hash: str | None = None) -> dict[str, Any]:
        if any(job["status"] in {"queued", "running"} for job in self.list(project_id)):
            raise ValueError("A workspace run is already queued or running for this project")
        workspaces = Workspaces(self.store)
        current = workspaces.get(project_id)
        if current['version'] != version:
            raise WorkspaceConflict('Save the latest workspace before running')
        revision: ProjectRevision
        blocked: list[dict] = []
        partial = bool(current['issues'])
        if partial:
            from pipeline_core.partial import execution_plan
            from pipeline_core.workspace import WorkspaceDocument
            self.store.dataset_path(project_id)
            revision, blocked = execution_plan(WorkspaceDocument.model_validate(current['document']))
        else:
            revision = workspaces.compile(project_id, version)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            project = dict(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
            workspace = db.execute('SELECT version FROM workspaces WHERE project_id=?', (project_id,)).fetchone()
            if (not workspace or workspace['version'] != version
                    or (expected_input_hash is not None and project['dataset_hash'] != expected_input_hash)):
                raise WorkspaceConflict('The workspace or input changed before the run was captured. Ask again.')
        source = self.store.root / project_id / 'datasets' / f"{project['dataset_hash']}.csv"
        job: dict[str, Any] = {"id": str(uuid4()), "revision_id": revision.revision_id, "workspace_version": version,
            "status": "queued", "run_id": None, "error": None, "partial": partial, "events": [{"event": "step", **v} for v in blocked], "created_at": now()}
        self.put(project_id, job)
        cancel = threading.Event()
        self.cancellations[job["id"]] = cancel

        def emit(event: dict[str, Any]) -> None:
            compact = {key: value for key, value in event.items() if key in {
                "event", "message", "step_id", "title", "status", "cached", "duration_ms", "run_id"}}
            job["events"] = [*job["events"], compact][-100:]
            if event["event"] == "run_started":
                job["run_id"] = event["run_id"]
            if event["event"] in {"step", "worker_started"} and job["status"] in {"queued", "running"}:
                job["status"] = "running"
            self.put(project_id, job)

        async def execute() -> None:
            try:
                run = await self.service.execute(project_id, revision, parameters, emit, cancel,
                    input_path=source, dataset_name=project["dataset_name"], workspace_version=version)
                job.update(status=run.status, error=run.error)
                if run.status == "succeeded" and not partial:
                    # Later presentation edits may safely reuse this run, but later calculation edits stay pending.
                    await asyncio.to_thread(Workspaces(self.store).validate_presentation, project_id)
                if not partial:
                    await self.targets.sync(project_id)
            except asyncio.CancelledError:
                cancel.set()
                job.update(status="interrupted" if self.closing else "cancelled", error="Builder stopped" if self.closing else "Run cancelled")
            except Exception as exc:
                job.update(status="failed", error=str(exc))
            finally:
                job["finished_at"] = now()
                self.put(project_id, job)
                self.cancellations.pop(job["id"], None)
                self.tasks.pop(job["id"], None)
        self.tasks[job["id"]] = asyncio.create_task(execute())
        def finished(task: asyncio.Task[None]) -> None:
            self.tasks.pop(job["id"], None)
            self.cancellations.pop(job["id"], None)
        self.tasks[job["id"]].add_done_callback(finished)
        return job

    def cancel(self, project_id: str, job_id: str) -> dict[str, Any]:
        job = self.get(project_id, job_id)
        event = self.cancellations.get(job_id)
        if event:
            event.set()
            if job["status"] == "queued":
                job.update(status="cancelled", error="Run cancelled", finished_at=now())
                self.put(project_id, job)
                task = self.tasks.get(job_id)
                if task:
                    task.cancel()
        return {"cancel_requested": event is not None}

    async def close(self) -> None:
        self.closing = True
        for event in self.cancellations.values():
            event.set()
        for event in self.service.cancellations.values():
            event.set()
        tasks = list(self.tasks.values())
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 7)
            except asyncio.TimeoutError:
                for task in tasks:
                    task.cancel()
