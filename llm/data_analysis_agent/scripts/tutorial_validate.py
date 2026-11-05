"""Validate published tutorial prompts through the real builder service and LLM."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import platform
import json
import re
from pathlib import Path
import sys
import threading
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.dataset_import import import_csv
from backend.services.project_agent import ProjectAgent
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.workspace_service import Workspaces
from backend.services.llm_gateway import llm
from config import config
from pipeline_core.bundle import installed_versions
from pipeline_core.engine import safe_json
from pipeline_core.models import now
from backend.services.chat_store import ChatStore
from scripts.tutorial_data import PACK, sha
from scripts.tutorial_specs import LESSONS, expected, checks


def prompt_hash(lesson: dict) -> str:
    return hashlib.sha256(json.dumps(lesson["prompts"]).encode()).hexdigest()


def title_key(title: str) -> str:
    """Allow cosmetic capitalization, punctuation and unit suffixes."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)", "", title).lower())


def widget(revision: Any, run: Any, title: str) -> dict:
    matches = [item for item in revision.dashboard.widgets if title_key(item.title) == title_key(title)]
    if len(matches) != 1:
        raise AssertionError(f"Expected one widget titled {title!r}; got {[w.title for w in revision.dashboard.widgets]}")
    return run.result["widgets"][matches[0].id]


def verify_metrics(key: str, frame: pd.DataFrame, revision: Any, run: Any, parameters: dict) -> dict:
    wanted = expected(key, frame, parameters)
    results = {}
    for title, value in wanted.items():
        actual = widget(revision, run, title).get("value")
        tolerance = .00051 if title == "Mean quality" else .0051
        if isinstance(value, (int, np.integer)):
            assert actual == value, f"{title}: actual={actual}; expected={value}"
        else:
            assert isinstance(actual, (int, float)) and abs(actual - value) <= tolerance, f"{title}: actual={actual}; expected={value}"
        results[title] = {"expected": float(value) if isinstance(value, np.floating) else value, "actual": actual, "passed": True}
    return results


def actual_parameters(revision: Any, values: dict) -> dict:
    result = {}
    for name, value in values.items():
        if any(p.id == name for p in revision.parameters):
            result[name] = value
        elif name == "country":
            match = next((p for p in revision.parameters if p.filter_column == "Country"), None)
            assert match is not None, "Add the requested country select control: id=country, filter_column=Country, filter_artifact=cleaned, default=null. Preserve discount_pct."
            result[match.id] = value
        else:
            raise AssertionError(f"The root parameters array is missing control {name}. Add a ParameterSpec object to /parameters/-, with id={name}, label={name}, kind={'select' if name in {'wine_type','calendar_year','species'} else 'integer'}, default={'null' if name in {'wine_type','calendar_year','species'} else 14 if name == 'horizon' else 7}, filter_column={name if name in {'wine_type','calendar_year','species'} else 'null'}, filter_artifact=cleaned, filter_operator=eq, choices=[], minimum=null, maximum=null. Set appropriate numeric bounds if needed. This is a root parameter, NOT a widget, NOT a step output and NOT just a parameters_used entry. Preserve existing source and widgets.")
    return result


def check_chart_values(key: str, frame: pd.DataFrame, revision: Any, run: Any) -> None:
    """Compare plotted values, not just dashboard metric totals."""
    def option(title): return widget(revision, run, title)['value']['option']
    def series(title):
        value = option(title)['series']
        return value if isinstance(value, list) else [value]
    def numbers(data): return np.asarray([v.get('value') if isinstance(v, dict) else v for v in data], dtype=float)
    def equal(actual, wanted, label):
        a, b = np.asarray(actual, dtype=float), np.asarray(wanted, dtype=float)
        assert a.shape == b.shape and np.allclose(a, b, atol=.005, rtol=1e-9), f'{label}: plotted values differ from independently computed source values. For sales charts aggregate Quantity*UnitPrice. For calendar heatmaps use zero-based coordinates x=month-1 and y=weekday, and mean cnt (not sum).'
    if key == 'penguins':
        clean = frame.dropna(subset=['bill_length_mm','bill_depth_mm','flipper_length_mm','body_mass_g'])
        counts = clean.species.value_counts()
        o = option('Species counts')
        equal(numbers(series('Species counts')[0]['data']), counts.reindex(o['xAxis']['data']).values, 'Species counts')
        data = series('Species share')[0]['data']
        actual = numbers(data); actual = actual / actual.sum()
        equal(actual, [counts[d['name']] / len(clean) for d in data], 'Species share')
        equal(series('Mass and flipper length')[0]['data'], clean[['flipper_length_mm','body_mass_g']].values, 'Scatter coordinates')
    elif key == 'retail':
        valid = ~frame.InvoiceNo.astype(str).str.upper().str.startswith('C') & frame.Quantity.gt(0) & frame.UnitPrice.gt(0)
        sales = frame.loc[valid].copy()
        sales['sales_value'] = sales.Quantity * sales.UnitPrice
        sales['date'] = pd.to_datetime(sales.InvoiceDate).dt.strftime('%Y-%m-%d')
        for title, column in [('Sales by country','Country'), ('Daily sales','date'), ('Top invoice items','Description')]:
            grouped = sales.groupby(column).sales_value.sum()
            o = option(title)
            labels = o['yAxis']['data'] if title == 'Top invoice items' else o['xAxis']['data']
            if column == 'date': labels = [str(v)[:10] for v in labels]
            equal(numbers(series(title)[0]['data']), grouped.reindex(labels).values, title)
        detail = widget(revision, run, 'Invoice detail')
        for row in detail['rows']:
            equal([row['sales_value']], [row['Quantity'] * row['UnitPrice']], 'Invoice detail sales_value')
    elif key == 'wine':
        hist, _ = np.histogram(frame.alcohol, bins=np.arange(8,15.5,.5))
        equal(numbers(series('Alcohol distribution')[0]['data']), hist, 'Alcohol histogram')
        o = option('Alcohol by wine type')
        groups = o['xAxis']['data']
        wanted = [np.quantile(frame.loc[frame.wine_type.eq(g),'alcohol'], [0,.25,.5,.75,1]) for g in groups]
        equal(series('Alcohol by wine type')[0]['data'], wanted, 'Alcohol boxplot quantiles')
    else:
        source = frame.sort_values('dteday')
        lines = series('Daily demand')
        arrays = [numbers(s['data']) for s in lines]
        for wanted in [source.cnt.values, source.cnt.rolling(7,min_periods=1).mean().values]:
            assert any(a.shape == wanted.shape and np.allclose(a,wanted,atol=.005) for a in arrays), 'Daily demand or rolling mean differs from source'
        area = series('Rider mix')
        assert all(s.get('stack') == area[0].get('stack') and s.get('stack') and 'areaStyle' in s for s in area), "Rider mix must be a stacked area chart: both line series require stack='riders' and areaStyle={}"
        equal(sum(numbers(s['data']) for s in area), source.cnt.values, 'Rider mix stacked total')
        o = option('Calendar pattern'); cells = series('Calendar pattern')[0]['data']
        month_labels, weekdays = o['xAxis']['data'], o['yAxis']['data']
        grouped = source.groupby(['mnth','weekday']).cnt.mean()
        assert len(cells) == 84, 'Calendar pattern must have all month/weekday means'
        # Both category encodings use month and weekday order specified in the prompt.
        for x, y, value in cells:
            equal([value], [grouped.loc[int(x)+1,int(y)]], 'Calendar mean')


def check_extra(lesson: dict, frame: pd.DataFrame, revision: Any, run: Any, parameters: dict | None = None) -> dict:
    key = lesson["key"]
    if key == 'bike' and (parameters or {}).get('calendar_year') is not None:
        frame = frame.loc[pd.to_datetime(frame.dteday).dt.year.eq(parameters['calendar_year'])]
    check_chart_values(key, frame, revision, run)
    for title in lesson["charts"]:
        item = widget(revision, run, title)
        assert item["kind"] == "chart" and item["value"].get("option"), f"Missing chart: {title}"
    if key == "wine":
        from scipy.stats import spearmanr
        option = widget(revision, run, "Measurement correlations")["value"]["option"]
        series = option["series"] if isinstance(option["series"], list) else [option["series"]]
        cells = next(s["data"] for s in series if s["type"] == "heatmap")
        assert len(cells) == 36, "Correlation heatmap must contain 36 cells"
        matrix = {(int(c[0]), int(c[1])): float(c[2]) for c in cells}
        for i in range(6): assert abs(matrix[i, i] - 1) < 1e-6
        assert abs(matrix[0, 5] - float(spearmanr(frame.alcohol, frame.quality).statistic)) < 1e-6
        return {"heatmap_cells": 36, "correlation_matches_scipy": True}
    if key == "bike":
        from statsmodels.tsa.arima.model import ARIMA
        values = frame.sort_values("dteday").cnt.to_numpy(dtype=float)
        horizon = int((parameters or {}).get('horizon', 14))
        holdout = max(2, min(horizon, len(frame) // 5))
        predictions = np.asarray(ARIMA(values[:-holdout], order=(1, 1, 0)).fit().forecast(holdout))
        mae = float(np.abs(predictions - values[-holdout:]).mean())
        baseline = float(np.abs(values[-holdout-1] - values[-holdout:]).mean())
        for title, number in [("Holdout MAE", mae), ("Baseline MAE", baseline)]:
            assert abs(float(widget(revision, run, title)["value"]) - number) <= .0051, f"Invalid chronological {title}"
        forecast = widget(revision, run, "Demand forecast")["value"]["option"]
        axes = forecast["xAxis"] if isinstance(forecast["xAxis"], list) else [forecast["xAxis"]]
        dates = axes[0].get("data", [])
        last = pd.to_datetime(frame.dteday).max()
        future = pd.date_range(last + pd.Timedelta(days=1), periods=horizon, freq="D").strftime("%Y-%m-%d").tolist()
        assert [str(date)[:10] for date in dates[-horizon:]] == future, "Forecast dates must follow the final input date"
        series = forecast["series"] if isinstance(forecast["series"], list) else [forecast["series"]]
        assert len(series) >= 4, "Actual, forecast, lower-bound and interval-fill series are required"
        fitted = ARIMA(values, order=(1, 1, 0)).fit().get_forecast(horizon)
        point = np.asarray(fitted.predicted_mean)
        interval = np.asarray(fitted.conf_int(alpha=.05))
        arrays = []
        for item in series:
            data = item.get("data", [])[-horizon:]
            if len(data) != horizon: continue
            try:
                values_array = np.array([d.get("value") if isinstance(d, dict) else d for d in data], dtype=float)
                if values_array.shape == (horizon,): arrays.append(values_array)
            except (TypeError, ValueError): continue
        for wanted in (point, interval[:, 0], interval[:, 1] - interval[:, 0]):
            assert any(np.allclose(item, wanted, atol=.005) for item in arrays), "Forecast points or model interval arrays differ from independent ARIMA calculation"
        assert any(s.get("stackStrategy") == "all" for s in series), "Interval stack must support negative lower bounds"
        return {"training_observations": len(frame)-holdout, "holdout_observations": holdout, "mae": mae, "baseline_mae": baseline,
                "future_days": horizon, "forecast_and_intervals_match_independent_fit": True}
    if key == "retail":
        option = widget(revision, run, "Monthly country mix")["value"]["option"]
        series = option["series"] if isinstance(option["series"], list) else [option["series"]]
        total = sum(float(item.get("value", 0) if isinstance(item, dict) else item or 0) for s in series for item in s["data"])
        assert abs(total - expected(key, frame)["Sales value"]) < .01, "Monthly country mix includes invalid lines: filter cleaned.loc[cleaned.is_valid_sale].copy() BEFORE computing month or grouping. Exclude C-prefix cancellations and Quantity<=0 or UnitPrice<=0, just as Sales value does. Return the declared output name. Stacked totals must equal Sales value."
        detail = widget(revision, run, "Invoice detail")
        assert detail["total_rows"] == expected(key, frame)["Invoice lines"], "Full detail rows were truncated"
        return {"stacked_values_reconcile": True, "full_table_rows": detail["total_rows"]}
    text = str(widget(revision, run, "Reading the scatter")["value"])
    correlation = str(dict(checks(key, frame))["Pearson r: flipper length / body mass"])
    assert f"{float(correlation):.3f}" in text, "Scatter note must contain the calculated Pearson coefficient"
    return {"scatter_note_matches_scipy": True}


async def validate(keys: list[str], state_dir: Path) -> None:
    manifest = json.loads((PACK / "manifest.json").read_text())
    report_path = PACK / "validation.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {"schema_version": 1, "lessons": {}}
    previous_versions = report.get('runtime_versions')
    runtime_versions = installed_versions()
    report.update(model=config.openai_model_name, endpoint=config.openai_api_base, runtime_versions=runtime_versions)
    report['tool_versions'] = {name: importlib.metadata.version(name) for name in ['openai','pandas','numpy','scipy','statsmodels','openpyxl']}
    report['tool_versions'].update(python=platform.python_version(), echarts=json.loads((ROOT / 'frontend/node_modules/echarts/package.json').read_text())['version'])
    store = ProjectStore(state_dir)
    audit_dir = state_dir / "model_responses"
    audit_dir.mkdir(exist_ok=True)
    class AuditGateway:
        async def complete(self, messages, response_format=None):
            content = await llm.complete(messages, response_format)
            index = len(list(audit_dir.glob("*.json"))) + 1
            # Only public tutorial context and generated source; never credentials.
            (audit_dir / f"{index:03}.json").write_text(json.dumps({"messages": messages, "response": content}, indent=2))
            return content
    agent = ProjectAgent()
    agent.llm = AuditGateway()
    service = ProjectService(store, agent=agent)
    workspaces = Workspaces(store)
    (PACK / "reference").mkdir(exist_ok=True)
    try:
        for lesson in LESSONS:
            key = lesson["key"]
            if keys and key not in keys: continue
            previous = report["lessons"].get(key, {})
            if (previous_versions == runtime_versions and previous.get("status") == "passed" and previous.get("prompt_sha256") == prompt_hash(lesson)
                    and previous.get("input_sha256") == manifest["datasets"][key]["sha256"]
                    and previous.get("model") == config.openai_model_name and (PACK / "reference" / f"{key}.json").exists()):
                print(f"[{key}] Reusing matching passed validation", flush=True)
                continue
            entry = {"status": "running", "started_at": now(), "model": config.openai_model_name,
                     "input_sha256": manifest["datasets"][key]["sha256"], "prompt_sha256": prompt_hash(lesson), "prompts": [], "repairs": []}
            report["lessons"][key] = entry
            report_path.write_text(json.dumps(safe_json(report), indent=2))
            path = PACK / "data" / lesson["file"]
            frame = pd.read_csv(path)
            view = import_csv(store, path, description=lesson["context"])
            project_id = view["project"]["id"]
            entry["project_id"] = project_id
            print(f"[{key}] Created isolated project {project_id}", flush=True)
            def emit(event: dict) -> None:
                if event["event"] == "status": print(f"[{key}] {event.get('message')}", flush=True)
            async def execute() -> tuple[Any, Any]:
                revision = workspaces.compile(project_id, workspaces.get(project_id)["version"])
                run = await service.execute(project_id, revision, {}, emit, threading.Event())
                if run.status != "succeeded": raise AssertionError(run.error)
                return revision, run
            try:
                for number, prompt in enumerate(lesson["prompts"], 1):
                    print(f"[{key}] Testing published prompt {number}", flush=True)
                    proposal = await service.build(project_id, prompt, emit, threading.Event())
                    if proposal.get("kind") == "proposal":
                        ChatStore(store).apply(project_id, proposal["id"])
                    for attempt in range(3):
                        try:
                            revision, run = await execute()
                            metrics = verify_metrics(key, frame, revision, run, {})
                            actual_parameters(revision, lesson["filter"])
                            if lesson.get("scenario") and (key != "bike" or number == len(lesson["prompts"])):
                                actual_parameters(revision, lesson["scenario"])
                            extra = check_extra(lesson, frame, revision, run) if number == len(lesson["prompts"]) else {}
                            break
                        except Exception as exc:
                            if attempt == 2: raise
                            repair = f"Repair the current tutorial revision. Preserve its requested widgets, exact titles and metric definitions. Run/independent validation found: {exc}. Correct the saved Python, bindings or chart arrays as needed. Do not hard-code answers. I will select Run."
                            entry["repairs"].append({"prompt_number": number, "request": repair})
                            print(f"[{key}] Repair {attempt+1}: {exc}", flush=True)
                            proposal = await service.build(project_id, repair, emit, threading.Event())
                            if proposal.get("kind") == "proposal":
                                ChatStore(store).apply(project_id, proposal["id"])
                    entry["prompts"].append({"number": number, "text": prompt, "status": "passed", "metrics": metrics, "extra_checks": extra})
                    report_path.write_text(json.dumps(safe_json(report), indent=2))
                baseline_revision, baseline_run = revision, run
                variants = [("filtered", lesson["filter"])]
                if lesson.get("scenario"): variants.append(("scenario", lesson["scenario"]))
                entry["variants"] = {}
                for name, values in variants:
                    params = actual_parameters(revision, values)
                    changed = await service.execute(project_id, revision, params, emit, threading.Event())
                    assert changed.status == "succeeded", changed.error
                    entry["variants"][name] = {"parameters": values, "metrics": verify_metrics(key, frame, revision, changed, values)}
                    if key == "bike": entry["variants"][name]["extra_checks"] = check_extra(lesson, frame, revision, changed, values)
                replacement_path = PACK / manifest["datasets"][key]["practice"]["replacement"]
                replacement = await service.execute(project_id, revision, {}, emit, threading.Event(), input_path=replacement_path)
                assert replacement.status == "succeeded", replacement.error
                entry["replacement"] = verify_metrics(key, pd.read_csv(replacement_path), revision, replacement, {})
                failed = await service.execute(project_id, revision, {}, emit, threading.Event(), input_path=PACK / manifest["datasets"][key]["practice"]["invalid"])
                assert failed.status == "failed", "Invalid-schema practice input must fail"
                assert store.get(project_id)["display_run_id"] == replacement.run_id, "Failed input replaced the previous good result"
                entry["invalid_schema_retains_results"] = True
                # Return to the exact tutorial default input before acceptance.
                final = await service.execute(project_id, revision, {}, emit, threading.Event())
                assert final.status == "succeeded", final.error
                store.accept(project_id, final.run_id, True)
                entry["acceptance_passed"] = True
                (PACK / "reference" / f"{key}.json").write_text(json.dumps(safe_json({"revision": revision.model_dump(), "run": final.model_dump(),
                    "input_sha256": sha(path), "checks": checks(key, frame), "configured_model": config.openai_model_name}), indent=2, ensure_ascii=False))
                entry.update(status="passed", finished_at=now(), independent_checks=checks(key, frame))
                print(f"[{key}] PASS: published prompts, independent results, filter, scenario, replacement, failure retention and acceptance", flush=True)
            except Exception as exc:
                entry.update(status="failed", finished_at=now(), error=str(exc))
                report_path.write_text(json.dumps(safe_json(report), indent=2))
                print(f"[{key}] FAIL: {type(exc).__name__}: {exc}", flush=True)
                continue
            report_path.write_text(json.dumps(safe_json(report), indent=2))
    finally:
        await llm.close()
    failed = [key for key, item in report["lessons"].items() if item["status"] != "passed"]
    if failed: raise RuntimeError(f"Tutorial validation is incomplete: {', '.join(failed)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-model", action="store_true", help="Required: permits model calls and API token use")
    parser.add_argument("--lesson", action="append", choices=[item["key"] for item in LESSONS], default=[])
    parser.add_argument("--state-dir", type=Path, default=ROOT / "data" / "tutorial_validation")
    args = parser.parse_args()
    if not args.live_model: parser.error("Pass --live-model to authorize the configured model calls")
    asyncio.run(validate(args.lesson, args.state_dir))
