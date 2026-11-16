"""Small model contracts. These do not expose storage or execution permissions."""
from typing import Literal
from pydantic import Field, model_validator
from pipeline_core.models import Contract


class Question(Contract):
    question: str = Field(min_length=1, max_length=2000)
    reason: str = Field(default="", max_length=2000)
    choices: list[str] = Field(default_factory=list, max_length=6)
    saveable: bool = False


class Route(Contract):
    kind: Literal["answer", "clarification", "proposal", "needs_run", "analysis", "mixed"]
    message: str = Field(min_length=1, max_length=16000)
    requested_scope: Literal["current", "project"] = "current"
    questions: list[Question] = Field(default_factory=list, max_length=3)
    proposal_id: str | None = Field(default=None, description='Exact pending proposal UUID from pending_proposals for explicit refinement, otherwise null. Never a stage ID.')


class EditOperation(Contract):
    op: Literal["add", "update", "remove"]
    kind: Literal["input", "step", "widget", "control", "project", "dashboard"]
    target_id: str
    fields_json: str = "{}"
    code_request: str = ""
    linked_reason: str = ""
    unset_fields: list[str] = Field(default_factory=list, max_length=20)


class EditPlan(Contract):
    summary: str
    operations: list[EditOperation] = Field(default_factory=list, max_length=100)
    questions: list[Question] = Field(default_factory=list, max_length=3)


class StepSource(Contract):
    code: str = Field(min_length=1, max_length=50000)


class QueryOperation(Contract):
    op: Literal["filter", "aggregate", "sort", "limit", "select", "correlation", "describe"]
    column: str = ""
    columns: list[str] = Field(default_factory=list)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "is_null", "not_null"] = "eq"
    value_json: str = "null"
    group_by: list[str] = Field(default_factory=list)
    metric: Literal["count", "sum", "mean", "min", "max", "median", "nunique"] = "count"
    alias: str = "value"
    descending: bool = True
    limit: int = Field(default=20, ge=1, le=5000)

    @model_validator(mode='after')
    def check_operation(self) -> 'QueryOperation':
        if self.op != 'filter' and (self.operator != 'eq' or self.value_json not in {'null',''}):
            raise ValueError('Filter predicates apply only to a separate filter operation. Aggregations do not filter rows.')
        if self.op in {'filter','sort'} and not self.column:
            raise ValueError('A filter or sort requires a column. Use Python for predicates across multiple columns.')
        if self.op == 'aggregate' and self.columns:
            raise ValueError('Aggregate uses column and group_by. Use Python for several measures.')
        if self.op == 'aggregate' and self.alias in self.group_by:
            raise ValueError('An aggregate alias must differ from grouping columns.')
        return self


class AnalysisPlan(Contract):
    kind: Literal["query", "python", "clarification"]
    message: str
    source: str = Field(default="auto", description='auto, raw, cleaned, or an exact cleaning output name. Never a step ID.')
    operations: list[QueryOperation] = Field(default_factory=list, max_length=30)
    code: str = ""
    chart_kind: Literal["none", "bar", "line", "scatter", "pie"] = "none"
    chart_x: str = ""
    chart_y: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list, max_length=3)


class Answer(Contract):
    message: str = Field(min_length=1, max_length=16000)
    evidence_ids: list[str] = Field(default_factory=list)
