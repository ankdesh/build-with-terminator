"""Exercise real local target processes and workers without model calls or a Windows cache."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def wait_for(check, message, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(.1)
    raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18090)
    parser.add_argument('--target-port-start', type=int, default=18200)
    args = parser.parse_args()
    from backend.services.project_store import ProjectStore
    from examples.electric_dashboard import revision
    with tempfile.TemporaryDirectory(prefix='wps-studio-smoke-') as temporary, ExitStack() as cleanup:
        root = Path(temporary)
        source = root / 'reference.csv'
        pd.DataFrame({'timestamp': pd.date_range('2025-01-01', periods=40, freq='h'), 'zone': ['A'] * 40,
            'kwh': [float(n + 10) for n in range(40)]}).to_csv(source, index=False)
        store = ProjectStore(root / 'projects')
        project_ids = []
        for _ in range(2):
            project = store.create('Studio smoke test')
            store.save_dataset(project['id'], source, 'reference.csv', {}, '')
            store.save_revision(project['id'], revision())
            project_ids.append(project['id'])
        environment = {**os.environ, 'WPS_PROJECTS_DIR': str(store.root), 'WPS_TARGET_PORT_START': str(args.target_port_start),
            'WPS_TARGET_PORT_END': str(args.target_port_start + 20), 'OPENAI_API_KEY': 'test-secret-must-not-reach-target'}
        log = cleanup.enter_context((root / 'builder.log').open('wb'))
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(args.port),
            '--log-level', 'warning', '--timeout-graceful-shutdown', '3'], cwd=ROOT, env=environment, stdout=log, stderr=log)
        def stop():
            if server.poll() is None:
                server.send_signal(signal.SIGINT)
                try:
                    server.wait(timeout=16)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait(timeout=5)
        cleanup.callback(stop)
        client = cleanup.enter_context(httpx.Client(base_url=f'http://127.0.0.1:{args.port}', timeout=120, trust_env=False))
        wait_for(lambda: client.get('/health').status_code == 200, 'Builder did not start')
        def post(path, body=None):
            response = client.post(path, json=body or {})
            response.raise_for_status()
            return response.json()
        def get(path):
            response = client.get(path); response.raise_for_status(); return response.json()
        targets = [post(f'/api/projects/{project}/target/start') for project in project_ids]
        assert targets[0]['port'] != targets[1]['port'], targets
        pids = Path(f'/proc/{server.pid}/task/{server.pid}/children').read_text().split() if sys.platform == 'linux' else []
        for pid in pids:
            assert b'OPENAI_API_KEY=' not in Path(f'/proc/{pid}/environ').read_bytes()
        project = project_ids[0]
        base = '/api/projects/' + project
        target = cleanup.enter_context(httpx.Client(base_url=targets[0]['url'], timeout=120, trust_env=False))
        assert target.get('/api/projects').status_code == 404
        assert target.post('/internal/snapshot', json={}).status_code == 403
        assert target.get('/api/runtime/state').json()['revision'] is None
        workspace = get(base + '/workspace')
        job = post(base + '/run', {'expected_version': workspace['version']})
        wait_for(lambda: get(base + '/jobs/' + job['id'])['status'] in {'succeeded', 'failed'}, 'Builder run did not finish')
        assert get(base + '/jobs/' + job['id'])['status'] == 'succeeded', get(base + '/jobs/' + job['id'])
        state = wait_for(lambda: (s if (s := target.get('/api/runtime/state').json())['display_run'] and not s['active_run'] else None), 'Target did not apply the validated revision')
        assert state['display_run']['result']['outputs']['total']['value'] == 1180
        workspace = get(base + '/workspace')
        workspace['document']['dashboard']['title'] = 'Live presentation check'
        changed = client.patch(base + '/workspace', json={'expected_version': workspace['version'], 'document': workspace['document']})
        changed.raise_for_status()
        state = wait_for(lambda: (s if (s := target.get('/api/runtime/state').json())['revision']['dashboard']['title'] == 'Live presentation check' else None), 'Presentation did not update')
        assert state['display_run']['validation_mode'] == 'presentation'
        assert len(get(base + '/jobs')) == 1
        workspace = get(base + '/workspace')
        preview = post(base + '/stages/step:forecast/delete', {'expected_version': workspace['version']})
        assert len(preview['affected']) == 3, preview
        removed = post(base + '/stages/step:forecast/delete', {'expected_version': workspace['version'], 'confirmed': True})
        assert removed['workspace']['calculation_pending']
        assert target.get('/api/runtime/state').json()['display_run']['result']['outputs']['total']['value'] == 1180
        response = client.patch(base + '/workspace', json={'expected_version': removed['workspace']['version'], 'action': 'undo'})
        response.raise_for_status()
        builder_hash = get(base)['project']['dataset_hash']
        replacement = pd.DataFrame({'timestamp': pd.date_range('2025-02-01', periods=40, freq='h'), 'zone': ['Z'] * 40, 'kwh': [2.] * 40}).to_csv(index=False).encode()
        response = target.post('/api/runtime/upload', files={'csv_file': ('replacement.csv', replacement)})
        response.raise_for_status(); state = response.json()['state']
        assert state['display_run']['result']['outputs']['total']['value'] == 80
        assert state['input_mode'] == 'replacement'
        assert get(base)['project']['dataset_hash'] == builder_hash
        response = target.post('/api/runtime/upload', files={'csv_file': ('bad.csv', b'wrong\n1\n')})
        response.raise_for_status()
        assert response.json()['run']['status'] == 'failed'
        assert response.json()['state']['display_run']['result']['outputs']['total']['value'] == 80
        response = target.post('/api/runtime/use-builder-data', json={}); response.raise_for_status()
        assert response.json()['state']['display_run']['result']['outputs']['total']['value'] == 1180
        old_port = targets[0]['port']
        post(base + '/target/stop')
        restarted = post(base + '/target/start')
        assert restarted['port'] == old_port, restarted
        # Hold an SSE connection during shutdown to verify that streams do not keep child processes alive.
        with target.stream('GET', '/api/runtime/events') as stream:
            assert stream.status_code == 200
            stop()
        assert server.poll() is not None
        for item in targets:
            def closed():
                with socket.socket() as connection:
                    return connection.connect_ex(('127.0.0.1', item['port'])) != 0
            wait_for(closed, 'Target survived builder shutdown', timeout=10)
        # A second launch proves that abrupt parent loss also closes a target with an active stream.
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(args.port),
            '--log-level', 'warning', '--timeout-graceful-shutdown', '3'], cwd=ROOT, env=environment, stdout=log, stderr=log)
        wait_for(lambda: client.get('/health').status_code == 200, 'Builder did not restart')
        restarted = post(base + '/target/start')
        crash_target = cleanup.enter_context(httpx.Client(base_url=restarted['url'], timeout=10, trust_env=False))
        crash_children = Path(f'/proc/{server.pid}/task/{server.pid}/children').read_text().split() if sys.platform == 'linux' else []
        with crash_target.stream('GET', '/api/runtime/events') as stream:
            assert stream.status_code == 200
            server.kill(); server.wait(timeout=5)
            def crash_closed():
                with socket.socket() as connection:
                    return connection.connect_ex(('127.0.0.1', restarted['port'])) != 0
            wait_for(crash_closed, 'Target survived abrupt parent loss', timeout=10)
            def children_stopped():
                for pid in crash_children:
                    status = Path(f'/proc/{pid}/stat')
                    if status.exists() and status.read_text().split(') ', 1)[1].split()[0] != 'Z':
                        return False
                return True
            wait_for(children_stopped, 'Orphan target process did not exit', timeout=10)
        print('Studio smoke passed: separate ports, manual Run, live presentation, deletion and Undo, isolated input, recovery, credentials, restart, shutdown, and parent-crash cleanup.')


if __name__ == '__main__':
    main()
