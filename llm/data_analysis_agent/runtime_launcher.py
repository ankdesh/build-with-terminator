"""Portable application launcher and frozen worker dispatch."""

import argparse
from pathlib import Path
import socket
import sys
import threading
import time
import webbrowser


def main() -> None:
    # Dispatch before importing the HTTP app. Worker code never loads a model client.
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from pipeline_core.worker import main as worker_main
        raise SystemExit(worker_main(sys.argv[2]))
    parser = argparse.ArgumentParser(description="Saved data analysis dashboard")
    default = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    parser.add_argument("--project", type=Path, default=default)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--verify", action="store_true", help="Verify the package and exit")
    args = parser.parse_args()
    from pipeline_core.bundle import load_bundle
    load_bundle(args.project)
    if args.verify:
        print("Bundle integrity and runtime compatibility verified")
        return
    from offline_app import create_app
    import uvicorn
    app = create_app(args.project, args.state_dir)
    with socket.socket() as reservation:
        try:
            reservation.bind(("127.0.0.1", args.port))
        except OSError:
            reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info"))
    if not args.headless:
        def open_browser() -> None:
            deadline = time.monotonic() + 15
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.1)
            if server.started:
                webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=open_browser, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
