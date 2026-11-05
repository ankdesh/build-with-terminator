"""Startup builds both UIs and never serves stale or partial bundles."""

from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from backend.services import frontend_build as build
import launcher


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    directory = tmp_path/'frontend'
    directory.mkdir()
    (directory/'package.json').write_text('{}')
    (directory/'pnpm-lock.yaml').write_text('lockfileVersion: 9')
    (directory/'src').mkdir()
    (directory/'src/App.tsx').write_text('first UI')
    monkeypatch.setattr(build.shutil, 'which', lambda name: '/tools/'+name)
    def run(command, **kwargs):
        assert kwargs['cwd'] == directory and kwargs['check']
        if command[1] == 'install':
            binary = directory/'node_modules/.bin/vite'
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text('vite')
        elif '--mode' in command:
            output = tmp_path/'runtime_static/runtime.html'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('runtime')
        else:
            output = tmp_path/'backend/static/index.html'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('builder')
    runner = Mock(side_effect=run)
    monkeypatch.setattr(build.subprocess, 'run', runner)
    return tmp_path, directory, runner


def test_first_launch_installs_and_builds_both_then_skips_current_files(frontend):
    root, directory, runner = frontend
    build.ensure_frontend(root)
    assert [call.args[0][1:] for call in runner.call_args_list] == [
        ['install', '--frozen-lockfile'], ['exec', 'vite', 'build'], ['exec', 'vite', 'build', '--mode', 'runtime']]
    runner.reset_mock()
    # Build dependencies must not become source inputs.
    (directory/'node_modules/noise').write_text('dependency file')
    build.ensure_frontend(root)
    runner.assert_not_called()


@pytest.mark.parametrize('change', ['source', 'missing', 'tampered', 'dependency'])
def test_changes_rebuild_and_only_dependency_changes_reinstall(frontend, change):
    root, directory, runner = frontend
    build.ensure_frontend(root)
    runner.reset_mock()
    if change == 'source':
        (directory/'src/App.tsx').write_text('second UI')
    elif change == 'missing':
        (root/'runtime_static/runtime.html').unlink()
    elif change == 'tampered':
        (root/'backend/static/index.html').write_text('old version')
    else:
        (directory/'pnpm-lock.yaml').write_text('changed lock')
    build.ensure_frontend(root)
    assert runner.call_count == (3 if change == 'dependency' else 2)


def test_failed_build_invalidates_stamp_and_does_not_claim_success(frontend):
    root, directory, runner = frontend
    build.ensure_frontend(root)
    (directory/'src/App.tsx').write_text('broken UI')
    runner.side_effect = subprocess.CalledProcessError(1, 'vite')
    with pytest.raises(RuntimeError, match='Frontend command failed'):
        build.ensure_frontend(root)
    assert not (root/'runtime_cache/frontend-build.json').exists()


def test_missing_build_tools_stop_stale_startup(frontend, monkeypatch):
    root, directory, runner = frontend
    monkeypatch.setattr(build.shutil, 'which', lambda _: None)
    with pytest.raises(RuntimeError, match='Install Node.js and pnpm'):
        build.ensure_frontend(root)
    runner.assert_not_called()


def test_launcher_stops_before_import_or_server_when_build_fails(monkeypatch, capsys):
    listener = Mock()
    monkeypatch.setattr(launcher, 'reserve_server_socket', Mock(return_value=listener))
    monkeypatch.setattr(launcher, 'ensure_frontend', Mock(side_effect=RuntimeError('Build failed')))
    importer, server = Mock(), Mock()
    monkeypatch.setattr(launcher, 'import_startup_csv', importer)
    monkeypatch.setattr(launcher.uvicorn, 'Server', server)
    monkeypatch.setattr('sys.argv', ['launcher.py', '--headless', '--csv', 'input.csv'])
    with pytest.raises(SystemExit) as error:
        launcher.main()
    assert error.value.code == 1
    assert 'Build failed' in capsys.readouterr().err
    listener.close.assert_called_once()
    importer.assert_not_called()
    server.assert_not_called()
