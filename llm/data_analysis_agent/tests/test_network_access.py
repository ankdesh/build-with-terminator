"""LAN clients use their server address without bypassing origin or token checks."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from backend.app import app
from backend.routes import project_routes
from config import AppConfig
from pipeline_core.runtime import RuntimeApplication
from pipeline_core.runtime_http import create_runtime_app


@pytest.mark.asyncio
async def test_builder_allows_same_origin_lan_clients():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://analysis.lan:8080') as client:
        response = await client.get('/health', headers={'Origin': 'http://analysis.lan:8080'})
        assert response.status_code == 200
        assert "connect-src 'self'" in response.headers['content-security-policy']
        assert (await client.post('/api/projects', json={}, headers={'Origin': 'http://other.lan:8080'})).status_code == 403
        assert (await client.post('/api/internal/targets/unknown/execute', json={
            'revision_id': 'unknown', 'input': 'input.csv',
            'run_id': '00000000-0000-0000-0000-000000000000'})).status_code == 403


@pytest.mark.asyncio
async def test_target_links_follow_each_client_host_and_broker_stays_local(monkeypatch):
    manager = Mock()
    manager.status.return_value = {'status': 'running', 'url': 'http://127.0.0.1:8101', 'port': 8101}
    manager.state = AsyncMock(return_value=None)
    manager.start = AsyncMock()
    monkeypatch.setattr(project_routes, 'targets', manager)
    monkeypatch.setenv('WPS_BIND_HOST', '0.0.0.0')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://analysis.lan:8095') as client:
        response = await client.post('/api/projects/example/target/start')
        assert response.json()['url'] == 'http://analysis.lan:8101'
        manager.start.assert_awaited_once_with('example', 'http://127.0.0.1:8095')
        response = await client.get('/api/projects/example/target', headers={'Host': '192.168.1.10:8095'})
        assert response.json()['url'] == 'http://192.168.1.10:8101'


@pytest.mark.asyncio
async def test_runtime_host_policy_is_explicit_and_origin_guard_remains(tmp_path):
    runtime = RuntimeApplication(tmp_path/'runtime', live=True)
    live = create_runtime_app(runtime, tmp_path/'static', 'test-token', allowed_hosts=['analysis.lan', '127.0.0.1'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(live), base_url='http://analysis.lan:8101') as client:
        assert (await client.get('/health')).status_code == 200
        assert (await client.get('/health', headers={'Host': 'unknown.lan'})).status_code == 400
        assert (await client.post('/api/runtime/run', json={}, headers={'Origin': 'http://analysis.lan:8101'})).status_code == 422
        assert (await client.post('/api/runtime/run', json={}, headers={'Origin': 'http://analysis.lan:8080'})).status_code == 403
        assert (await client.post('/internal/snapshot', json={})).status_code == 403
    offline = create_runtime_app(runtime, tmp_path/'static')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(offline), base_url='http://analysis.lan') as client:
        assert (await client.get('/health')).status_code == 400


@pytest.mark.parametrize('hosts', [[], '*', [None], ['']])
def test_invalid_allowed_hosts_fail_at_startup(tmp_path, hosts):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'allowed_hosts': hosts}))
    with pytest.raises(ValueError, match='allowed_hosts'):
        AppConfig.load(path)


def test_host_allowlist_retains_internal_loopback(tmp_path):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'allowed_hosts': ['analysis.lan']}))
    assert AppConfig.load(path).allowed_hosts == ('127.0.0.1', 'localhost', 'analysis.lan')


@pytest.mark.skipif(os.name == 'nt', reason='Linux builder process lifecycle')
def test_real_lan_builder_and_target(tmp_path):
    # UDP connect selects a route; it sends no packets to this documentation address.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect(('192.0.2.1', 9))
        address = route.getsockname()[0]
    if address.startswith('127.'):
        pytest.skip('No non-loopback interface is available')
    with socket.socket() as reservation:
        reservation.bind(('0.0.0.0', 0))
        port = reservation.getsockname()[1]
    environment = dict(os.environ, WPS_PROJECTS_DIR=str(tmp_path/'projects'))
    environment.pop('OPENAI_API_KEY', None)
    with (tmp_path/'server.log').open('w+') as log:
        process = subprocess.Popen([sys.executable, 'launcher.py', '--headless', '--host', '0.0.0.0', '--port', str(port)],
            cwd=Path(__file__).resolve().parents[1], env=environment, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f'http://{address}:{port}', trust_env=False, timeout=15) as client:
                deadline = time.monotonic()+15
                while True:
                    try:
                        if client.get('/health').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() > deadline or process.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    time.sleep(.1)
                view = client.post('/api/projects/examples/energy').json()
                project = view['project']['id']
                response = client.post(f'/api/projects/{project}/target/start')
                assert response.status_code == 200, response.text
                status = response.json()
                assert status['url'].startswith(f'http://{address}:')
                target_port = status['port']
                target = client.get(status['url']+'/health')
                assert target.status_code == 200 and target.json()['mode'] == 'live'
                assert client.post(status['url']+'/api/runtime/run', json={}, headers={'Origin': status['url']}).status_code == 422
                assert client.post(status['url']+'/internal/snapshot', json={}).status_code == 403
                response = client.post(f'/api/projects/{project}/run', json={'expected_version': view['workspace']['version']})
                assert response.status_code == 202, response.text
                job_id = response.json()['id']
                deadline = time.monotonic()+30
                while True:
                    job = client.get(f'/api/projects/{project}/jobs/{job_id}').json()
                    if job['status'] in {'succeeded', 'failed', 'cancelled'}:
                        assert job['status'] == 'succeeded', job
                        break
                    assert time.monotonic() < deadline, job
                    time.sleep(.1)
                deadline = time.monotonic()+30
                while True:
                    state = client.get(status['url']+'/api/runtime/state').json()
                    if state['display_run'] and not state['active_run']:
                        break
                    assert time.monotonic() < deadline, state
                    time.sleep(.1)
                # Exercise target -> authenticated local broker -> worker after LAN promotion.
                response = client.post(status['url']+'/api/runtime/run', json={'parameters': {}},
                    headers={'Origin': status['url']})
                assert response.status_code == 200, response.text
                assert response.json()['run']['status'] == 'succeeded', response.text
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        with socket.socket() as check:
            assert check.connect_ex((address, target_port)) != 0
