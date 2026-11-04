"""Editable documents and deterministic views of the four stage types."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import Field, ValidationError

from pipeline_core.models import (
    Contract, Dependency, InputContract, ParameterSpec, PipelineStep,
    ProjectRevision, Widget, default_dependencies,
)


class DraftDashboard(Contract):
    title: str = Field(default="Your analysis dashboard", max_length=200)
    subtitle: str = Field(default="", max_length=2000)
    widgets: list[Widget] = Field(default_factory=list, max_length=100)


class WorkspaceDocument(Contract):
    title: str = Field(default="New analysis", min_length=1, max_length=200)
    summary: str = ""
    input_enabled: bool = True
    input_contract: InputContract | None = None
    steps: list[PipelineStep] = Field(default_factory=list, max_length=40)
    parameters: list[ParameterSpec] = Field(default_factory=list, max_length=80)
    dashboard: DraftDashboard = Field(default_factory=DraftDashboard)
    dependencies: list[Dependency] = Field(default_factory=default_dependencies)
    seed: int = 0

    @classmethod
    def from_revision(cls, revision: ProjectRevision) -> "WorkspaceDocument":
        data = revision.model_dump(exclude={"schema_version", "revision_id", "parent_revision_id", "created_at"})
        return cls.model_validate(data)

    def compile(self, parent: str | None = None) -> ProjectRevision:
        if not self.input_enabled:
            raise ValueError("Restore Data input before running the workspace")
        return ProjectRevision.model_validate({**self.model_dump(exclude={"input_enabled"}),
            "schema_version": 2, "parent_revision_id": parent})

    def issues(self) -> list[str]:
        missing = []
        if not self.input_enabled:
            missing.append("Restore the Data input stage")
        if not self.input_contract:
            missing.append("Ask the agent to define the input columns")
        if not any(step.stage == "cleanup" for step in self.steps):
            missing.append("Add a Data cleaning stage through chat")
        if not any(step.stage == "analysis" for step in self.steps):
            missing.append("Add an Analysis stage through chat")
        if not self.dashboard.widgets:
            missing.append("Add a Visualization stage through chat")
        if missing:
            return missing
        try:
            self.compile()
            return []
        except ValidationError as exc:
            return list(dict.fromkeys(e["msg"].removeprefix("Value error, ") for e in exc.errors()))
        except ValueError as exc:
            return [str(exc)]


def calculation_hash(document: dict[str, Any] | ProjectRevision) -> str:
    data = document.model_dump() if isinstance(document, ProjectRevision) else document
    # Titles and rationale do not change executable behavior.
    steps = [{k: v for k, v in s.items() if k not in {"title", "rationale"}} for s in data.get("steps", [])]
    contract = data.get("input_contract")
    if contract:
        contract = {**contract, "columns": [{k: v for k, v in column.items() if k != "description"} for column in contract["columns"]]}
    identity = {"input_contract": contract, "input_enabled": data.get("input_enabled", True),
        "steps": steps, "parameters": [{k: v for k, v in p.items() if k != "label"} for p in data.get("parameters", [])],
        "dependencies": data.get("dependencies"), "seed": data.get("seed", 0)}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()


def stages(document: WorkspaceDocument, has_input: bool) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if document.input_enabled and has_input:
        result.append({"id": "input:data", "type": "input", "title": "Data input", "inputs": [], "outputs": ["data"], "dependencies": []})
    owners = {"data": "input:data"}
    owners.update({output: f"step:{step.id}" for step in document.steps for output in step.outputs})
    for step in document.steps:
        result.append({"id": f"step:{step.id}", "type": "cleaning" if step.stage == "cleanup" else "analysis",
            "title": step.title, "rationale": step.rationale, "inputs": step.inputs, "outputs": step.outputs,
            "dependencies": list(dict.fromkeys(owners[i] for i in step.inputs if i in owners))})
    for widget in document.dashboard.widgets:
        result.append({"id": f"widget:{widget.id}", "type": "visualization", "title": widget.title,
            "inputs": [widget.output], "outputs": [], "dependencies": [owners[widget.output]] if widget.output in owners else []})
    return result


def deletion(document: WorkspaceDocument, stage_id: str, has_input: bool) -> tuple[WorkspaceDocument, list[dict[str, Any]]]:
    graph = stages(document, has_input)
    if stage_id not in {s["id"] for s in graph}:
        raise KeyError("Stage not found")
    removed = {stage_id}
    while True:
        affected = {s["id"] for s in graph if set(s["dependencies"]) & removed}
        if affected <= removed:
            break
        removed.update(affected)
    data = document.model_dump()
    data["steps"] = [s for s in data["steps"] if f"step:{s['id']}" not in removed]
    data["dashboard"]["widgets"] = [w for w in data["dashboard"]["widgets"] if f"widget:{w['id']}" not in removed]
    if "input:data" in removed:
        data["input_enabled"] = False
    outputs = {"data"} | {o for s in data["steps"] for o in s["outputs"]}
    data["parameters"] = [p for p in data["parameters"] if not p["filter_column"] or p["filter_artifact"] in outputs]
    return WorkspaceDocument.model_validate(data), [s for s in graph if s["id"] in removed]
