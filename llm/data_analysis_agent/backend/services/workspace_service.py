"""Versioned development edits, undo, stage deletion, and presentation validation."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, TYPE_CHECKING

from pipeline_core.engine import render_saved
from pipeline_core.models import ProjectRevision, RunRecord, now
from pipeline_core.workspace import WorkspaceDocument, calculation_hash, deletion, stages

if TYPE_CHECKING:
    from backend.services.project_store import ProjectStore


class WorkspaceConflict(ValueError):
    pass


class Workspaces:
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def get(self, project_id: str) -> dict[str, Any]:
        project = self.store.get(project_id)
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM workspaces WHERE project_id=?", (project_id,)).fetchone()
            if row is None:
                document = (WorkspaceDocument.from_revision(self.store.revision(project_id, project["draft_id"]))
                    if project["draft_id"] else WorkspaceDocument(title=project["title"]))
                db.execute("INSERT OR IGNORE INTO workspaces(project_id,version,document) VALUES(?,1,?)",
                    (project_id, document.model_dump_json()))
                row = db.execute("SELECT * FROM workspaces WHERE project_id=?", (project_id,)).fetchone()
        assert row is not None
        document = WorkspaceDocument.model_validate_json(row["document"])
        issues = document.issues()
        if not project["dataset_hash"]:
            issues.insert(0, "Upload a CSV before running the workspace")
        validated_run_id = None
        calculation_pending = True
        if project["display_run_id"]:
            record = self.store.run(project_id, project["display_run_id"])
            revision = self.store.revision(project_id, record.revision_id)
            calculation_pending = calculation_hash(document.model_dump()) != calculation_hash(revision) or record.input_hash != project["dataset_hash"]
            if (not issues and WorkspaceDocument.from_revision(revision).model_dump() == document.model_dump()
                    and record.input_hash == project["dataset_hash"] and record.parameters == revision.default_parameters()):
                validated_run_id = record.run_id
        return {"version": row["version"], "document": document.model_dump(), "issues": issues,
            "stages": stages(document, bool(project["dataset_hash"])),
            "validated_run_id": validated_run_id, "calculation_pending": calculation_pending,
            "can_undo": bool(json.loads(row["history"])), "can_redo": bool(json.loads(row["future"]))}

    def write(self, project_id: str, expected: int, document: WorkspaceDocument,
              action: str = "edit", trusted: bool = False) -> dict[str, Any]:
        self.get(project_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM workspaces WHERE project_id=?", (project_id,)).fetchone()
            assert row is not None
            if row["version"] != expected:
                raise WorkspaceConflict("This workspace changed. Reload it before saving your edit.")
            previous = json.loads(row["document"])
            history, future = json.loads(row["history"]), json.loads(row["future"])
            if action in {"undo", "redo"}:
                source, destination = (history, future) if action == "undo" else (future, history)
                if not source:
                    raise ValueError(f"Nothing to {action}")
                destination.append(previous)
                document = WorkspaceDocument.model_validate(source.pop())
            else:
                if not trusted:
                    old_steps = {s["id"]: s for s in previous["steps"]}
                    if set(old_steps) != {step.id for step in document.steps}:
                        raise ValueError("Use chat to add stages or use the stage deletion review")
                    for step in document.steps:
                        before = old_steps.get(step.id)
                        if before is None or any(step.model_dump()[k] != before[k] for k in ("code", "function", "stage", "inputs", "outputs", "parameters_used", "changes_meaning")):
                            raise ValueError("Use chat to create or change calculation stages")
                    old_widgets = {w["id"] for w in previous["dashboard"]["widgets"]}
                    if old_widgets != {w.id for w in document.dashboard.widgets}:
                        raise ValueError("Use chat to create visualization stages")
                if document.model_dump() == previous:
                    return self.get(project_id)
                history.append(previous)
                future = []
            db.execute("UPDATE workspaces SET version=version+1,document=?,history=?,future=? WHERE project_id=?",
                (document.model_dump_json(), json.dumps(history[-50:]), json.dumps(future[-50:]), project_id))
            db.execute("UPDATE projects SET title=?,updated_at=? WHERE id=?", (document.title, now(), project_id))
        return self.get(project_id)

    def from_revision(self, project_id: str, revision: ProjectRevision) -> dict[str, Any]:
        current = self.get(project_id)
        return self.write(project_id, current["version"], WorkspaceDocument.from_revision(revision), trusted=True)

    def delete(self, project_id: str, stage_id: str, expected: int, confirmed: bool) -> dict[str, Any]:
        current = self.get(project_id)
        if current["version"] != expected:
            raise WorkspaceConflict("The workspace changed. Review the deletion again.")
        document, affected = deletion(WorkspaceDocument.model_validate(current["document"]), stage_id,
            bool(self.store.get(project_id)["dataset_hash"]))
        if not confirmed:
            return {"affected": affected, "version": expected}
        return self.write(project_id, expected, document, trusted=True)

    def compile(self, project_id: str, expected: int) -> ProjectRevision:
        current = self.get(project_id)
        if current["version"] != expected:
            raise WorkspaceConflict("Save the latest workspace before running")
        if current["issues"]:
            raise ValueError("; ".join(current["issues"]))
        project = self.store.get(project_id)
        document = WorkspaceDocument.model_validate(current["document"])
        if project["draft_id"]:
            existing = self.store.revision(project_id, project["draft_id"])
            if WorkspaceDocument.from_revision(existing).model_dump() == document.model_dump():
                return existing
        revision = document.compile(project["draft_id"])
        self.store.save_revision(project_id, revision, sync_workspace=False, expected_workspace_version=expected)
        return revision

    def validate_presentation(self, project_id: str) -> bool:
        current = self.get(project_id)
        project = self.store.get(project_id)
        if current["issues"] or not project["display_run_id"]:
            return False
        previous = self.store.run(project_id, project["display_run_id"])
        old = self.store.revision(project_id, previous.revision_id)
        if (not previous.result or previous.input_hash != project["dataset_hash"]
                or calculation_hash(old) != calculation_hash(current["document"])):
            return False
        if WorkspaceDocument.from_revision(old).model_dump() == current["document"]:
            return True
        revision = WorkspaceDocument.model_validate(current["document"]).compile(project["draft_id"])
        source = self.store.run_dir(project_id, previous.run_id) / "output"
        try:
            result = render_saved(revision, source, previous.result, old)
        except (ValueError, KeyError, OSError):
            return False
        try:
            self.store.save_revision(project_id, revision, sync_workspace=False, expected_workspace_version=current["version"])
        except WorkspaceConflict:
            return False
        record = RunRecord(revision_id=revision.revision_id, dataset_name=previous.dataset_name,
            input_hash=previous.input_hash, parameters=previous.parameters, status="succeeded", finished_at=now(),
            result=result, validation_mode="presentation", source_run_id=previous.run_id, workspace_version=current["version"])
        destination = self.store.project_dir(project_id) / "runs" / record.run_id / "output"
        shutil.copytree(source, destination, copy_function=_link_or_copy)
        (destination / "result.json").unlink(missing_ok=True)
        (destination / "result.json").write_text(json.dumps(result, allow_nan=False))
        self.store.put_run(project_id, record)
        return True


def _link_or_copy(source: str, destination: str) -> str:
    # Artifacts are immutable. Hard links avoid duplicating large tables for each layout edit.
    import os
    try:
        os.link(source, destination)
        return destination
    except OSError:
        return shutil.copy2(source, destination)
