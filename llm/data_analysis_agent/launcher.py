"""
Desktop application launcher for WPS-AI.

Starts the FastAPI server with embedded frontend assets, verifies health,
and automatically opens the local user interface in the system default browser.
"""

import argparse
import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import uvicorn

from config import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] launcher: %(message)s",
)
logger = logging.getLogger("launcher")


def is_port_in_use(host: str, port: int) -> bool:
    """Check whether a TCP port is currently open and in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_available_port(host: str, starting_port: int) -> int:
    """Find the next available TCP port if the default port is already bound."""
    port = starting_port
    while port < starting_port + 50:
        if not is_port_in_use(host, port):
            return port
        port += 1
    return starting_port


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


def main() -> None:
    parser = argparse.ArgumentParser(description="WPS-AI Desktop Application Launcher")
    parser.add_argument("--host", default=config.server_host, help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=config.server_port, help="Bind port (default: 8080)")
    parser.add_argument("--headless", action="store_true", help="Start server without launching browser")
    parser.add_argument("--log-level", default="info", help="Uvicorn log level (default: info)")
    args = parser.parse_args()

    host = args.host
    port = find_available_port(host, args.port)
    server_url = f"http://{host}:{port}"

    logger.info("==================================================")
    logger.info("              WPS-AI DATA ANALYST                 ")
    logger.info("==================================================")
    logger.info("Server Target: %s", server_url)
    logger.info("Model:         %s", config.openai_model_name)
    logger.info("API Endpoint:  %s", config.openai_api_base or "(Not configured - mock fallback active)")
    logger.info("Sessions Dir:  %s", config.sessions_dir)
    logger.info("==================================================")

    # Configure Uvicorn server instance
    uvicorn_config = uvicorn.Config(
        "backend.app:app",
        host=host,
        port=port,
        log_level=args.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)

    # Start server in daemon thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server readiness
    logger.info("Waiting for local server initialization...")
    if wait_for_server(server_url):
        logger.info("Server is live and healthy at %s", server_url)
        if not args.headless:
            logger.info("Launching user interface in system browser...")
            try:
                webbrowser.open(server_url)
            except Exception as e:
                logger.warning("Could not launch browser automatically: %s", e)
                logger.info("Please open your browser manually at %s", server_url)
    else:
        logger.error("Server failed to respond to health check within timeout.")

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


if __name__ == "__main__":
    main()
