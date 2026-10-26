"""Versioned project, dashboard, and execution contracts."""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = str
Scalar = str | int | float | bool | None
Dependency = Literal["pandas", "numpy", "scipy", "statsmodels"]


def default_dependencies() -> list[Dependency]:
    return ["pandas", "numpy"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ColumnSpec(Contract):
    name: str = Field(min_length=1)
    dtype: Literal["string", "number", "integer", "boolean", "datetime"] = "string"
    nullable: bool = True
    description: str = ""
    date_format: str | None = None


class InputContract(Contract):
    columns: list[ColumnSpec] = Field(min_length=1)
    encoding: str = "utf-8-sig"
    delimiter: str = Field(default=",", min_length=1, max_length=1)

    @model_validator(mode="after")
    def unique_columns(self) -> "InputContract":
        if len({c.name for c in self.columns}) != len(self.columns):
            raise ValueError("Input column names must be unique")
        return self


class ParameterSpec(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    kind: Literal["number", "integer", "string", "boolean", "select"]
    default: Scalar = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Scalar] = Field(default_factory=list)
    filter_column: str | None = None
    filter_artifact: str = "cleaned"
    filter_operator: Literal["eq", "gte", "lte", "contains"] = "eq"


class PipelineStep(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    title: str
    stage: Literal["cleanup", "analysis"]
    function: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    code: str = Field(min_length=1, max_length=50000)
    inputs: list[str] = Field(default_factory=lambda: ["data"])
    outputs: list[str] = Field(min_length=1)
    parameters_used: list[str] | None = None
    changes_meaning: bool = False
    rationale: str = ""


class ChartBinding(Contract):
    kind: Literal["bar", "line", "scatter", "pie"] = "bar"
    x: str
    y: list[str] = Field(min_length=1)
    x_label: str | None = None
    y_label: str | None = None


class Widget(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["metric", "chart", "table", "text"]
    title: str
    output: str
    width: Literal[1, 2] = 1
    format: str | None = None
    chart_binding: ChartBinding | None = None


class DashboardSpec(Contract):
    title: str = Field(min_length=1)
    subtitle: str = ""
    widgets: list[Widget] = Field(min_length=1)


class ProjectRevision(Contract):
    schema_version: Literal[1] = 1
    revision_id: str = Field(default_factory=lambda: str(uuid4()))
    parent_revision_id: str | None = None
    created_at: str = Field(default_factory=now)
    title: str
    summary: str = ""
    input_contract: InputContract
    steps: list[PipelineStep] = Field(min_length=1, max_length=40)
    parameters: list[ParameterSpec] = Field(default_factory=list)
    dashboard: DashboardSpec
    dependencies: list[Dependency] = Field(default_factory=default_dependencies)
    seed: int = 0

    @model_validator(mode="after")
    def validate_graph(self) -> "ProjectRevision":
        from pipeline_core.validation import validate_revision
        validate_revision(self)
        return self

    def default_parameters(self) -> dict[str, Scalar]:
        return {p.id: p.default for p in self.parameters}


class RunRecord(Contract):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    revision_id: str
    dataset_name: str
    input_hash: str
    parameters: dict[str, Scalar]
    status: Literal["running", "succeeded", "failed", "cancelled", "interrupted"] = "running"
    started_at: str = Field(default_factory=now)
    finished_at: str | None = None
    runtime_version: str = "0.2.0"
    error: str | None = None
    result: dict[str, Any] | None = None
