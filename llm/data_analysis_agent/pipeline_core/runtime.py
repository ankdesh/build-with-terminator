"""Shared dashboard state machine for live targets and offline applications."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import threading
from typing import Any, Callable, Protocol
from uuid import uuid4

from pipeline_core.engine import fingerprint, render_saved
from pipeline_core.models import ProjectRevision, RunRecord, now
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.validation import validate_parameters
from pipeline_core.workspace import calculation_hash


class Runner(Protocol):
    async def run(self, revision: ProjectRevision, input_path: Path, parameters: dict[str, Any],
                  job_dir: Path, cancel: threading.Event, cache_dir: Path | None = None,
                  on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]: ...


def link_or_copy(source: str, destination: str) -> str:
    import os
    try:
        os.link(source, destination)
        return destination
    except OSError:
        return shutil.copy2(source, destination)


class RuntimeApplication:
    def __init__(self, root: Path, revision: ProjectRevision | None = None,
                 runner: Runner | None = None, live: bool = False) -> None:
        self.root, self.live = root, live
        root.mkdir(parents=True, exist_ok=True)
        self.state_path = root / "state.json"
        self.state: dict[str, Any] = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "input": None, "dataset_name": None, "display_run": None, "last_error": None,
            "input_mode": "builder" if live else "local", "applied_snapshot": None}
        saved = self.state.get("revision")
        self.revision = ProjectRevision.model_validate(saved) if live and saved else revision
        self.desired_revision = self.revision
        self.presentation = self.state.get("presentation")
        self.pending = self.state.get("pending", False)
        self.runner: Runner = runner or ProcessRunner()
        self.lock = asyncio.Lock()
        self.cancel: threading.Event | None = None
        self.events: list[dict[str, Any]] = []
        self.sequence = 0
        self.instance_id = uuid4().hex
        self.changed = asyncio.Condition()
        self.builder_input: tuple[Path, str] | None = None
        self.attempted_snapshot: str | None = None
        self.tasks: set[asyncio.Task[Any]] = set()
        if self.state.get("active_run"):
            self.state.update(active_run=None, last_error="The previous run was interrupted. The last successful dashboard is retained.")
            self.save()

    def save(self) -> None:
        self.state.update(revision=self.revision.model_dump() if self.revision else None,
            presentation=self.presentation, pending=self.pending)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, allow_nan=False))
        temporary.replace(self.state_path)

    async def notify(self) -> None:
        async with self.changed:
            self.sequence += 1
            self.changed.notify_all()

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self.events = self.events[-80:]
        task = asyncio.create_task(self.notify())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def copy_input(self, source: Path) -> Path:
        directory = self.root / "datasets"
        directory.mkdir(exist_ok=True)
        destination = directory / f"{fingerprint(source)}.csv"
        if not destination.exists():
            shutil.copyfile(source, destination)
        return destination

    def view(self) -> dict[str, Any]:
        return {"mode": "live" if self.live else "runtime",
            "revision": self.revision.model_dump() if self.revision else None,
            "presentation": self.presentation, "pending": self.pending or bool(self.attempted_snapshot and self.attempted_snapshot != self.state.get("applied_snapshot")),
            "calculation_pending": self.pending,
            "display_run": self.state.get("display_run"), "dataset_name": self.state.get("dataset_name"),
            "has_input": bool(self.state.get("input")), "last_error": self.state.get("last_error"),
            "input_mode": self.state.get("input_mode", "local"),
            "active_run": self.state.get("active_run"), "events": self.events[-80:],
            "sequence": self.sequence, "instance_id": self.instance_id, "control_notice": self.state.get("control_notice")}

    async def execute(self, candidate: Path, name: str, parameters: dict[str, Any],
                      revision: ProjectRevision | None = None, input_mode: str | None = None,
                      snapshot: str | None = None) -> dict[str, Any]:
        async with self.lock:
            selected = revision or self.revision
            if selected is None:
                raise ValueError("The developer must run the workspace first")
            resolved = validate_parameters(selected, parameters)
            run = RunRecord(revision_id=selected.revision_id, dataset_name=name,
                input_hash=fingerprint(candidate), parameters=resolved)
            self.cancel = threading.Event()
            self.events = []
            self.state["active_run"] = run.model_dump()
            self.save()
            await self.notify()
            loop = asyncio.get_running_loop()
            previous = self.state.get("display_run")
            cache = self.root / "runs" / previous["run_id"] / "output" if previous else None
            job_dir = self.root / "runs" / run.run_id
            job_dir.mkdir(parents=True, exist_ok=True)
            def relay(event: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(self.emit, event)
            try:
                response = await self.runner.run(selected, candidate, resolved, job_dir, self.cancel, cache,
                    relay)
                run.status = "succeeded" if response["success"] else "cancelled" if response.get("cancelled") else "failed"
                run.finished_at, run.error, run.result = now(), response.get("error"), response.get("result")
                if snapshot and snapshot != self.attempted_snapshot:
                    response = {"success": False}
                    run.status, run.error = "cancelled", "A newer developer revision replaced this update"
                if response["success"]:
                    input_path = self.copy_input(candidate)
                    self.revision = selected
                    self.state.update(input=str(input_path), dataset_name=name, display_run=run.model_dump(), last_error=None)
                    if input_mode:
                        self.state["input_mode"] = input_mode
                    if snapshot:
                        self.state["applied_snapshot"] = snapshot
                elif not snapshot or snapshot == self.attempted_snapshot:
                    self.state["last_error"] = run.error
                (job_dir / "record.json").write_text(run.model_dump_json(indent=2))
                return {"run": run.model_dump(), "state": self.view()}
            except asyncio.CancelledError:
                self.cancel.set()
                self.state["last_error"] = "Run cancelled"
                raise
            except Exception as exc:
                self.state["last_error"] = str(exc)
                raise
            finally:
                self.state["active_run"] = None
                self.save()
                self.cancel = None
                await self.notify()

    async def update(self, snapshot: dict[str, Any]) -> None:
        """Receive a builder snapshot. Presentation is independent of calculations."""
        self.presentation = snapshot["presentation"]
        self.pending = snapshot["pending"]
        candidate = ProjectRevision.model_validate(snapshot["revision"]) if snapshot.get("revision") else None
        self.desired_revision = candidate
        if snapshot.get("input_hash"):
            path = self.root / "builder-input" / f"{snapshot['input_hash']}.csv"
            if path.is_file():
                self.builder_input = (path, snapshot.get("dataset_name") or "data.csv")
        self.save()
        await self.notify()
        key = snapshot.get("key")
        if not candidate or not key or key in {self.state.get("applied_snapshot"), self.attempted_snapshot}:
            return
        self.attempted_snapshot = key
        if self.cancel:
            self.cancel.set()
        task = asyncio.create_task(self._apply(candidate, key))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _apply(self, candidate: ProjectRevision, key: str) -> None:
        try:
            # Wait for a cancelled or user-started run to release runtime state.
            async with self.lock:
                if self.attempted_snapshot != key:
                    return
                previous = self.state.get("display_run")
                old_parameters = previous["parameters"] if previous else {}
                parameters = candidate.default_parameters()
                reset = set(old_parameters) - set(parameters)
                for parameter in candidate.parameters:
                    if parameter.id in old_parameters:
                        try:
                            validate_parameters(candidate, {parameter.id: old_parameters[parameter.id]})
                            parameters[parameter.id] = old_parameters[parameter.id]
                        except ValueError:
                            reset.add(parameter.id)
                self.state["control_notice"] = f"Reset changed controls: {', '.join(sorted(reset))}" if reset else None
                source = (Path(self.state["input"]), self.state["dataset_name"]) if self.state.get("input_mode") == "replacement" and self.state.get("input") else self.builder_input
                if not source:
                    return
                # A layout edit can reuse complete artifacts without another calculation.
                if (self.revision and previous and previous.get("result")
                        and calculation_hash(candidate) == calculation_hash(self.revision)
                        and fingerprint(source[0]) == previous["input_hash"]):
                    artifact_dir = self.root / "runs" / previous["run_id"] / "output"
                    result = await asyncio.to_thread(render_saved, candidate, artifact_dir, previous["result"], self.revision)
                    if self.attempted_snapshot != key:
                        return
                    record = RunRecord(revision_id=candidate.revision_id, dataset_name=previous["dataset_name"],
                        input_hash=previous["input_hash"], parameters=parameters, status="succeeded", finished_at=now(),
                        result=result, validation_mode="presentation", source_run_id=previous["run_id"])
                    destination = self.root / "runs" / record.run_id
                    await asyncio.to_thread(shutil.copytree, artifact_dir, destination / "output", copy_function=link_or_copy)
                    (destination / "output" / "result.json").unlink(missing_ok=True)
                    (destination / "output" / "result.json").write_text(json.dumps(result, allow_nan=False))
                    (destination / "record.json").write_text(record.model_dump_json())
                    self.revision = candidate
                    self.state.update(display_run=record.model_dump(), applied_snapshot=key, last_error=None)
                    self.save()
                    await self.notify()
                    return
            if self.attempted_snapshot == key:
                await self.execute(source[0], source[1], parameters, candidate, snapshot=key)
        except Exception as exc:
            self.state["last_error"] = f"Developer update could not be applied: {exc}"
            self.save()
            await self.notify()

    async def close(self) -> None:
        if self.cancel:
            self.cancel.set()
        tasks = list(self.tasks)
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 6)
            except asyncio.TimeoutError:
                for task in tasks:
                    task.cancel()
