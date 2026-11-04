"""Credential-free target process and authenticated live execution adapter."""

import asyncio
import json
from pathlib import Path
import socket
import sys
import threading
from typing import Any, Callable

import httpx

from pipeline_core.models import ProjectRevision
from pipeline_core.runtime import RuntimeApplication
from pipeline_core.runtime_http import create_runtime_app


class BrokerRunner:
    def __init__(self, base: str, token: str, root: Path) -> None:
        self.base, self.token, self.root = base, token, root

    async def run(self, revision: ProjectRevision, input_path: Path, parameters: dict[str, Any],
                  job_dir: Path, cancel: threading.Event, cache_dir: Path | None = None,
                  on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        headers = {"X-Target-Token": self.token}
        body = {"revision_id": revision.revision_id, "input": str(input_path.relative_to(self.root)),
            "run_id": job_dir.name, "parameters": parameters,
            "cache_run_id": cache_dir.parent.name if cache_dir else None}
        async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
            async def watch_cancel() -> None:
                while not cancel.is_set():
                    await asyncio.sleep(.1)
                try:
                    await client.post(f"{self.base}/cancel/{job_dir.name}", headers=headers, timeout=5)
                except httpx.HTTPError:
                    pass
            watcher = asyncio.create_task(watch_cancel())
            try:
                async with client.stream("POST", f"{self.base}/execute", headers=headers, json=body) as response:
                    if response.status_code != 200:
                        return {"success": False, "error": (await response.aread()).decode()}
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get("event") == "result":
                            return dict(event["response"])
                        if on_event:
                            on_event(event)
                return {"success": False, "error": "Builder execution connection closed"}
            except httpx.HTTPError as exc:
                return {"success": False, "error": f"Builder execution service is unavailable: {exc}"}
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)


def main() -> None:
    # Bootstrap credentials travel only through the parent-owned pipe.
    settings = json.loads(sys.stdin.buffer.readline())
    root = Path(settings["root"])
    application = RuntimeApplication(root, runner=BrokerRunner(settings["broker"], settings["token"], root), live=True)
    app = create_runtime_app(application, Path(settings["static"]), settings["token"])
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=settings["port"], access_log=False,
        log_level="warning", timeout_graceful_shutdown=3))
    def parent_watch() -> None:
        sys.stdin.buffer.read()
        server.should_exit = True
    threading.Thread(target=parent_watch, daemon=True).start()
    inherited = socket.socket(fileno=settings["socket"])
    server.run(sockets=[inherited])


if __name__ == "__main__":
    main()
