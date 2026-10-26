"""Dashboard-only runtime API. Never imports model clients or builder services."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from pipeline_core.bundle import load_bundle
from pipeline_core.engine import fingerprint
from pipeline_core.models import RunRecord, now
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.validation import validate_parameters
from pipeline_core.http_policy import CONTENT_SECURITY_POLICY


class Controls(BaseModel):
    parameters: dict = Field(default_factory=dict)


class OfflineApplication:
    """Keep the last successful input and dashboard through failed refreshes."""

    def __init__(self, package: Path, state_dir: Path, runner: ProcessRunner | None = None) -> None:
        self.revision, self.manifest = load_bundle(package)
        self.package, self.root = package, state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = state_dir / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"input": None, "dataset_name": None, "display_run": None, "last_error": None}
        self.runner = runner or ProcessRunner()
        self.lock = asyncio.Lock()
        self.cancel: threading.Event | None = None
        self.events: list[dict] = []
        if not self.state["input"] and (package / "input" / "data.csv").is_file():
            destination = self.copy_input(package / "input" / "data.csv")
            self.state.update(input=str(destination), dataset_name=self.manifest["dataset_name"])
            self.save()
        if self.state.get("active_run"):
            self.state.update(active_run=None, last_error="The previous run was interrupted. The last successful dashboard is retained.")
            self.save()

    def copy_input(self, source: Path) -> Path:
        directory = self.root / "datasets"
        directory.mkdir(exist_ok=True)
        destination = directory / f"{fingerprint(source)}.csv"
        if not destination.exists():
            shutil.copyfile(source, destination)
        return destination

    def save(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, allow_nan=False))
        temporary.replace(self.state_path)

    def view(self) -> dict:
        return {"mode": "runtime", "revision": self.revision.model_dump(),
            "display_run": self.state["display_run"], "dataset_name": self.state["dataset_name"],
            "has_input": bool(self.state["input"]), "last_error": self.state["last_error"],
            "active_run": self.state.get("active_run"), "events": self.events[-80:]}

    async def execute(self, candidate: Path, name: str, parameters: dict) -> dict:
        if self.lock.locked():
            raise HTTPException(409, "Another pipeline run is active")
        async with self.lock:
            resolved = validate_parameters(self.revision, parameters)
            run = RunRecord(revision_id=self.revision.revision_id, dataset_name=name,
                input_hash=fingerprint(candidate), parameters=resolved)
            self.cancel = threading.Event()
            self.events = []
            self.state["active_run"] = run.model_dump()
            self.save()
            loop = asyncio.get_running_loop()
            previous = self.state["display_run"]
            cache = self.root / "runs" / previous["run_id"] / "output" if previous else None
            def relay(event: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(self.events.append, event)
            try:
                response = await self.runner.run(self.revision, candidate, resolved, self.root / "runs" / run.run_id,
                    self.cancel, cache, relay)
                run.status = "succeeded" if response["success"] else "cancelled" if response.get("cancelled") else "failed"
                run.finished_at = now()
                run.error = response.get("error")
                run.result = response.get("result")
                if response["success"]:
                    input_path = self.copy_input(candidate)
                    self.state.update(input=str(input_path), dataset_name=name, display_run=run.model_dump(), last_error=None)
                else:
                    self.state["last_error"] = run.error
                (self.root / "runs" / run.run_id / "record.json").write_text(run.model_dump_json(indent=2))
                self.state["active_run"] = None
                return {"run": run.model_dump(), "state": self.view()}
            except asyncio.CancelledError:
                if self.cancel:
                    self.cancel.set()
                self.state["last_error"] = "Run cancelled"
                raise
            finally:
                self.state["active_run"] = None
                self.save()
                self.cancel = None


def create_app(package: Path, state_dir: Path | None = None, runner: ProcessRunner | None = None) -> FastAPI:
    revision, _ = load_bundle(package)
    root = state_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "WPSAnalysis" / revision.revision_id
    application = OfflineApplication(package, root, runner)
    app = FastAPI(title="Saved Data Analysis Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.state.application = application

    @app.middleware("http")
    async def origin_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(status_code=403, content={"detail": "Cross-site access is blocked"})
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response

    @app.exception_handler(ValueError)
    async def invalid_input(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "healthy", "mode": "runtime", "model_required": False}

    @app.get("/api/runtime/state")
    async def state() -> dict[str, Any]:
        return application.view()

    @app.post("/api/runtime/run")
    async def run(controls: Controls) -> dict[str, Any]:
        if not application.state["input"]:
            raise HTTPException(422, "Upload a CSV first")
        return await application.execute(Path(application.state["input"]), str(application.state["dataset_name"] or "data.csv"), controls.parameters)

    @app.post("/api/runtime/upload")
    async def upload(csv_file: UploadFile = File(...)) -> dict[str, Any]:
        if application.lock.locked():
            raise HTTPException(409, "Another pipeline run is active")
        with tempfile.TemporaryDirectory(dir=application.root) as temporary:
            path = Path(temporary) / "input.csv"
            total = 0
            with path.open("wb") as stream:
                while chunk := await csv_file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 100 * 1024 * 1024:
                        raise HTTPException(413, "CSV exceeds the 100 MB input limit")
                    stream.write(chunk)
            if not total:
                raise HTTPException(422, "CSV is empty")
            return await application.execute(path, Path(csv_file.filename or "data.csv").name, {})

    @app.post("/api/runtime/cancel")
    async def cancel() -> dict[str, Any]:
        if application.cancel:
            application.cancel.set()
        return {"cancel_requested": application.cancel is not None}

    @app.get("/api/runtime/tables/{output_name}")
    async def table(output_name: str) -> FileResponse:
        display = application.state["display_run"]
        if not display or output_name not in {w.output for w in revision.dashboard.widgets if w.kind == "table"}:
            raise HTTPException(404, "Table not found")
        return FileResponse(application.root / "runs" / display["run_id"] / "output" / f"{output_name}.csv", media_type="text/csv", filename=f"{output_name}.csv")

    static = package / "static"
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})

    return app
