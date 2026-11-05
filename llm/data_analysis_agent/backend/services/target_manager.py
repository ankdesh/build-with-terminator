"""Own one dashboard process per opened project."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from typing import Any

import httpx

from config import config
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import Workspaces
from pipeline_core.runtime import link_or_copy
from pipeline_core.workspace import calculation_hash


@dataclass
class Target:
    process: subprocess.Popen[bytes]
    token: str
    port: int
    root: Path
    error: str | None = None
    connect_host: str = "127.0.0.1"

    @property
    def url(self) -> str:
        return f"http://{self.connect_host}:{self.port}"


class TargetManager:
    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.targets: dict[str, Target] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.sync_locks: dict[str, asyncio.Lock] = {}
        self.start_port = int(os.environ.get("WPS_TARGET_PORT_START", "8100"))
        self.end_port = int(os.environ.get("WPS_TARGET_PORT_END", "8199"))
        if not 1024 <= self.start_port <= self.end_port <= 65535:
            raise ValueError("Target ports must be a range between 1024 and 65535")

    def status(self, project_id: str) -> dict[str, Any]:
        self.store.get(project_id)
        target = self.targets.get(project_id)
        if not target:
            return {"status": "stopped", "url": None, "port": None, "error": None}
        running = target.process.poll() is None
        return {"status": "running" if running else "failed", "url": target.url if running else None,
            "port": target.port, "error": target.error or (None if running else "Target process exited. Select Restart.")}

    async def start(self, project_id: str, builder_url: str) -> dict[str, Any]:
        async with self.locks.setdefault(project_id, asyncio.Lock()):
            if self.status(project_id)["status"] == "running":
                return self.status(project_id)
            self.store.get(project_id)
            root = self.store.project_dir(project_id).resolve() / "target"
            root.mkdir(exist_ok=True)
            with self.store.connect() as db:
                row = db.execute("SELECT port FROM target_preferences WHERE project_id=?", (project_id,)).fetchone()
            preferred = [row["port"]] if row and self.start_port <= row["port"] <= self.end_port else []
            bind_host = os.environ.get("WPS_BIND_HOST", config.server_host)
            connect_host = "127.0.0.1" if bind_host == "0.0.0.0" else bind_host
            reservation = socket.socket()
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            for port in dict.fromkeys([*preferred, *range(self.start_port, self.end_port + 1)]):
                try:
                    reservation.bind((bind_host, port))
                    break
                except OSError:
                    continue
            else:
                reservation.close()
                raise ValueError("No target port is available. Change WPS_TARGET_PORT_START and WPS_TARGET_PORT_END.")
            reservation.listen(128)
            port = reservation.getsockname()[1]
            token = secrets.token_urlsafe(32)
            project_root = Path(__file__).resolve().parents[2]
            environment = {"PATH": os.defpath, "PYTHONPATH": str(project_root), "PYTHONIOENCODING": "utf-8",
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
            try:
                with (root / "server.log").open("ab") as log:
                    process = subprocess.Popen([sys.executable, "-m", "pipeline_core.live_target"], cwd=project_root,
                        env=environment, stdin=subprocess.PIPE, stdout=log, stderr=log,
                        pass_fds=(reservation.fileno(),), start_new_session=True)
                target = Target(process, token, port, root, connect_host=connect_host)
                self.targets[project_id] = target
                assert process.stdin is not None
                settings = {"root": str(root), "token": token, "port": port, "socket": reservation.fileno(),
                    "static": str(project_root / "runtime_static"), "allowed_hosts": list(config.allowed_hosts),
                    "broker": f"{builder_url.rstrip('/')}/api/internal/targets/{project_id}"}
                process.stdin.write((json.dumps(settings) + "\n").encode())
                process.stdin.flush()
            finally:
                reservation.close()
            with self.store.connect() as db:
                db.execute("INSERT INTO target_preferences(project_id,port) VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET port=excluded.port", (project_id, port))
            try:
                async with httpx.AsyncClient(timeout=.5, trust_env=False) as client:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise ValueError("Target exited during startup. Check the project target/server.log.")
                        try:
                            response = await client.get(target.url + "/health")
                            if response.status_code == 200 and response.json().get("mode") == "live":
                                break
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(.1)
                    else:
                        raise ValueError("Target did not become ready within ten seconds")
                await self.sync(project_id)
            except Exception as exc:
                target.error = str(exc)
                await self.stop(project_id)
                raise
            return self.status(project_id)

    async def stop(self, project_id: str) -> dict[str, Any]:
        target = self.targets.get(project_id)
        if target:
            if target.process.stdin:
                target.process.stdin.close()
            try:
                await asyncio.wait_for(asyncio.to_thread(target.process.wait), 7)
            except asyncio.TimeoutError:
                target.process.kill()
                await asyncio.to_thread(target.process.wait)
            self.targets.pop(project_id, None)
        return {"status": "stopped", "url": None, "port": None, "error": None}

    def authorize(self, project_id: str, token: str) -> Target:
        target = self.targets.get(project_id)
        if not target or not hmac.compare_digest(token, target.token):
            raise PermissionError("Invalid target session")
        return target

    async def sync(self, project_id: str) -> None:
        async with self.sync_locks.setdefault(project_id, asyncio.Lock()):
            await self._sync(project_id)

    async def _sync(self, project_id: str) -> None:
        target = self.targets.get(project_id)
        if not target or target.process.poll() is not None:
            return
        project = self.store.get(project_id)
        workspace = Workspaces(self.store).get(project_id)
        run = self.store.run(project_id, project["display_run_id"]) if project["display_run_id"] else None
        revision = self.store.revision(project_id, run.revision_id) if run else None
        pending = (not revision or not run or bool(workspace["issues"]) or calculation_hash(workspace["document"]) != calculation_hash(revision)
            or project["dataset_hash"] != run.input_hash)
        if run:
            directory = target.root / "builder-input"
            directory.mkdir(exist_ok=True)
            destination = directory / f"{run.input_hash}.csv"
            if not destination.exists():
                source = self.store.project_dir(project_id) / "datasets" / f"{run.input_hash}.csv"
                await asyncio.to_thread(link_or_copy, str(source), str(destination))
        document = workspace["document"]
        payload = {"presentation": {"title": document["title"], "dashboard": document["dashboard"]},
            "pending": pending, "revision": revision.model_dump() if revision else None,
            "key": run.run_id if run else None, "input_hash": run.input_hash if run else None,
            "dataset_name": run.dataset_name if run else None}
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.post(target.url + "/internal/snapshot", json=payload, headers={"X-Target-Token": target.token})
                response.raise_for_status()
            target.error = None
        except httpx.HTTPError as exc:
            target.error = f"Dashboard update failed: {exc}"

    async def state(self, project_id: str) -> dict[str, Any] | None:
        target = self.targets.get(project_id)
        if not target or target.process.poll() is not None:
            return None
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
                response = await client.get(target.url + "/api/runtime/state")
                response.raise_for_status()
                return dict(response.json())
        except httpx.HTTPError:
            return None

    async def close(self) -> None:
        await asyncio.gather(*(self.stop(project) for project in list(self.targets)), return_exceptions=True)
