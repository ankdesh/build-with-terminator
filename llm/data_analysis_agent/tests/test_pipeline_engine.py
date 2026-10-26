"""Known-result, replacement, cache, statistics, and isolation acceptance tests."""

import asyncio
import json
import os
from pathlib import Path
import threading

import numpy as np
import pandas as pd
import pytest

from pipeline_core.engine import PipelineEngine
from pipeline_core.models import ProjectRevision
from pipeline_core.process_runner import ProcessRunner
from pipeline_core.statistics import forecast


def test_cleanup_controls_and_new_input(simple_revision, input_csv, tmp_path):
    engine = PipelineEngine()
    result = engine.execute(simple_revision, input_csv, {}, tmp_path / "first")
    assert result["outputs"]["total"]["value"] == 30
    assert result["cleanup_impacts"][0]["removed_rows"] == 2
    assert result["cleanup_impacts"][0]["before_missing_cells"] == 1
    assert result["cleanup_impacts"][0]["after_missing_cells"] == 0
    filtered = engine.execute(simple_revision, input_csv, {"zone": "B", "multiplier": 3}, tmp_path / "filtered")
    assert filtered["outputs"]["total"]["value"] == 60
    empty = engine.execute(simple_revision, input_csv, {"zone": "new"}, tmp_path / "empty")
    assert empty["outputs"]["total"]["value"] == 0
    input_csv.write_text("zone,value\nNew,50\nA,5\n")
    refreshed = engine.execute(simple_revision, input_csv, {}, tmp_path / "new")
    assert refreshed["outputs"]["total"]["value"] == 55
    assert "55.0" in refreshed["outputs"]["finding"]["value"]
    assert "New" in refreshed["parameter_options"]["zone"]


@pytest.mark.parametrize("contents,expected", [
    ("wrong,value\nA,10\n", "Missing required columns"),
    ("zone,value\nA,nope\n", "Invalid values"),
    ("zone,value\n", "no data rows"),
    ("zone,zone,value\nA,A,10\n", "unique"),
])
def test_invalid_replacement_fails_explicitly(simple_revision, input_csv, tmp_path, contents, expected):
    input_csv.write_text(contents)
    with pytest.raises(ValueError, match=expected):
        PipelineEngine().execute(simple_revision, input_csv, {}, tmp_path / "out")


def test_datetime_contract(simple_revision, input_csv, tmp_path):
    payload = simple_revision.model_dump()
    payload["input_contract"]["columns"][0].update(dtype="datetime", date_format="%Y-%m-%d")
    revision = ProjectRevision.model_validate(payload)
    with pytest.raises(ValueError, match="Invalid values in column zone"):
        PipelineEngine().execute(revision, input_csv, {}, tmp_path / "out")


def test_full_table_export_and_checkpoint_reuse(simple_revision, input_csv, tmp_path):
    input_csv.write_text("zone,value\n" + "".join(f"A,{n}\n" for n in range(800)))
    first = tmp_path / "first"
    result = PipelineEngine().execute(simple_revision, input_csv, {}, first)
    assert len(result["outputs"]["records"]["rows"]) == 500
    assert len(pd.read_csv(first / "records.csv")) == 800
    changed = simple_revision.model_dump()
    changed["revision_id"] = "presentation-change"
    changed["dashboard"]["title"] = "New presentation"
    second = PipelineEngine().execute(ProjectRevision.model_validate(changed), input_csv, {}, tmp_path / "second", first)
    assert all(e["cached"] for e in second["steps"] if e["status"] == "succeeded")
    changed["steps"][1]["code"] = changed["steps"][1]["code"].replace("float(df['value'].sum())", "float(df['value'].sum()) + 1")
    third = PipelineEngine().execute(ProjectRevision.model_validate(changed), input_csv, {}, tmp_path / "third", first)
    success = [e for e in third["steps"] if e["status"] == "succeeded"]
    assert success[0]["cached"] and not success[1]["cached"]


@pytest.mark.parametrize("change", ["cycle", "bad_binding", "unsafe_import", "bad_parameter"])
def test_contract_rejects_invalid_projects(simple_revision, change):
    payload = simple_revision.model_dump()
    if change == "cycle": payload["steps"][0]["inputs"] = ["records"]
    if change == "bad_binding": payload["dashboard"]["widgets"][0]["output"] = "missing"
    if change == "unsafe_import": payload["steps"][0]["code"] = "import os\n" + payload["steps"][0]["code"]
    if change == "bad_parameter": payload["parameters"][1]["default"] = -1
    with pytest.raises(ValueError): ProjectRevision.model_validate(payload)


@pytest.mark.parametrize('expression', ['pd.Timestamp.now()', 'np.random.default_rng()'])
def test_hidden_clock_and_entropy_inputs_are_rejected(simple_revision, expression):
    payload = simple_revision.model_dump()
    payload['steps'][0]['code'] = f"def clean(inputs, parameters, context):\n    hidden = {expression}\n    return {{'cleaned': inputs['data']}}\n"
    with pytest.raises(ValueError): ProjectRevision.model_validate(payload)


def test_forecast_backtest_is_chronological_and_reports_baseline():
    series = pd.Series(np.arange(1, 61, dtype=float))
    result = forecast(series, horizon=5)
    assert result["training_observations"] == 55
    assert result["holdout_observations"] == 5
    assert result["baseline_mae"] == 3
    assert result["backtest_mae"] < 0.1
    assert np.allclose(result["forecast"], [61, 62, 63, 64, 65], atol=0.1)
    assert result["uncertainty"]
    with pytest.raises(ValueError): forecast(series.iloc[:3])
    dated = pd.Series(np.arange(20, dtype=float), index=pd.date_range('2025-01-01', periods=20, freq='D'))
    with pytest.raises(ValueError, match="equally spaced"):
        forecast(dated.drop(dated.index[5]), horizon=2)


def test_scipy_statistics_match_independent_calculation(simple_revision, input_csv, tmp_path):
    payload = simple_revision.model_dump()
    payload['dependencies'].append('scipy')
    payload['steps'][1]['code'] = "from scipy.stats import ttest_1samp\ndef calculate(inputs, parameters, context):\n    df = inputs['cleaned']\n    statistic = float(ttest_1samp(df['value'], popmean=0).statistic)\n    return {'total': statistic, 'records': df, 'finding': 'One-sample t statistic against zero'}\n"
    result = PipelineEngine().execute(ProjectRevision.model_validate(payload), input_csv, {}, tmp_path / 'statistics')
    # Cleaned observations are 10 and 20: mean 15, standard error 5.
    assert result['outputs']['total']['value'] == pytest.approx(3)


def test_one_frame_supports_distinct_chart_and_table_views(simple_revision, input_csv, tmp_path):
    payload = simple_revision.model_dump()
    payload['dashboard']['widgets'].append({'id': 'chart', 'kind': 'chart', 'title': 'Records chart', 'output': 'records',
        'chart_binding': {'kind': 'bar', 'x': 'zone', 'y': ['value']}})
    payload['dashboard']['widgets'].append({'id': 'total_text', 'kind': 'text', 'title': 'Total as text', 'output': 'total'})
    result = PipelineEngine().execute(ProjectRevision.model_validate(payload), input_csv, {}, tmp_path / 'views')
    assert result['widgets']['chart']['value']['option']['series'][0]['data'] == [10, 20]
    assert result['widgets']['table']['total_rows'] == 2
    assert result['widgets']['total_text']['value'] == '30.0'
    assert result['outputs']['records']['kind'] == 'table'


@pytest.mark.asyncio
async def test_worker_runs_without_model_credentials(simple_revision, input_csv, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-worker")
    response = await ProcessRunner().run(simple_revision, input_csv, {}, tmp_path / "job", threading.Event())
    assert response["success"], response
    assert response["result"]["outputs"]["total"]["value"] == 30
    payload = simple_revision.model_dump()
    payload["steps"][1]["code"] = payload["steps"][1]["code"].replace("f'Total {total:.1f} from {len(df)} rows'", "str(pd.io.common.os.environ.get('OPENAI_API_KEY'))")
    response = await ProcessRunner().run(ProjectRevision.model_validate(payload), input_csv, {}, tmp_path / "secret-check", threading.Event())
    assert response["success"], response
    assert response["result"]["outputs"]["finding"]["value"] == "None"


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="Linux authoring network policy")
async def test_worker_cannot_connect_to_host_network(simple_revision, input_csv, tmp_path):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    received = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.set()
            self.send_response(200); self.end_headers(); self.wfile.write(b"data")
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    payload = simple_revision.model_dump()
    payload["steps"][0]["code"] = f"def clean(inputs, parameters, context):\n    pd.io.common.urlopen('http://127.0.0.1:{server.server_port}').read()\n    return {{'cleaned': inputs['data']}}\n"
    try:
        response = await ProcessRunner().run(ProjectRevision.model_validate(payload), input_csv, {}, tmp_path / "network-check", threading.Event())
        assert not response["success"]
        assert "URLError" in response["error"] or "Network access is disabled" in response["error"]
        assert not received.is_set()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.mark.asyncio
async def test_deadline_and_cancellation_terminate_worker(simple_revision, input_csv, tmp_path):
    payload = simple_revision.model_dump()
    payload["steps"][1]["code"] = "def calculate(inputs, parameters, context):\n    while True:\n        pass\n"
    revision = ProjectRevision.model_validate(payload)
    response = await ProcessRunner(timeout_seconds=3).run(revision, input_csv, {}, tmp_path / "deadline", threading.Event())
    assert not response["success"]
    assert "deadline" in response["error"] or "exited unexpectedly" in response["error"]
    cancel = threading.Event()
    task = asyncio.create_task(ProcessRunner().run(revision, input_csv, {}, tmp_path / "cancel", cancel))
    await asyncio.sleep(.2)
    cancel.set()
    response = await task
    assert response.get("cancelled")


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="Linux authoring isolation policy")
async def test_worker_cannot_read_host_file(simple_revision, input_csv, tmp_path):
    secret = tmp_path / "not-mounted.csv"
    secret.write_text("secret\n123\n")
    payload = simple_revision.model_dump()
    payload["steps"][0]["code"] = f"def clean(inputs, parameters, context):\n    return {{'cleaned': pd.read_csv({str(secret)!r})}}\n"
    response = await ProcessRunner().run(ProjectRevision.model_validate(payload), input_csv, {}, tmp_path / "job", threading.Event())
    assert not response["success"]
    assert "FileNotFoundError" in response["error"]
