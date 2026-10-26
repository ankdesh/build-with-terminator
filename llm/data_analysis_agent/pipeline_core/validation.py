"""Validate generated source, dependency graphs, controls, and widget bindings."""

import ast
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline_core.models import ProjectRevision

SAFE_MODULES = {
    "pandas", "numpy", "scipy", "statsmodels", "math", "datetime", "re",
    "statistics", "collections", "itertools", "functools", "decimal", "typing", "json",
    "pipeline_core",
}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "breakpoint", "input",
}


def validate_source(code: str, function: str) -> None:
    tree = ast.parse(code)
    if not any(isinstance(n, ast.FunctionDef) and n.name == function for n in tree.body):
        raise ValueError(f"Source must define function {function}(inputs, parameters, context)")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if isinstance(node, ast.ImportFrom) and node.level:
                raise ValueError("Relative imports are not supported")
            for module in modules:
                if module.split(".")[0] not in SAFE_MODULES:
                    raise ValueError(f"Unsupported import: {module}")
                if module.startswith("pipeline_core") and module != "pipeline_core.statistics":
                    raise ValueError("Only pipeline_core.statistics is available to generated code")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Private runtime attributes are not supported")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Private runtime names are not supported")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            raise ValueError(f"Unsupported call: {node.func.id}")
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            if name in {"now", "today", "utcnow"}:
                raise ValueError("Use an explicit date parameter or the dataset's date range instead of the system clock")
            if name in {"default_rng", "RandomState"}:
                seeds = list(node.args) + [kw.value for kw in node.keywords if kw.arg == "seed"]
                if not seeds or any(isinstance(seed, ast.Constant) and seed.value is None for seed in seeds):
                    raise ValueError("Random generators require an explicit saved seed")
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
    if len(functions[0].args.args) != 3:
        raise ValueError("Step functions must have three arguments: inputs, parameters, context")


def ordered_steps(revision: "ProjectRevision") -> list[Any]:
    available = {"data"}
    pending = list(revision.steps)
    ordered: list[Any] = []
    while pending:
        ready = [s for s in pending if set(s.inputs) <= available]
        if not ready:
            raise ValueError("Pipeline has a cycle or a missing input")
        # All cleanup must precede analysis so filters operate on cleaned data.
        ready.sort(key=lambda s: s.stage != "cleanup")
        step = ready[0]
        if step.stage == "cleanup" and any(s.stage == "analysis" for s in ordered):
            raise ValueError("Cleanup steps cannot depend on analysis steps")
        ordered.append(step)
        available.update(step.outputs)
        pending.remove(step)
    return ordered


def validate_revision(revision: "ProjectRevision") -> None:
    if {s.stage for s in revision.steps} != {"cleanup", "analysis"}:
        raise ValueError("Projects require separate cleanup and analysis steps")
    if len({s.id for s in revision.steps}) != len(revision.steps):
        raise ValueError("Step identifiers must be unique")
    outputs = [name for s in revision.steps for name in s.outputs]
    if "data" in outputs or len(set(outputs)) != len(outputs):
        raise ValueError("Output names must be unique and cannot replace data")
    if any(not name.isidentifier() or name.startswith("_") for name in outputs):
        raise ValueError("Output names must be public Python identifiers")
    parameter_ids = {p.id for p in revision.parameters}
    if len(parameter_ids) != len(revision.parameters):
        raise ValueError("Parameter identifiers must be unique")
    for step in revision.steps:
        validate_source(step.code, step.function)
        if step.parameters_used is not None and not set(step.parameters_used) <= parameter_ids:
            raise ValueError(f"Unknown parameter in step {step.id}")
        if step.stage == "cleanup" and not step.inputs:
            raise ValueError("Cleanup requires an input")
    ordered_steps(revision)
    cleanup_outputs = {o for s in revision.steps if s.stage == "cleanup" for o in s.outputs} | {"data"}
    for p in revision.parameters:
        if p.minimum is not None and p.maximum is not None and p.minimum > p.maximum:
            raise ValueError(f"Invalid limits for {p.id}")
        if p.filter_column and p.filter_artifact not in cleanup_outputs:
            raise ValueError("Filters must bind to source data or a cleanup output")
    if len({w.id for w in revision.dashboard.widgets}) != len(revision.dashboard.widgets):
        raise ValueError("Widget identifiers must be unique")
    for widget in revision.dashboard.widgets:
        if widget.output not in outputs:
            raise ValueError(f"Widget {widget.id} references an unknown output")
    validate_parameters(revision, {})


def validate_parameters(revision: "ProjectRevision", supplied: dict[str, Any]) -> dict[str, Any]:
    known = {p.id for p in revision.parameters}
    if not supplied.keys() <= known:
        raise ValueError("Unknown dashboard parameter")
    result = revision.default_parameters() | supplied
    for spec in revision.parameters:
        value = result[spec.id]
        if value is None:
            if not spec.filter_column and spec.kind in {"number", "integer", "boolean"}:
                raise ValueError(f"{spec.label} requires a value")
            continue
        if spec.kind in {"number", "integer"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{spec.label} requires a finite number")
            if spec.kind == "integer" and int(value) != value:
                raise ValueError(f"{spec.label} requires an integer")
            if spec.kind == "integer":
                result[spec.id] = int(value)
            if spec.minimum is not None and value < spec.minimum or spec.maximum is not None and value > spec.maximum:
                raise ValueError(f"{spec.label} is outside its limits")
        elif spec.kind == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{spec.label} requires a boolean")
        elif spec.kind == "string" and not isinstance(value, str):
            raise ValueError(f"{spec.label} requires text")
        if spec.kind == "select" and spec.choices and not spec.filter_column and value not in spec.choices:
            raise ValueError(f"Invalid choice for {spec.label}")
    return result
