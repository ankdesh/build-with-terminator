"""Project API and event streaming for the local authoring application."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.services.dataset_import import import_csv
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import Workspaces
from backend.services.target_manager import TargetManager
from backend.services.project_jobs import ProjectEvents, ProjectJobs
from pipeline_core.workspace import WorkspaceDocument
from config import config

router = APIRouter(prefix="/api/projects", tags=["projects"])
store = ProjectStore(Path(os.environ.get("WPS_PROJECTS_DIR", str(config.sessions_dir.parent / "projects"))))
service = ProjectService(store)
events = ProjectEvents()
targets = TargetManager(store)
jobs = ProjectJobs(store, service, targets, events)
internal_router = APIRouter(prefix="/api/internal/targets", include_in_schema=False)
target_cancellations: dict[tuple[str, str], threading.Event] = {}
target_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}
target_running: set[tuple[str, str]] = set()


class CreateProject(BaseModel):
    title: str = Field(default="New analysis", min_length=1, max_length=200)


class BuildRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    description: str | None = Field(default=None, max_length=12000)


class RunRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class AcceptRequest(BaseModel):
    run_id: str
    cleanup_confirmed: bool = False


class WorkspaceEdit(BaseModel):
    expected_version: int
    document: WorkspaceDocument | None = None
    action: Literal["edit", "undo", "redo"] = "edit"


class DeleteStage(BaseModel):
    expected_version: int
    confirmed: bool = False


class WorkspaceRun(RunRequest):
    expected_version: int


class TargetExecution(BaseModel):
    revision_id: str
    input: str
    run_id: UUID
    cache_run_id: UUID | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


async def changed(project_id: str) -> None:
    events.publish(project_id)
    await targets.sync(project_id)


def stream_operation(operation: Any) -> EventSourceResponse:
    queue: asyncio.Queue = asyncio.Queue()
    cancel = threading.Event()

    async def produce() -> None:
        try:
            await operation(queue.put_nowait, cancel)
        except Exception as exc:
            queue.put_nowait({"event": "error", "message": str(exc)})
        finally:
            queue.put_nowait({"event": "done"})

    async def events() -> Any:
        task = asyncio.create_task(produce())
        try:
            while True:
                item = await queue.get()
                yield {"event": item["event"], "data": json.dumps(item)}
                if item["event"] == "done":
                    break
        finally:
            cancel.set()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()

    return EventSourceResponse(events())


@router.get("")
async def list_projects() -> list[dict]:
    return store.list_projects()


@router.post("", status_code=201)
async def create_project(request: CreateProject) -> dict:
    return store.create(request.title)


@router.post("/examples/energy")
async def energy_example() -> dict:
    from scripts.create_demo_project import create_demo
    return await create_demo(store, validate=False)


@router.get("/{project_id}")
async def get_project(project_id: str) -> dict:
    return store.view(project_id)


@router.post("/{project_id}/dataset")
async def upload_dataset(project_id: str, csv_file: UploadFile = File(...), description: str = Form("")) -> dict:
    directory = store.project_dir(project_id)
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        path = Path(temporary) / "input.csv"
        size = 0
        with path.open("wb") as output:
            while chunk := await csv_file.read(1024 * 1024):
                size += len(chunk)
                if size > config.max_upload_size_bytes:
                    raise HTTPException(413, "CSV exceeds the 100 MB input limit")
                output.write(chunk)
        if not size:
            raise HTTPException(422, "CSV is empty")
        await asyncio.to_thread(import_csv, store, path, project_id, csv_file.filename or "data.csv", description)
    await changed(project_id)
    return store.view(project_id)


@router.post("/{project_id}/chat")
async def build_project(project_id: str, request: BuildRequest) -> EventSourceResponse:
    store.dataset_path(project_id)
    if request.description is not None:
        store.describe(project_id, request.description)
    async def update(emit: Any, cancel: threading.Event) -> None:
        try:
            await service.build(project_id, request.query, emit, cancel)
        finally:
            await changed(project_id)
    return stream_operation(update)


@router.post("/{project_id}/revisions/{revision_id}/run")
async def run_revision(project_id: str, revision_id: str, request: RunRequest) -> EventSourceResponse:
    store.revision(project_id, revision_id)
    async def update(emit: Any, cancel: threading.Event) -> None:
        try:
            await service.rerun(project_id, revision_id, request.parameters, emit, cancel)
        finally:
            await changed(project_id)
    return stream_operation(update)


@router.post("/{project_id}/runs/{run_id}/cancel")
async def cancel_run(project_id: str, run_id: str) -> dict:
    store.run(project_id, run_id)
    cancel = service.cancellations.get(run_id)
    if cancel:
        cancel.set()
    return {"cancel_requested": bool(cancel)}


@router.post("/{project_id}/accept")
async def accept_revision(project_id: str, request: AcceptRequest) -> dict:
    store.accept(project_id, request.run_id, request.cleanup_confirmed)
    await changed(project_id)
    return store.view(project_id)


@router.post("/{project_id}/revisions/{revision_id}/rollback")
async def rollback_revision(project_id: str, revision_id: str) -> dict:
    store.rollback(project_id, revision_id)
    await asyncio.to_thread(Workspaces(store).validate_presentation, project_id)
    await changed(project_id)
    return store.view(project_id)


@router.get("/{project_id}/runs/{run_id}/tables/{output_name}")
async def export_table(project_id: str, run_id: str, output_name: str) -> FileResponse:
    run = store.run(project_id, run_id)
    revision = store.revision(project_id, run.revision_id)
    names = {w.output for w in revision.dashboard.widgets if w.kind == "table"}
    if run.status != "succeeded" or output_name not in names:
        raise HTTPException(404, "Table output not found")
    return FileResponse(store.run_dir(project_id, run_id) / "output" / f"{output_name}.csv", media_type="text/csv", filename=f"{output_name}.csv")


@router.get("/{project_id}/export")
async def export_project(project_id: str, include_data: bool = True, revision_id: str | None = None) -> FileResponse:
    from backend.services.export_service import ExportService
    try:
        path = await asyncio.to_thread(ExportService(store).export, project_id, include_data, revision_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/{project_id}/workspace")
async def get_workspace(project_id: str) -> dict:
    return Workspaces(store).get(project_id)


@router.patch("/{project_id}/workspace")
async def edit_workspace(project_id: str, request: WorkspaceEdit) -> dict:
    workspace = Workspaces(store)
    current = workspace.get(project_id)
    document = request.document or WorkspaceDocument.model_validate(current["document"])
    workspace.write(project_id, request.expected_version, document, request.action)
    await asyncio.to_thread(workspace.validate_presentation, project_id)
    await changed(project_id)
    return store.view(project_id)


@router.post("/{project_id}/stages/{stage_id}/delete")
async def delete_stage(project_id: str, stage_id: str, request: DeleteStage) -> dict:
    result = Workspaces(store).delete(project_id, stage_id, request.expected_version, request.confirmed)
    if not request.confirmed:
        return result
    await asyncio.to_thread(Workspaces(store).validate_presentation, project_id)
    await changed(project_id)
    return store.view(project_id)


@router.patch("/{project_id}/context")
async def describe_project(project_id: str, request: Request) -> dict:
    body = await request.json()
    description = str(body.get("description", ""))
    if len(description) > 12000:
        raise ValueError("Business context exceeds 12000 characters")
    store.describe(project_id, description)
    events.publish(project_id)
    return store.view(project_id)


@router.post("/{project_id}/run", status_code=202)
async def run_workspace(project_id: str, request: WorkspaceRun) -> dict:
    return jobs.create(project_id, request.expected_version, request.parameters)


@router.get("/{project_id}/jobs")
async def list_jobs(project_id: str) -> list[dict]:
    return jobs.list(project_id)


@router.get("/{project_id}/jobs/{job_id}")
async def get_job(project_id: str, job_id: str) -> dict:
    return jobs.get(project_id, job_id)


@router.post("/{project_id}/jobs/{job_id}/cancel")
async def cancel_job(project_id: str, job_id: str) -> dict:
    return jobs.cancel(project_id, job_id)


@router.get("/{project_id}/events")
async def project_events(project_id: str, request: Request) -> StreamingResponse:
    store.get(project_id)
    async def stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
        events.subscribers.setdefault(project_id, set()).add(queue)
        queue.put_nowait(events.sequences.get(project_id, 0))
        try:
            while not await request.is_disconnected():
                try:
                    sequence = await asyncio.wait_for(queue.get(), 15)
                    yield f"id: {sequence}\ndata: {json.dumps({'sequence': sequence})}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            events.subscribers[project_id].discard(queue)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get("/{project_id}/target")
async def target_status(project_id: str) -> dict:
    status = targets.status(project_id)
    state = await targets.state(project_id)
    if state:
        status.update(applied_revision=state["revision"]["revision_id"] if state["revision"] else None,
            pending=state["pending"], input_mode=state["input_mode"], last_error=state["last_error"],
            active_run=bool(state["active_run"]))
    return status


@router.post("/{project_id}/target/{action}")
async def target_control(project_id: str, action: Literal["start", "stop", "restart"], request: Request) -> dict:
    if action in {"stop", "restart"}:
        await targets.stop(project_id)
    if action in {"start", "restart"}:
        await targets.start(project_id, str(request.base_url).rstrip("/"))
    events.publish(project_id)
    return await target_status(project_id)


@internal_router.post("/{project_id}/execute")
async def execute_target(project_id: str, body: TargetExecution, request: Request) -> StreamingResponse:
    try:
        target = targets.authorize(project_id, request.headers.get("X-Target-Token", ""))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    revision = store.revision(project_id, body.revision_id)
    source = (target.root / body.input).resolve()
    if not source.is_relative_to(target.root) or not source.is_file() or source.stat().st_size > config.max_upload_size_bytes:
        raise HTTPException(422, "Invalid target input")
    run_id = str(body.run_id)
    cache = target.root / "runs" / str(body.cache_run_id) / "output" if body.cache_run_id else None
    cancel = threading.Event()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    target_cancellations[(project_id, run_id)] = cancel

    async def produce() -> None:
        try:
            queue.put_nowait({"event": "status", "message": "Waiting for the execution slot"})
            response: dict[str, Any]
            def relay(event: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            async with service.lock:
                if cancel.is_set():
                    response = {"success": False, "cancelled": True, "error": "Run cancelled"}
                else:
                    target_running.add((project_id, run_id))
                    response = await service.runner.run(revision, source, body.parameters, target.root / "runs" / run_id,
                        cancel, cache, relay)
            queue.put_nowait({"event": "result", "response": response})
        except asyncio.CancelledError:
            queue.put_nowait({"event": "result", "response": {"success": False, "cancelled": True, "error": "Run cancelled"}})
        except Exception as exc:
            queue.put_nowait({"event": "result", "response": {"success": False, "error": str(exc)}})
        finally:
            target_running.discard((project_id, run_id))
            events.publish(project_id)

    async def stream() -> AsyncIterator[str]:
        task = asyncio.create_task(produce())
        target_tasks[(project_id, run_id)] = task
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event, allow_nan=False) + "\n"
                if event["event"] == "result":
                    break
        finally:
            cancel.set()
            target_cancellations.pop((project_id, run_id), None)
            target_tasks.pop((project_id, run_id), None)
            try:
                await asyncio.wait_for(asyncio.shield(task), 5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
    return StreamingResponse(stream(), media_type="application/x-ndjson")


@internal_router.post("/{project_id}/cancel/{run_id}")
async def cancel_target(project_id: str, run_id: str, request: Request) -> dict:
    try:
        targets.authorize(project_id, request.headers.get("X-Target-Token", ""))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    event = target_cancellations.get((project_id, run_id))
    if event:
        event.set()
        if (project_id, run_id) not in target_running:
            task = target_tasks.get((project_id, run_id))
            if task:
                task.cancel()
    return {"cancel_requested": event is not None}
