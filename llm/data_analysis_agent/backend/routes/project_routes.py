"""Project API and event streaming for the local authoring application."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, AsyncIterator, Literal, cast
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.services.dataset_import import import_csv
from backend.services.chat_service import ChatService, redact, results_preview
from backend.services.chat_store import ChatStore, context_for, public_item
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
chat_followups: dict[str, asyncio.Task[None]] = {}
chat_action_lock = asyncio.Lock()


class CreateProject(BaseModel):
    title: str = Field(default="New analysis", min_length=1, max_length=200)


class BuildRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    description: str | None = Field(default=None, max_length=12000)
    stage_id: str | None = Field(default=None, max_length=200)
    expected_version: int | None = None


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
    async def update(emit: Any, cancel: threading.Event) -> None:
        try:
            await ChatService(service).respond(project_id, request.query, request.stage_id,
                request.expected_version, emit, cancel)
        finally:
            events.publish(project_id)
    return stream_operation(update)


@router.get('/{project_id}/chat/items/{item_id}')
async def chat_item(project_id: str, item_id: str) -> dict:
    return cast(dict, redact(public_item(ChatStore(store).get(project_id, item_id), os.environ.get('WPS_DEVELOPER_MODE') == '1')))


@router.post('/{project_id}/chat/items/{item_id}/apply')
async def apply_chat_item(project_id: str, item_id: str) -> dict:
    item = ChatStore(store).apply(project_id, item_id)
    await asyncio.to_thread(Workspaces(store).validate_presentation, project_id)
    await changed(project_id)
    return public_item(item)


@router.post('/{project_id}/chat/items/{item_id}/discard')
async def discard_chat_item(project_id: str, item_id: str) -> dict:
    item = ChatStore(store).discard(project_id, item_id)
    events.publish(project_id)
    return public_item(item)


@router.post('/{project_id}/chat/items/{item_id}/run', status_code=202)
async def run_and_reask(project_id: str, item_id: str) -> dict:
    from backend.services.workspace_service import WorkspaceConflict
    async with chat_action_lock:
        items = ChatStore(store)
        item = items.get(project_id, item_id)
        if item.get('job_id'):
            return jobs.get(project_id, item['job_id'])
        if item.get('run_skipped'):
            raise ValueError('Run was skipped. Ask the question again to request another run.')
        if not ((item['kind'] == 'proposal' and item['status'] == 'applied')
                or (item['kind'] == 'needs_run' and item['status'] == 'pending')):
            raise ValueError('This chat action cannot be run')
        workspace = Workspaces(store).get(project_id)
        if workspace['version'] != item.get('applied_version', item['version']) or store.get(project_id)['dataset_hash'] != item['input_hash']:
            raise WorkspaceConflict('The workspace or input changed. Ask your question again before running.')
        if item['kind'] == 'needs_run':
            context_for(workspace['document'], item['context']['stage_id'], bool(item['input_hash']))
        job = jobs.create(project_id, workspace['version'], {}, expected_input_hash=item['input_hash'])
        item.update(job_id=job['id'], run_status='queued')
        items.put(project_id, item)
        async def finish() -> None:
            try:
                while True:
                    current_job = jobs.get(project_id, job['id'])
                    if current_job['status'] not in {'queued', 'running'}: break
                    await asyncio.sleep(.1)
                if current_job['status'] != 'succeeded':
                    raise ValueError(current_job.get('error') or 'Run did not succeed')
                item['run_status'] = 'answering'
                items.put(project_id, item)
                await ChatService(service).respond(project_id, item['query'], item['context']['stage_id'], None,
                    lambda event: events.publish(project_id), threading.Event(), answer_only=True,
                    run_id=current_job['run_id'], captured_context=item['context'])
                item['run_status'] = 'answered'
            except asyncio.CancelledError:
                item.update(run_status='interrupted', run_error='Builder stopped before the follow-up completed.')
                raise
            except Exception as exc:
                item.update(run_status='failed', run_error=str(exc))
                store.message(project_id, 'assistant', f'Run and ask again stopped: {exc}',
                    {'kind': 'error', 'context': item['context'], 'item_id': item_id})
            finally:
                items.put(project_id, item)
                events.publish(project_id)
                chat_followups.pop(item_id, None)
        chat_followups[item_id] = asyncio.create_task(finish())
        return job


@router.get('/{project_id}/stages/{stage_id}/inspect')
async def inspect_stage(project_id: str, stage_id: str) -> dict:
    if os.environ.get('WPS_DEVELOPER_MODE') != '1':
        raise HTTPException(404, 'Developer inspection is disabled')
    from backend.services.run_diagnostics import collect_run_diagnostics
    from backend.services.chat_store import entities
    workspace = Workspaces(store).get(project_id)
    project = store.get(project_id)
    context = context_for(workspace['document'], stage_id, bool(project['dataset_hash']))
    stage = next(s for s in workspace['stages'] if s['id'] == stage_id)
    configuration = entities(workspace['document'])[stage_id]
    owners = {output: step for step in workspace['document']['steps'] for output in step['outputs']}
    producer = configuration if stage_id.startswith('step:') else owners.get(configuration.get('output'), {})
    declared = producer.get('parameters_used')
    controls = [p for p in workspace['document']['parameters'] if (producer and declared is None)
        or p['id'] in (declared or []) or (p.get('filter_column') and (producer.get('stage') == 'analysis' or p.get('filter_artifact') in stage['outputs']))]
    run = store.run(project_id, project['display_run_id']).model_dump() if project['display_run_id'] else None
    return cast(dict, redact({'context': context, 'workspace_version': workspace['version'], 'configuration': configuration,
        'source': configuration.get('code'), 'dependencies': stage['dependencies'], 'inputs': stage['inputs'],
        'outputs': stage['outputs'], 'controls': controls, 'saved_results': results_preview(run, store, project_id),
        'diagnostics': collect_run_diagnostics(store, project_id, secret=config.openai_api_key)}))


@router.get('/{project_id}/stages/{stage_id}/inspect.json')
async def download_inspection(project_id: str, stage_id: str) -> JSONResponse:
    data = await inspect_stage(project_id, stage_id)
    return JSONResponse(data, headers={'Content-Disposition': 'attachment; filename="stage-inspection.json"'})


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
async def target_status(project_id: str, request: Request) -> dict:
    status = targets.status(project_id)
    if status["url"]:
        # Use the host seen by this client, never the server's loopback address.
        status["url"] = str(request.url.replace(port=status["port"], path="", query=""))
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
        bind_host = os.environ.get("WPS_BIND_HOST", config.server_host)
        broker_host = "127.0.0.1" if bind_host == "0.0.0.0" else bind_host
        await targets.start(project_id, f"http://{broker_host}:{request.url.port or config.server_port}")
    events.publish(project_id)
    return await target_status(project_id, request)


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
