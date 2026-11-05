"""
Desktop application launcher for WPS-AI.

Starts the FastAPI server with embedded frontend assets, verifies health,
and automatically opens the local user interface in the system default browser.
"""

import argparse
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import uvicorn

from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] launcher: %(message)s",
)
logger = logging.getLogger("launcher")


def reserve_server_socket(host: str, port: int) -> socket.socket:
    """Bind the exact requested port and hold it until server shutdown."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(128)
    except OSError:
        listener.close()
        raise
    return listener


def wait_for_server(url: str, timeout_seconds: float = 10.0) -> bool:
    """Poll the health check endpoint until the server is ready to accept requests."""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def import_startup_csv(source: Path) -> str:
    """Create a project from a CSV and return its builder navigation path."""
    from backend.routes.project_routes import store
    from backend.services.dataset_import import import_csv
    view = import_csv(store, source.expanduser().resolve())
    return f"/?project={view['project']['id']}&view=data"


def main() -> None:
    parser = argparse.ArgumentParser(description="WPS-AI Desktop Application Launcher")
    parser.add_argument("--host", default=config.server_host, help="Bind address; use 0.0.0.0 for LAN access (default: config.json)")
    parser.add_argument("--port", type=int, default=config.server_port, help="Exact bind port (default: config.json); fail if unavailable")
    parser.add_argument("--headless", action="store_true", help="Start server without launching browser")
    parser.add_argument("--log-level", default="info", help="Uvicorn log level (default: info)")
    parser.add_argument("--csv", type=Path, metavar="FILE", help="Load a CSV into a new project at startup (no model call or calculation)")
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.exit(2, "Port must be between 1 and 65535.\n")
    host, port = args.host, args.port
    try:
        listener = reserve_server_socket(host, port)
    except OSError as exc:
        parser.exit(2, f"Cannot bind {host}:{port}: {exc}. Stop the service using this port or change server_port/--port. No other port was selected.\n")

    # Targets must use the actual bind address, including a command-line override.
    os.environ["WPS_BIND_HOST"] = args.host
    initial_path = "/"
    if args.csv is not None:
        try:
            initial_path = import_startup_csv(args.csv)
        except Exception as exc:
            listener.close()
            parser.exit(2, f"Cannot load startup CSV: {exc}\n")

    local_host = "127.0.0.1" if host == "0.0.0.0" else host
    server_url = f"http://{local_host}:{port}"
    builder_url = server_url + initial_path

    logger.info("==================================================")
    logger.info("              WPS-AI DATA ANALYST                 ")
    logger.info("==================================================")
    logger.info("Bind address:  %s:%s", host, port)
    if host == "0.0.0.0":
        logger.info("LAN clients:   http://<server-IP>:%s", port)
    logger.info("Server Target: %s", server_url)
    logger.info("Model:         %s", config.openai_model_name)
    logger.info("API Endpoint:  %s", config.openai_api_base)
    logger.info("Sessions Dir:  %s", config.sessions_dir)
    logger.info("==================================================")

    # Configure Uvicorn server instance
    uvicorn_config = uvicorn.Config(
        "backend.app:app",
        host=host,
        port=port,
        log_level=args.log_level.lower(),
        access_log=False,
        timeout_graceful_shutdown=3,
    )
    server = uvicorn.Server(uvicorn_config)

    # Start server in daemon thread
    server_thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    server_thread.start()

    # Wait for server readiness
    logger.info("Waiting for local server initialization...")
    if wait_for_server(server_url):
        logger.info("Server is live and healthy at %s", server_url)
        logger.info("Builder: %s", builder_url)
        if not args.headless:
            logger.info("Launching user interface in system browser...")
            try:
                webbrowser.open(builder_url)
            except Exception as e:
                logger.warning("Could not launch browser automatically: %s", e)
                logger.info("Please open your browser manually at %s", builder_url)
    else:
        server.should_exit = True
        server_thread.join(timeout=3.0)
        listener.close()
        parser.exit(1, "Server failed to start on the requested port.\n")

    try:
        # Keep main thread alive while server runs
        while server_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Shutting down WPS-AI server gracefully...")
        server.should_exit = True
        server_thread.join(timeout=3.0)
        logger.info("Shutdown complete.")
        sys.exit(0)
    finally:
        listener.close()


if __name__ == "__main__":
    main()
