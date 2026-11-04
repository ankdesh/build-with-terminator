"""Build, execute, validate, accept, and refine persistent analysis projects."""

import asyncio
import threading
from pathlib import Path
from typing import Any, Callable

from backend.services.project_agent import ProjectAgent, ProposalValidationError, ModelUnavailableError
from backend.services.project_store import ProjectStore
from backend.services.run_diagnostics import collect_run_diagnostics
from config import config
from pipeline_core.engine import fingerprint
from pipeline_core.models import ProjectRevision, RunRecord, DashboardSpec, now
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.validation import validate_parameters
from backend.services.workspace_service import Workspaces
from pipeline_core.workspace import WorkspaceDocument


class ProjectService:
    def __init__(self, store: ProjectStore, agent: ProjectAgent | None = None, runner: ProcessRunner | None = None) -> None:
        self.store = store
        self.agent = agent or ProjectAgent()
        self.runner = runner or ProcessRunner()
        self.lock = asyncio.Lock()
        self.authoring_locks: dict[str, asyncio.Lock] = {}
        self.cancellations: dict[str, threading.Event] = {}

    async def execute(self, project_id: str, revision: ProjectRevision, parameters: dict,
                      emit: Callable[[dict], None], cancel: threading.Event,
                      input_path: Path | None = None, dataset_name: str | None = None,
                      workspace_version: int | None = None) -> RunRecord:
        project = self.store.get(project_id)
        input_path = input_path or self.store.dataset_path(project_id)
        run = RunRecord(revision_id=revision.revision_id, dataset_name=dataset_name or project["dataset_name"],
                        input_hash=fingerprint(input_path), parameters=validate_parameters(revision, parameters),
                        workspace_version=workspace_version or Workspaces(self.store).get(project_id)["version"])
        self.store.put_run(project_id, run)
        self.cancellations[run.run_id] = cancel
        emit({"event": "run_started", "run_id": run.run_id})
        previous = project["display_run_id"]
        cache = self.store.run_dir(project_id, previous) / "output" if previous else None
        loop = asyncio.get_running_loop()
        def relay(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(emit, event)
        try:
            emit({"event": "status", "message": "Waiting for the execution slot"})
            response: dict[str, Any]
            async with self.lock:
                if cancel.is_set():
                    response = {"success": False, "cancelled": True, "error": "Run cancelled"}
                else:
                    emit({"event": "worker_started", "message": "Running saved pipeline"})
                    response = await self.runner.run(revision, input_path, run.parameters,
                        self.store.run_dir(project_id, run.run_id), cancel, cache, relay)
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
        except Exception as exc:
            run.status, run.finished_at, run.error = "failed", now(), str(exc)
            self.store.put_run(project_id, run)
            emit({"event": "run", "run": run.model_dump()})
            return run
        finally:
            self.cancellations.pop(run.run_id, None)

    async def build(self, project_id: str, query: str, emit: Callable[[dict], None], cancel: threading.Event) -> None:
        async with self.authoring_locks.setdefault(project_id, asyncio.Lock()):
            self.store.dataset_path(project_id)
            self.store.message(project_id, "user", query)
            project = self.store.get(project_id)
            workspace = Workspaces(self.store)
            base = workspace.get(project_id)
            run_diagnostics = await asyncio.to_thread(collect_run_diagnostics, self.store, project_id,
                                                     query, config.openai_api_key)
            document = WorkspaceDocument.model_validate(base["document"])
            current = None
            if document.input_contract:
                # Agent context can include an incomplete graph. Only the proposal is compiled.
                context = {field: getattr(document, field) for field in ProjectRevision.model_fields if hasattr(document, field)}
                context["dashboard"] = DashboardSpec.model_construct(title=document.dashboard.title,
                    subtitle=document.dashboard.subtitle, widgets=document.dashboard.widgets)
                current = ProjectRevision.model_construct(**context,
                    revision_id=project["draft_id"] or "workspace", schema_version=2)
            error = None
            failed = None
            for attempt in range(config.max_retries + 1):
                if cancel.is_set():
                    raise ValueError("Build cancelled")
                emit({"event": "status", "message": "Updating workspace" if attempt == 0 else f"Repairing proposal ({attempt}/{config.max_retries})"})
                try:
                    try:
                        revision = await self.agent.propose(project, current, query, self.store.messages(project_id), error, failed,
                                                            run_diagnostics=run_diagnostics)
                    except (ProposalValidationError, ModelUnavailableError):
                        raise
                    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
                        # A malformed patch belongs to proposal repair. Preserve
                        # the complete working revision, not the patch payload.
                        error = f"Invalid model proposal: {exc}"
                        continue
                    if cancel.is_set():
                        raise ValueError("Build cancelled")
                    workspace.write(project_id, base["version"], WorkspaceDocument.from_revision(revision), trusted=True)
                    self.store.save_revision(project_id, revision, sync_workspace=False)
                    await asyncio.to_thread(workspace.validate_presentation, project_id)
                    emit({"event": "revision", "revision": revision.model_dump()})
                    self.store.message(project_id, "assistant", (revision.summary or "Workspace updated.") + " Select Run to update calculations.")
                    return
                except ProposalValidationError as exc:
                    failed, error = exc.proposal, str(exc)
                except ModelUnavailableError as exc:
                    error = str(exc)
                    break
            self.store.message(project_id, "assistant", f"Workspace update failed: {error}")
            raise ValueError(error or "Proposal validation failed")

    async def rerun(self, project_id: str, revision_id: str, parameters: dict,
                    emit: Callable[[dict], None], cancel: threading.Event) -> None:
        await self.execute(project_id, self.store.revision(project_id, revision_id), parameters, emit, cancel)
