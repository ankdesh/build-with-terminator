"""Same-origin HTTP interface shared by both dashboard launch modes."""

import asyncio
from contextlib import asynccontextmanager
import hmac
import json
from pathlib import Path
import tempfile
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from pipeline_core.http_policy import CONTENT_SECURITY_POLICY
from pipeline_core.runtime import RuntimeApplication


class Controls(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


def create_runtime_app(application: RuntimeApplication, static: Path, control_token: str | None = None,
                       allowed_hosts: list[str] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await application.close()

    app = FastAPI(title="Saved Data Analysis Dashboard", docs_url=None, redoc_url=None,
        openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost"])
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
        return {"status": "healthy", "mode": "live" if application.live else "runtime", "model_required": False}

    @app.get("/api/runtime/state")
    async def state() -> dict[str, Any]:
        return application.view()

    @app.get("/api/runtime/events")
    async def events(request: Request) -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            sequence = -1
            while not await request.is_disconnected():
                async with application.changed:
                    if sequence == application.sequence:
                        try:
                            await asyncio.wait_for(application.changed.wait(), 15)
                        except asyncio.TimeoutError:
                            yield ": heartbeat\n\n"
                            continue
                    sequence = application.sequence
                yield f"id: {sequence}\ndata: {json.dumps({'sequence': sequence})}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    def ready() -> None:
        if application.lock.locked():
            raise HTTPException(409, "Another dashboard run is active")

    @app.post("/api/runtime/run")
    async def run(controls: Controls) -> dict[str, Any]:
        ready()
        if not application.state.get("input"):
            raise HTTPException(422, "Upload a CSV first")
        result = await application.execute(Path(application.state["input"]), application.state["dataset_name"] or "data.csv",
            controls.parameters, application.desired_revision, snapshot=application.attempted_snapshot)
        result["state"] = application.view()
        return result

    @app.post("/api/runtime/upload")
    async def upload(csv_file: UploadFile = File(...)) -> dict[str, Any]:
        ready()
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
            result = await application.execute(path, Path(csv_file.filename or "data.csv").name, {},
                application.desired_revision, "replacement" if application.live else "local",
                snapshot=application.attempted_snapshot)
        result["state"] = application.view()
        return result

    @app.post("/api/runtime/use-builder-data")
    async def use_builder_data() -> dict[str, Any]:
        ready()
        if not application.live or not application.builder_input:
            raise HTTPException(422, "Builder data is not available")
        path, name = application.builder_input
        result = await application.execute(path, name, {}, application.desired_revision, "builder",
            snapshot=application.attempted_snapshot)
        result["state"] = application.view()
        return result

    @app.post("/api/runtime/cancel")
    async def cancel() -> dict[str, Any]:
        if application.cancel:
            application.cancel.set()
        return {"cancel_requested": application.cancel is not None}

    @app.get("/api/runtime/tables/{output_name}")
    async def table(output_name: str) -> FileResponse:
        display = application.state.get("display_run")
        revision = application.revision
        if not display or not revision or output_name not in {w.output for w in revision.dashboard.widgets if w.kind == "table"}:
            raise HTTPException(404, "Table not found")
        return FileResponse(application.root / "runs" / display["run_id"] / "output" / f"{output_name}.csv",
            media_type="text/csv", filename=f"{output_name}.csv")

    if control_token:
        @app.post("/internal/snapshot")
        async def snapshot(request: Request) -> dict[str, Any]:
            if not hmac.compare_digest(request.headers.get("X-Target-Token", ""), control_token):
                raise HTTPException(403, "Invalid target control token")
            await application.update(await request.json())
            return {"sequence": application.sequence}

    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    async def dashboard() -> FileResponse:
        index = static / "index.html"
        if not index.is_file():
            index = static / "runtime.html"
        if not index.is_file():
            raise HTTPException(503, "Build the runtime frontend with pnpm exec vite build --mode runtime")
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    return app
