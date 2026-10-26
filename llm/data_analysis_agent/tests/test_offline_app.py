"""Offline application replacement and recovery without model imports."""

import ast
from pathlib import Path
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest

from offline_app import create_app
from tests.test_projects import fake_runtime, saved_project
from backend.services.export_service import ExportService


@pytest.mark.asyncio
async def test_offline_replacement_preserves_last_good_dashboard(saved_project, tmp_path):
    store, project_id, record = saved_project
    store.accept(project_id, record.run_id, True)
    archive = ExportService(store, fake_runtime(tmp_path)).export(project_id)
    package = tmp_path / "package"
    with zipfile.ZipFile(archive) as stream: stream.extractall(package)
    app = create_app(package, tmp_path / "state")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.get('/health')).json()['model_required'] is False
        assert "connect-src 'self'" in (await client.get('/')).headers['content-security-policy']
        assert (await client.get('/health', headers={'Host': 'untrusted.example'})).status_code == 400
        assert (await client.get('/api/projects')).status_code == 404
        assert (await client.post('/api/runtime/chat', json={})).status_code == 404
        first = await client.post('/api/runtime/run', json={})
        assert first.json()['run']['status'] == 'succeeded', first.text
        assert first.json()['run']['result']['outputs']['total']['value'] == 30
        replaced = await client.post('/api/runtime/upload', files={'csv_file': ('new.csv', b'zone,value\nNew,99\n')})
        assert replaced.json()['run']['result']['outputs']['total']['value'] == 99
        assert '99.0' in replaced.json()['run']['result']['outputs']['finding']['value']
        failed = await client.post('/api/runtime/upload', files={'csv_file': ('bad.csv', b'wrong,columns\nx,y\n')})
        assert failed.json()['run']['status'] == 'failed'
        state = (await client.get('/api/runtime/state')).json()
        assert state['dataset_name'] == 'new.csv'
        assert state['display_run']['result']['outputs']['total']['value'] == 99
        changed = await client.post('/api/runtime/run', json={'parameters': {'multiplier': 2}})
        assert changed.json()['run']['result']['outputs']['total']['value'] == 198
        assert 'New,99' in (await client.get('/api/runtime/tables/records')).text
    restarted = create_app(package, tmp_path / 'state')
    assert restarted.state.application.view()['display_run']['result']['outputs']['total']['value'] == 198


def test_runtime_import_graph_has_no_model_or_builder_dependency():
    root = Path(__file__).resolve().parents[1]
    paths = [root / 'offline_app.py', root / 'runtime_launcher.py', *list((root / 'pipeline_core').glob('*.py'))]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import): names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom): names = [node.module or '']
            else: continue
            assert not any(n.startswith(('openai', 'backend', 'config')) for n in names), (path, names)
