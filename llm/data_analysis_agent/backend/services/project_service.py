"""Build, execute, validate, accept, and refine persistent analysis projects."""

import asyncio
import threading
from typing import Any, Callable

from backend.services.project_agent import ProjectAgent, ProposalValidationError, ModelUnavailableError
from backend.services.project_store import ProjectStore
from config import config
from pipeline_core.engine import fingerprint
from pipeline_core.models import ProjectRevision, RunRecord, now
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.validation import validate_parameters


class ProjectService:
    def __init__(self, store: ProjectStore, agent: ProjectAgent | None = None, runner: ProcessRunner | None = None) -> None:
        self.store = store
        self.agent = agent or ProjectAgent()
        self.runner = runner or ProcessRunner()
        self.lock = asyncio.Lock()
        self.cancellations: dict[str, threading.Event] = {}

    async def execute(self, project_id: str, revision: ProjectRevision, parameters: dict,
                      emit: Callable[[dict], None], cancel: threading.Event) -> RunRecord:
        project = self.store.get(project_id)
        input_path = self.store.dataset_path(project_id)
        run = RunRecord(revision_id=revision.revision_id, dataset_name=project["dataset_name"],
                        input_hash=fingerprint(input_path), parameters=validate_parameters(revision, parameters))
        self.store.put_run(project_id, run)
        self.cancellations[run.run_id] = cancel
        emit({"event": "run_started", "run_id": run.run_id})
        previous = project["display_run_id"]
        cache = self.store.run_dir(project_id, previous) / "output" if previous else None
        loop = asyncio.get_running_loop()
        def relay(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(emit, event)
        try:
            response = await self.runner.run(revision, input_path, run.parameters,
                self.store.run_dir(project_id, run.run_id), cancel, cache,
                relay)
            run.status = "succeeded" if response["success"] else "cancelled" if response.get("cancelled") else "failed"
            run.result = response.get("result")
            run.error = response.get("error")
            run.finished_at = now()
            self.store.put_run(project_id, run)
            emit({"event": "run", "run": run.model_dump()})
            return run
        except asyncio.CancelledError:
            cancel.set()
            run.status, run.finished_at, run.error = "cancelled", now(), "Run cancelled"
            self.store.put_run(project_id, run)
            raise
        finally:
            self.cancellations.pop(run.run_id, None)

    async def build(self, project_id: str, query: str, emit: Callable[[dict], None], cancel: threading.Event) -> None:
        async with self.lock:
            self.store.dataset_path(project_id)
            self.store.message(project_id, "user", query)
            project = self.store.get(project_id)
            current = self.store.revision(project_id, project["draft_id"]) if project["draft_id"] else None
            error = None
            failed = None
            for attempt in range(config.max_retries + 1):
                if cancel.is_set():
                    raise ValueError("Build cancelled")
                emit({"event": "status", "message": "Generating project draft" if attempt == 0 else f"Repairing draft ({attempt}/{config.max_retries})"})
                try:
                    revision = await self.agent.propose(project, current, query, self.store.messages(project_id), error, failed)
                    failed = revision.model_dump()
                    if cancel.is_set():
                        raise ValueError("Build cancelled")
                    self.store.save_revision(project_id, revision)
                    emit({"event": "revision", "revision": revision.model_dump()})
                    run = await self.execute(project_id, revision, {}, emit, cancel)
                    if run.status == "succeeded":
                        self.store.message(project_id, "assistant", revision.summary or "Draft validated. Review cleanup and accept the revision.")
                        return
                    if run.status == "cancelled":
                        raise ValueError("Build cancelled")
                    error = run.error or "Pipeline failed validation"
                    # Infrastructure failures cannot be repaired by changing code.
                    if "Bubblewrap" in error or "Worker could not start" in error:
                        break
                except asyncio.CancelledError:
                    cancel.set()
                    raise
                except ProposalValidationError as exc:
                    failed = exc.proposal
                    error = str(exc)
                except ModelUnavailableError as exc:
                    error = str(exc)
                    break
                except Exception as exc:
                    error = str(exc)
                    if cancel.is_set():
                        raise
            self.store.message(project_id, "assistant", f"Draft could not be validated: {error}")
            raise ValueError(error or "Draft validation failed")

    async def rerun(self, project_id: str, revision_id: str, parameters: dict,
                    emit: Callable[[dict], None], cancel: threading.Event) -> None:
        async with self.lock:
            await self.execute(project_id, self.store.revision(project_id, revision_id), parameters, emit, cancel)
