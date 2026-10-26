"""FastAPI application entrypoint for WPS-AI data analysis server."""

import logging
from pathlib import Path
from typing import Awaitable, Callable
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from backend.exceptions import WPSAIBaseException
from backend.routes.project_routes import router as project_router
from backend.routes.session_routes import router as session_router
from backend.routes.chat_routes import export_table_csv
from config import config
from pipeline_core.http_policy import CONTENT_SECURITY_POLICY

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wps-ai")

app = FastAPI(
    title="WPS-AI Data Analysis Studio",
    description="Chat-built reusable pipelines and offline dashboards",
    version="0.2.0",
)

# Enable CORS for local development and embedded webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

# Include API route modules
app.include_router(session_router)
app.include_router(project_router)
# Retain data-only export compatibility. The legacy chat executor is not routed.
app.add_api_route("/api/sessions/{session_id}/export-csv", export_table_csv, methods=["POST"])


@app.middleware("http")
async def local_origin_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Reject cross-site requests to the local authoring service."""
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/"), "http://localhost:3000", "http://127.0.0.1:3000"}
    if origin and origin not in allowed:
        return JSONResponse(status_code=403, content={"detail": "Cross-site access to this local application is blocked"})
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


@app.exception_handler(ValueError)
async def validation_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def missing_project(request: Request, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(WPSAIBaseException)
async def wps_exception_handler(request: Request, exc: WPSAIBaseException) -> JSONResponse:
    """Handle custom domain exceptions uniformly."""
    logger.error("Domain exception: %s", exc)
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "details": exc.details},
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for application and readiness monitoring."""
    return {
        "status": "healthy",
        "app": "WPS-AI",
        "mode": "builder",
        "model": config.openai_model_name,
        "api_base_configured": bool(config.openai_api_base),
    }


# Mount static assets if compiled frontend exists
static_path = config.static_dir
if static_path.exists() and (static_path / "index.html").exists():
    logger.info("Serving compiled frontend from %s", static_path)
    app.mount("/assets", StaticFiles(directory=str(static_path / "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve SPA index.html for frontend routing."""
        target = (static_path / full_path).resolve()
        if target.is_relative_to(static_path.resolve()) and target.exists() and target.is_file():
            return FileResponse(str(target))
        response = FileResponse(str(static_path / "index.html"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
else:
    logger.info("Static frontend not yet built at %s. API-only mode active.", static_path)
