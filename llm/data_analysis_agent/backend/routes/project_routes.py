"""Project API and event streaming for the local authoring application."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.services.data_profiler import DataProfiler
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from config import config

router = APIRouter(prefix="/api/projects", tags=["projects"])
store = ProjectStore(Path(os.environ.get("WPS_PROJECTS_DIR", str(config.sessions_dir.parent / "projects"))))
service = ProjectService(store)


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
    if service.lock.locked():
        raise HTTPException(409, "Another pipeline operation is active")
    from scripts.create_demo_project import create_demo
    async with service.lock:
        return await create_demo(store)


@router.get("/{project_id}")
async def get_project(project_id: str) -> dict:
    return store.view(project_id)


@router.post("/{project_id}/dataset")
async def upload_dataset(project_id: str, csv_file: UploadFile = File(...), description: str = Form("")) -> dict:
    if service.lock.locked():
        raise HTTPException(409, "Wait for the current operation or cancel it before replacing data")
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
        profile = await asyncio.to_thread(DataProfiler().profile_csv, project_id, path.read_bytes(), csv_file.filename or "data.csv", description)
        store.save_dataset(project_id, path, Path(csv_file.filename or "data.csv").name, profile.model_dump(), description)
    return store.view(project_id)


@router.post("/{project_id}/chat")
async def build_project(project_id: str, request: BuildRequest) -> EventSourceResponse:
    store.dataset_path(project_id)
    if service.lock.locked():
        raise HTTPException(409, "Another pipeline operation is active")
    if request.description is not None:
        store.describe(project_id, request.description)
    return stream_operation(lambda emit, cancel: service.build(project_id, request.query, emit, cancel))


@router.post("/{project_id}/revisions/{revision_id}/run")
async def run_revision(project_id: str, revision_id: str, request: RunRequest) -> EventSourceResponse:
    store.revision(project_id, revision_id)
    if service.lock.locked():
        raise HTTPException(409, "Another pipeline operation is active")
    return stream_operation(lambda emit, cancel: service.rerun(project_id, revision_id, request.parameters, emit, cancel))


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
    return store.view(project_id)


@router.post("/{project_id}/revisions/{revision_id}/rollback")
async def rollback_revision(project_id: str, revision_id: str) -> dict:
    if service.lock.locked():
        raise HTTPException(409, "Wait for the current pipeline operation before rollback")
    store.rollback(project_id, revision_id)
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
async def export_project(project_id: str, include_data: bool = True) -> FileResponse:
    from backend.services.export_service import ExportService
    try:
        path = await asyncio.to_thread(ExportService(store).export, project_id, include_data)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)
