"""Command-line CSV input uses the builder's upload contract without model calls."""

from unittest.mock import Mock
import os

import pytest

import launcher
from backend.routes import project_routes
from backend.services.dataset_import import import_csv
from backend.services.project_store import ProjectStore
from config import config
from dataclasses import replace


@pytest.fixture(autouse=True)
def mock_frontend_for_unit_launches(monkeypatch):
    monkeypatch.setattr(launcher, 'ensure_frontend', Mock())


def test_startup_csv_creates_selected_project_without_running(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(project_routes, "store", store)
    source = tmp_path / "energy data.csv"
    source.write_text("zone,value\nA,10\nB,20\n")
    selected = launcher.import_startup_csv(source)
    project = store.list_projects()[0]
    view = store.view(project["id"])
    assert selected == f"/?project={project['id']}&view=data"
    assert project["title"] == "energy data"
    assert view["project"]["profile"]["row_count"] == 2
    assert view["workspace"]["document"]["input_enabled"]
    assert view["draft"] is None and view["display_run"] is None
    assert store.dataset_path(project["id"]).read_bytes() == source.read_bytes()
    source.write_text("changed")
    assert store.dataset_path(project["id"]).read_text().startswith("zone,value")


@pytest.mark.parametrize("content", ["", "zone,value\n", 'zone,value\n"broken,1'])
def test_invalid_startup_csv_does_not_create_a_project(tmp_path, content):
    store = ProjectStore(tmp_path / "projects")
    source = tmp_path / "invalid.csv"
    source.write_text(content)
    with pytest.raises(Exception):
        import_csv(store, source)
    assert store.list_projects() == []


def test_startup_csv_checks_size_limit(tmp_path, monkeypatch):
    from backend.services import dataset_import
    store = ProjectStore(tmp_path / "projects")
    source = tmp_path / "large.csv"
    source.write_text("zone,value\nA,10\n")
    monkeypatch.setattr(dataset_import, "config", replace(config, max_upload_size_bytes=5))
    with pytest.raises(ValueError, match="size limit"):
        import_csv(store, source)
    assert store.list_projects() == []


def test_launcher_csv_option_opens_project_url(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(project_routes, "store", store)
    source = tmp_path / "input.csv"
    source.write_text("zone,value\nA,10\n")
    monkeypatch.setattr("sys.argv", ["launcher.py", "--csv", str(source)])
    monkeypatch.setattr(launcher, "reserve_server_socket", Mock())
    monkeypatch.setattr(launcher, "config", replace(config, server_port=8080))
    monkeypatch.setattr(launcher, "wait_for_server", lambda url: True)
    monkeypatch.setattr(launcher.uvicorn, "Server", Mock())
    thread = Mock()
    thread.is_alive.return_value = False
    monkeypatch.setattr(launcher.threading, "Thread", Mock(return_value=thread))
    browser = Mock()
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    launcher.main()
    browser.assert_called_once_with(f"http://127.0.0.1:8080/?project={store.list_projects()[0]['id']}&view=data")


def test_launcher_missing_csv_exits_before_starting_server(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["launcher.py", "--csv", str(tmp_path / "missing.csv"), "--headless"])
    server = Mock()
    monkeypatch.setattr(launcher.uvicorn, "Server", server)
    with pytest.raises(SystemExit) as error:
        launcher.main()
    assert error.value.code == 2
    assert "Cannot load startup CSV" in capsys.readouterr().err
    server.assert_not_called()


@pytest.mark.skipif(os.name == "nt", reason="Linux builder launcher")
def test_real_headless_launcher_imports_csv_without_model_key(tmp_path):
    import json
    from pathlib import Path
    import signal
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    source = tmp_path / "startup.csv"
    source.write_text("zone,value\nA,10\nB,20\n")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = dict(os.environ, WPS_PROJECTS_DIR=str(tmp_path / "projects"))
    environment.pop("OPENAI_API_KEY", None)
    process = subprocess.Popen([sys.executable, "launcher.py", "--headless", "--port", str(port),
        "--csv", str(source)], cwd=Path(launcher.__file__).parent, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"Launcher exited: {process.communicate()}")
            try:
                with urllib.request.urlopen(base + "/api/projects", timeout=1) as response:
                    projects = json.load(response)
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("Launcher did not become ready")
        assert len(projects) == 1
        project_id = projects[0]["id"]
        with urllib.request.urlopen(base + f"/api/projects/{project_id}", timeout=2) as response:
            view = json.load(response)
        assert view["project"]["profile"]["row_count"] == 2
        assert view["draft"] is None and view["display_run"] is None
        # Wait for the launcher's own health check and URL log.
        time.sleep(0.3)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            stdout, stderr = process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            pytest.fail(f"Launcher did not shut down: {stderr}")
    assert process.returncode == 0, stderr
    assert f"{base}/?project={project_id}&view=data" in stdout + stderr


@pytest.mark.parametrize('override,expected', [(None, 6010), (6017, 6017)])
def test_launcher_uses_exact_config_or_explicit_cli_port(monkeypatch, override, expected):
    monkeypatch.setattr(launcher, 'config', replace(config, server_host='127.0.0.1', server_port=6010))
    arguments = ['launcher.py', '--headless']
    if override is not None:
        arguments += ['--port', str(override)]
    monkeypatch.setattr('sys.argv', arguments)
    listener = Mock()
    reserve = Mock(return_value=listener)
    monkeypatch.setattr(launcher, 'reserve_server_socket', reserve)
    monkeypatch.setattr(launcher, 'wait_for_server', Mock(return_value=True))
    uvicorn_config = Mock()
    monkeypatch.setattr(launcher.uvicorn, 'Config', uvicorn_config)
    monkeypatch.setattr(launcher.uvicorn, 'Server', Mock())
    thread = Mock()
    thread.is_alive.return_value = False
    create_thread = Mock(return_value=thread)
    monkeypatch.setattr(launcher.threading, 'Thread', create_thread)
    launcher.main()
    reserve.assert_called_once_with('127.0.0.1', expected)
    assert uvicorn_config.call_args.kwargs['port'] == expected
    assert create_thread.call_args.kwargs['kwargs']['sockets'] == [listener]
    launcher.wait_for_server.assert_called_once_with(f'http://127.0.0.1:{expected}')
    listener.close.assert_called_once()


def test_occupied_configured_port_fails_before_import_or_server_start(tmp_path, monkeypatch, capsys):
    import socket
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        monkeypatch.setattr(launcher, 'config', replace(config, server_host='127.0.0.1', server_port=port))
        monkeypatch.setattr('sys.argv', ['launcher.py', '--headless', '--csv', str(tmp_path/'input.csv')])
        importer = Mock()
        server = Mock()
        monkeypatch.setattr(launcher, 'import_startup_csv', importer)
        monkeypatch.setattr(launcher.uvicorn, 'Server', server)
        with pytest.raises(SystemExit) as error:
            launcher.main()
        assert error.value.code == 2
        message = capsys.readouterr().err
        assert f'Cannot bind 127.0.0.1:{port}' in message
        assert 'No other port was selected' in message
        importer.assert_not_called()
        server.assert_not_called()


@pytest.mark.parametrize('port', [0, -1, 65536])
def test_invalid_configured_port_is_rejected(tmp_path, port):
    import json
    from config import AppConfig
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'server_port': port}))
    with pytest.raises(ValueError, match='server_port'):
        AppConfig.load(path)
