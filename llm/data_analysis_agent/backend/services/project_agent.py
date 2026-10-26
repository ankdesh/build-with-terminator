"""Generate complete project drafts using current saved state and bounded data context."""

import json
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI, APIError

from config import config
from pipeline_core.models import ProjectRevision, now

PROMPT = """You build reusable data analysis applications. Return one complete ProjectRevision JSON object.
The saved project runs without an LLM. Produce portable Python functions with exactly three arguments:
    def function(inputs, parameters, context):
        df = inputs['data'].copy()
        return {'cleaned': df}
The mapping keys must exactly match that step's declared outputs. There are no hidden data variables.
Always separate cleanup and analysis. Cleanup outputs DataFrames. Analysis consumes the named cleanup
outputs. Set changes_meaning=true for row removal, imputation, outlier removal or substantive value changes,
and explain the rule in rationale. Missing values, date formats, timezone, units and duplicate treatment
must be explicit. Do not silently guess business rules. Preserve raw input.
Declare columns and their parsing types. Text that needs cleanup must remain string in the input contract.
Numeric columns may be nullable. Filter controls have filter_column and filter_artifact (usually cleaned),
with default=null for All. The engine filters the artifact before analysis and supplies parameters to all
functions. Every function handles empty filtered data. Non-filter controls require finite defaults and bounds.
Supported imports: pandas, numpy, scipy, statsmodels, math, datetime, re, statistics, collections,
itertools, functools, decimal, typing, json and pipeline_core.statistics. No filesystem, networking,
subprocess, reflection, pip, plotting libraries, or OS-specific code. Never import sklearn.
Do not read the system clock. Use saved date parameters or dates from the dataset. Random generators
must use context['seed'] or another explicit saved seed; do not use entropy-seeded default_rng().
Use pipeline_core.statistics.forecast(series, horizon, method, season_length) for forecasts. Its result
includes forecast, prediction_intervals_95, backtest_mae, baseline_mae, assumptions and uncertainty.
It requires ordered equally spaced observations and at least ten values. Surface insufficient-data errors,
the holdout validation and baseline, and distinguish predicted from observed values.
The dashboard uses only metric, chart, table and computed text widgets. Metric output is a scalar;
table output is a DataFrame; text output is a string computed from CURRENT data; chart output is
{'title':'...', 'option':{...}} using native ECharts JSON arrays, never Python callbacks or JavaScript.
Bound each chart axis, series or dataset to 5000 items with explicit aggregation or sampling.
Do not include external URLs or HTML in chart options. Output tables in full, not head(500).
IMPORTANT: dashboard.widgets contain ONLY id, kind, title, output, width, format and chart_binding.
Never place option, data, value, rows, or columns inside a widget. A widget's output is just the name
of a step output. Generate chart options dynamically inside Python and return that named output.
For example the widget {'id':'usage','kind':'chart','title':'Usage','output':'usage_chart','width':1}
binds to a function returning {'usage_chart': {'option': {'xAxis': {'data': df['category'].tolist()},
'yAxis': {'type':'value'}, 'series': [{'type':'bar','data': df['amount'].tolist()}]}}}.
Prefer DataFrame chart bindings for standard charts: return grouped data as a DataFrame and set
chart_binding={'kind':'bar','x':'category','y':['amount'],'x_label':null,'y_label':null} on the chart widget.
The same DataFrame can bind to a table widget. Set chart_binding=null on non-chart widgets or when
the Python output is an ECharts option object. A text widget can bind to a computed string or scalar.
Static dashboard title and subtitle describe PURPOSE, never data-specific findings.
When refining, use the supplied current revision as source of truth. Preserve unaffected step ids,
source, output names, parameters and widgets. For presentation-only changes, preserve ALL Python source.
Do not add steps just to answer a one-off question; refine the saved application coherently.
summary describes the changes and any assumptions that the user must review.
Only return schema fields; the server assigns revision identity and parentage.
When working_revision is present, return a PATCH instead of the whole revision:
{"summary":"Describe the changes", "changes":[{"op":"replace","path":"/dashboard/title","value":"New title"}]}.
Use JSON Pointer paths with add, replace, or remove operations. Patch only fields necessary for the request.
When the response contract requests value_json, encode each value as a JSON string inside value_json;
for example value_json='"New title"'. Use value_json=null for remove. Otherwise use value directly.
A dashboard title change modifies /dashboard/title, not /title (the project name).
For code changes, replace the affected /steps/<index>/code and any required bindings. Preserve other source.
For a repair, working_revision is the failed proposal; patch that proposal to correct the validation error.
"""


class ProposalValidationError(ValueError):
    """Retain the rejected proposal so repair has the actual failing source."""

    def __init__(self, message: str, proposal: dict[str, Any]) -> None:
        super().__init__(message)
        self.proposal = proposal


class ModelUnavailableError(RuntimeError):
    """Model connection, capability, or refusal errors cannot be repaired as code."""


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert Pydantic's optional defaults to the API's strict object contract."""
    result: dict[str, Any] = json.loads(json.dumps(schema))
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            if "const" in value:
                value["enum"] = [value.pop("const")]
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for key in ("properties", "$defs", "definitions"):
                for nested in value.get(key, {}).values(): visit(nested)
            for key in ("anyOf", "oneOf", "allOf"):
                for nested in value.get(key, []): visit(nested)
            if isinstance(value.get("items"), (dict, list)):
                visit(value["items"])
        elif isinstance(value, list):
            for nested in value: visit(nested)
    visit(result)
    return result


PATCH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["summary", "changes"],
    "properties": {
        "summary": {"type": "string"},
        "changes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["op", "path", "value_json"],
            "properties": {"op": {"type": "string", "enum": ["add", "replace", "remove"]},
                "path": {"type": "string"}, "value_json": {"type": ["string", "null"]}},
        }},
    },
}


def apply_changes(base: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply a bounded JSON Pointer patch to editable project fields only."""
    result: dict[str, Any] = json.loads(json.dumps(base))
    editable = {"title", "summary", "input_contract", "steps", "parameters", "dashboard", "dependencies", "seed"}
    if not isinstance(changes, list) or len(changes) > 100:
        raise ValueError("Refinement requires a list of at most 100 changes")
    for change in changes:
        op, path = change.get("op"), change.get("path")
        if op not in {"add", "replace", "remove"} or not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("Invalid refinement operation")
        tokens = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
        if tokens[0] not in editable or len(tokens) > 12:
            raise ValueError("Refinement cannot change revision identity or schema version")
        target: Any = result
        try:
            for token in tokens[:-1]:
                target = target[int(token)] if isinstance(target, list) else target[token]
            key = tokens[-1]
            if isinstance(target, list):
                if key != "-" and (not key.isdecimal() or int(key) < 0):
                    raise ValueError("Invalid array index")
                index = len(target) if key == "-" else int(key)
                if op == "add":
                    if index > len(target): raise ValueError("Array index is out of bounds")
                    target.insert(index, change["value"])
                elif op == "replace": target[index] = change["value"]
                else: target.pop(index)
            elif isinstance(target, dict):
                if op in {"replace", "remove"} and key not in target:
                    raise ValueError("Refinement path does not exist")
                if op == "remove": del target[key]
                else: target[key] = change["value"]
            else:
                raise ValueError("Refinement path is not an object or array")
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Invalid refinement path: {path}") from exc
    return result


class ProjectAgent:
    def __init__(self, client: Any = None) -> None:
        self.client = client

    async def propose(self, project: dict, current: ProjectRevision | None, query: str,
                      history: list[dict], error: str | None = None,
                      failed: dict | None = None) -> ProjectRevision:
        if self.client is None:
            self.client = AsyncOpenAI(base_url=config.openai_api_base, api_key=config.openai_api_key or "EMPTY", timeout=90, max_retries=0)
        profile = project["profile"] or {}
        context = {
            "description": project["description"],
            "profile": profile,
            "current_revision": current.model_dump() if current else None,
            "working_revision": failed or (current.model_dump() if current else None),
            "contract": ProjectRevision.model_json_schema(),
            "request": query,
            "recent_conversation": [{"role": h["role"], "content": h["content"]} for h in history[-8:]],
        }
        if error:
            context.update(validation_error=error[-16000:], failed_proposal=failed)
        response_format: dict[str, Any] = {"type": "json_object"}
        if config.strict_model_outputs:
            schema = PATCH_SCHEMA if context["working_revision"] else strict_schema(ProjectRevision.model_json_schema())
            response_format = {"type": "json_schema", "json_schema": {"name": "project_patch" if context["working_revision"] else "project_revision", "strict": True, "schema": schema}}
        try:
            response = await self.client.chat.completions.create(
                model=config.openai_model_name, temperature=0.1,
                response_format=response_format,
                messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(context)}],
            )
        except APIError as exc:
            raise ModelUnavailableError(f"Model request failed: {exc}. Check the endpoint, credentials, model and strict_model_outputs setting.") from exc
        if getattr(response.choices[0].message, "refusal", None):
            raise ModelUnavailableError("The model declined this request")
        payload = json.loads(response.choices[0].message.content or "{}")
        if "changes" in payload:
            base = failed or (current.model_dump() if current else None)
            if base is None:
                raise ValueError("A new project requires a complete revision")
            summary = payload.get("summary", "Project refined")
            for change in payload["changes"]:
                if "value_json" in change:
                    change["value"] = json.loads(change["value_json"]) if change["value_json"] is not None else None
            payload = apply_changes(base, payload["changes"])
            payload["summary"] = summary
        payload.update(revision_id=str(uuid4()), parent_revision_id=current.revision_id if current else None, created_at=now())
        try:
            return ProjectRevision.model_validate(payload)
        except ValueError as exc:
            raise ProposalValidationError(str(exc), payload) from exc
