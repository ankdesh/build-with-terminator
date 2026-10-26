"""Deterministic pipeline execution. Invoke only inside an isolated worker."""

import csv
import hashlib
import io
import json
import math
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from pipeline_core.models import ProjectRevision
from pipeline_core.validation import ordered_steps, validate_parameters


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_json(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [safe_json(v) for v in value]
    if isinstance(value, np.generic):
        return safe_json(value.item())
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise ValueError(f"Unsupported output value: {type(value).__name__}")


def read_input(path: Path, revision: ProjectRevision) -> pd.DataFrame:
    contract = revision.input_contract
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("CSV exceeds the 100 MB input limit")
    with path.open(encoding=contract.encoding, newline="") as stream:
        reader = csv.reader(stream, delimiter=contract.delimiter)
        header = next(reader, [])
        for number, row in enumerate(reader, 2):
            if row and len(row) != len(header):
                raise ValueError(f"CSV row {number} has {len(row)} cells; expected {len(header)}")
    if not header or any(not name.strip() for name in header) or len(header) != len(set(header)):
        raise ValueError("CSV column names must be non-empty and unique")
    missing = {c.name for c in contract.columns} - set(header)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    frame = pd.read_csv(path, encoding=contract.encoding, sep=contract.delimiter,
                        dtype={c.name: "string" for c in contract.columns if c.dtype == "string"})
    if frame.empty:
        raise ValueError("CSV contains no data rows")
    for col in contract.columns:
        try:
            if not col.nullable and frame[col.name].isna().any():
                raise ValueError("Missing values are not allowed")
            if col.dtype in {"number", "integer"}:
                series = pd.to_numeric(frame[col.name], errors="raise")
                if not np.isfinite(series.dropna()).all():
                    raise ValueError("Non-finite numbers are not allowed")
                if col.dtype == "integer":
                    if (series.dropna() % 1 != 0).any():
                        raise ValueError("Expected integers")
                    series = series.astype("Int64")
                frame[col.name] = series
            elif col.dtype == "datetime":
                frame[col.name] = pd.to_datetime(frame[col.name], format=col.date_format, errors="raise")
            elif col.dtype == "boolean":
                mapped = frame[col.name].astype("string").str.lower().map({"true": True, "false": False, "1": True, "0": False})
                if (frame[col.name].notna() & mapped.isna()).any():
                    raise ValueError("Expected true, false, 1, or 0")
                frame[col.name] = mapped.astype("boolean")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid values in column {col.name}: {exc}") from exc
    return frame


def describe_change(before: pd.DataFrame, after: pd.DataFrame) -> dict[str, Any]:
    common_columns = before.columns.intersection(after.columns)
    # Duplicate or reset indexes make row matching ambiguous. Report this explicitly.
    comparable = before.index.is_unique and after.index.is_unique
    changed_cells = None
    if comparable:
        common_rows = before.index.intersection(after.index)
        left = before.loc[common_rows, common_columns].astype("string").fillna("<NULL>")
        right = after.loc[common_rows, common_columns].astype("string").fillna("<NULL>")
        changed_cells = int((left != right).to_numpy().sum())
    return {
        "before_rows": len(before), "after_rows": len(after),
        "removed_rows": max(0, len(before) - len(after)),
        "before_missing_cells": int(before.isna().sum().sum()),
        "after_missing_cells": int(after.isna().sum().sum()),
        "changed_cells_in_matched_rows": changed_cells,
        "columns_removed": [str(c) for c in before.columns if c not in after.columns],
        "columns_added": [str(c) for c in after.columns if c not in before.columns],
        "changed": not before.equals(after),
    }


class PipelineEngine:
    """Run saved functions, serialize full artifacts, and reuse matching checkpoints."""

    def execute(
        self, revision: ProjectRevision, input_path: Path, supplied_parameters: dict[str, Any],
        output_dir: Path, cache_dir: Path | None = None,
        notify: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        parameters = validate_parameters(revision, supplied_parameters)
        from pipeline_core.bundle import installed_versions
        runtime_versions = installed_versions()
        output_dir.mkdir(parents=True, exist_ok=True)
        frame = read_input(input_path, revision)
        artifacts: dict[str, Any] = {"data": frame}
        hashes = {"data": fingerprint(input_path)}
        previous: dict[str, Any] = {}
        if cache_dir and (cache_dir / "cache.json").exists():
            previous = json.loads((cache_dir / "cache.json").read_text())
        cache: dict[str, Any] = {}
        cleanup: list[dict[str, Any]] = []
        logs: list[dict[str, Any]] = []
        options: dict[str, list[Any]] = {}
        applied_filters = False

        def emit(event: dict[str, Any]) -> None:
            logs.append(event)
            if notify:
                notify(event)

        def apply_filters() -> None:
            for spec in revision.parameters:
                if not spec.filter_column:
                    continue
                value = parameters[spec.id]
                target = artifacts.get(spec.filter_artifact)
                if not isinstance(target, pd.DataFrame) or spec.filter_column not in target.columns:
                    raise ValueError(f"Filter {spec.label} references a missing column")
                options[spec.id] = safe_json(target[spec.filter_column].dropna().unique().tolist()[:200])
            for spec in revision.parameters:
                if not spec.filter_column or parameters[spec.id] is None:
                    continue
                target = artifacts[spec.filter_artifact]
                column, value = target[spec.filter_column], parameters[spec.id]
                if spec.filter_operator == "eq":
                    mask = column == value
                elif spec.filter_operator == "gte":
                    mask = column >= value
                elif spec.filter_operator == "lte":
                    mask = column <= value
                else:
                    mask = column.astype("string").str.contains(str(value), regex=False, na=False)
                artifacts[spec.filter_artifact] = target.loc[mask.fillna(False)].copy()
                hashes[spec.filter_artifact] = hashlib.sha256(
                    (hashes[spec.filter_artifact] + json.dumps({spec.id: value}, sort_keys=True)).encode()
                ).hexdigest()

        for step in ordered_steps(revision):
            if step.stage == "analysis" and not applied_filters:
                apply_filters()
                applied_filters = True
            start = time.monotonic()
            # Dynamic Python may read any parameter, so the complete parameter map
            # is hashed even when parameters_used advertises a smaller set.
            signature = hashlib.sha256(json.dumps({
                "code": step.code, "function": step.function, "stage": step.stage,
                "inputs": {name: hashes[name] for name in step.inputs},
                "outputs": step.outputs, "parameters": parameters, "seed": revision.seed,
                "runtime": "0.2.0", "versions": runtime_versions,
            }, sort_keys=True).encode()).hexdigest()
            reused = False
            step_cache = previous.get(step.id, {})
            before = next((artifacts[n] for n in step.inputs if isinstance(artifacts[n], pd.DataFrame)), None)
            emit({"event": "step", "step_id": step.id, "title": step.title, "status": "running"})
            if cache_dir and step_cache.get("signature") == signature:
                produced = {}
                for name, record in step_cache["outputs"].items():
                    filename = record["file"]
                    if Path(filename).name != filename:
                        raise ValueError("Invalid cached artifact path")
                    source = cache_dir / filename
                    if fingerprint(source) != record["sha256"]:
                        raise ValueError("Cached artifact integrity check failed")
                    produced[name] = self._load(source, record["kind"])
                reused = True
            else:
                namespace: dict[str, Any] = {"pd": pd, "np": np, "__name__": "saved_pipeline"}
                # Source has already passed static checks. OS isolation is provided
                # by ProcessRunner, not by this namespace or the AST policy.
                exec(compile(step.code, f"<step:{step.id}>", "exec"), namespace)
                inputs = {n: artifacts[n].copy(deep=True) if isinstance(artifacts[n], pd.DataFrame) else safe_json(artifacts[n]) for n in step.inputs}
                np.random.seed(revision.seed)
                produced = namespace[step.function](inputs, dict(parameters), {"seed": revision.seed})
                if not isinstance(produced, dict) or set(produced) != set(step.outputs):
                    raise ValueError(f"Step {step.id} must return exactly these outputs: {step.outputs}")
            records = {}
            for name, value in produced.items():
                if isinstance(value, pd.Series):
                    value = value.to_frame()
                if step.stage == "cleanup" and not isinstance(value, pd.DataFrame):
                    raise ValueError("Cleanup outputs must be DataFrames so their impact can be reviewed")
                record = self._save(output_dir, name, value)
                artifacts[name] = value
                hashes[name] = record["sha256"]
                records[name] = record
                if step.stage == "cleanup" and isinstance(value, pd.DataFrame) and before is not None:
                    impact = describe_change(before, value)
                    cleanup.append({"step_id": step.id, "title": step.title, "rationale": step.rationale,
                                    "requires_confirmation": step.changes_meaning or impact["changed"], **impact})
            cache[step.id] = {"signature": signature, "outputs": records}
            emit({"event": "step", "step_id": step.id, "title": step.title,
                  "status": "succeeded", "cached": reused, "duration_ms": round((time.monotonic() - start) * 1000, 2)})

        rendered: dict[str, Any] = {}
        widget_views: dict[str, Any] = {}
        for widget in revision.dashboard.widgets:
            value = artifacts[widget.output]
            if widget.output not in rendered:
                if isinstance(value, pd.DataFrame):
                    rendered[widget.output] = {"kind": "table", "columns": [str(c) for c in value.columns],
                        "rows": safe_json(value.head(500).to_dict("records")), "total_rows": len(value)}
                elif isinstance(value, dict):
                    rendered[widget.output] = {"kind": "chart", "value": safe_json(value)}
                else:
                    rendered[widget.output] = {"kind": "text" if isinstance(value, str) else "metric", "value": safe_json(value)}
            if widget.kind == "table":
                if not isinstance(value, pd.DataFrame):
                    raise ValueError(f"Table {widget.title} requires a DataFrame")
                widget_views[widget.id] = rendered[widget.output]
            elif widget.kind == "chart":
                if isinstance(value, pd.DataFrame):
                    if widget.chart_binding is None:
                        raise ValueError(f"Chart {widget.title} binds DataFrame {widget.output}. Set its chart_binding with kind, x column, and y columns, or return an ECharts option object from Python.")
                    chart_value = chart_from_frame(value, widget.chart_binding)
                elif isinstance(value, dict) and isinstance(value.get("option"), dict):
                    chart_value = safe_json(value)
                elif isinstance(value, dict) and ("series" in value or "dataset" in value):
                    chart_value = {"option": safe_json(value)}
                else:
                    raise ValueError(f"Chart {widget.title} requires a DataFrame with chart_binding or an ECharts option object")
                validate_chart(chart_value["option"])
                widget_views[widget.id] = {"kind": "chart", "value": chart_value}
            elif widget.kind == "metric":
                if isinstance(value, (dict, list, pd.DataFrame)):
                    raise ValueError(f"Metric {widget.title} requires a scalar")
                widget_views[widget.id] = {"kind": "metric", "value": safe_json(value)}
            else:
                if isinstance(value, (dict, list, pd.DataFrame)):
                    raise ValueError(f"Text {widget.title} must be computed text or a scalar")
                widget_views[widget.id] = {"kind": "text", "value": str(safe_json(value)) if value is not None else ""}
        (output_dir / "cache.json").write_text(json.dumps(cache, allow_nan=False))
        result = {"outputs": rendered, "widgets": widget_views, "cleanup_impacts": cleanup, "steps": logs,
                  "parameter_options": options, "input_rows": len(frame), "input_hash": fingerprint(input_path)}
        (output_dir / "result.json").write_text(json.dumps(result, allow_nan=False))
        return result

    @staticmethod
    def _save(output_dir: Path, name: str, value: Any) -> dict[str, str]:
        if isinstance(value, pd.DataFrame):
            if not value.columns.is_unique or any(not isinstance(c, str) for c in value.columns):
                raise ValueError("Table columns must have unique string names")
            path = output_dir / f"{name}.frame.json"
            path.write_text(value.to_json(orient="table", date_format="iso", double_precision=15))
            value.to_csv(output_dir / f"{name}.csv", index=False)
            kind = "frame"
        else:
            path = output_dir / f"{name}.json"
            path.write_text(json.dumps(safe_json(value), allow_nan=False))
            kind = "json"
        return {"kind": kind, "file": path.name, "sha256": fingerprint(path)}

    @staticmethod
    def _load(path: Path, kind: str) -> Any:
        if kind == "frame":
            return pd.read_json(io.StringIO(path.read_text()), orient="table")
        return json.loads(path.read_text())


def validate_chart(option: Any) -> None:
    """Keep saved charts JSON-only and prevent remote asset or hyperlink requests."""
    if isinstance(option, dict):
        for key, value in option.items():
            if key in {"link", "href", "image"}:
                raise ValueError("Chart links and image assets are not supported offline")
            if key in {"data", "source"} and isinstance(value, (list, tuple)) and len(value) > 5000:
                raise ValueError("Chart data exceeds 5000 items; aggregate or sample chart data explicitly. Full tables remain available for export.")
            validate_chart(value)
    elif isinstance(option, (list, tuple)):
        for value in option:
            validate_chart(value)
    elif isinstance(option, str) and option.startswith(("http://", "https://", "//", "image://")):
        raise ValueError("External chart resources are not supported offline")


def chart_from_frame(frame: pd.DataFrame, binding: Any) -> dict[str, Any]:
    """Map declared columns to standard charts without guessing field meaning."""
    required = [binding.x, *binding.y]
    if any(name not in frame.columns for name in required):
        raise ValueError("Chart binding references a missing column")
    if len(frame) > 5000:
        raise ValueError("Chart input exceeds 5000 rows; aggregate or sample it explicitly")
    for name in binding.y:
        if not pd.api.types.is_numeric_dtype(frame[name]):
            raise ValueError(f"Chart series {name} must be numeric")
    option: dict[str, Any]
    if binding.kind == "pie":
        if len(binding.y) != 1:
            raise ValueError("Pie charts require one numeric series")
        option = {"series": [{"type": "pie", "data": [
            {"name": str(row[binding.x]), "value": safe_json(row[binding.y[0]])} for _, row in frame.iterrows()]}]}
    elif binding.kind == "scatter":
        if not pd.api.types.is_numeric_dtype(frame[binding.x]):
            raise ValueError("Scatter chart x values must be numeric")
        option = {"xAxis": {"type": "value", "name": binding.x_label or binding.x},
            "yAxis": {"type": "value", "name": binding.y_label or ", ".join(binding.y)},
            "series": [{"name": name, "type": "scatter", "data": safe_json(frame[[binding.x, name]].values.tolist())} for name in binding.y]}
    else:
        option = {"xAxis": {"type": "category", "name": binding.x_label or binding.x,
            "data": safe_json(frame[binding.x].tolist())},
            "yAxis": {"type": "value", "name": binding.y_label or ", ".join(binding.y)},
            "series": [{"name": name, "type": binding.kind, "data": safe_json(frame[name].tolist())} for name in binding.y]}
    return {"option": option}
