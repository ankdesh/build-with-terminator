"""FastAPI application entrypoint for WPS-AI data analysis server."""

import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.exceptions import WPSAIBaseException
from backend.routes.chat_routes import router as chat_router
from backend.routes.session_routes import router as session_router
from config import config

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wps-ai")

app = FastAPI(
    title="WPS-AI Data Analysis Agent",
    description="Lightweight air-gapped data analysis agent with interactive UI",
    version="0.1.0",
)

# Enable CORS for local development and embedded webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API route modules
app.include_router(session_router)
app.include_router(chat_router)


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
        target = static_path / full_path
        if target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(static_path / "index.html"))
else:
    logger.info("Static frontend not yet built at %s. API-only mode active.", static_path)
