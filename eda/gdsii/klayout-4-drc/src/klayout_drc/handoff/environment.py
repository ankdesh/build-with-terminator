"""Explicit setup and probes. These commands cannot dispatch a model request."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
from .archive import sha, write_json


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, text=True, **kwargs)


def lock(settings):
    return json.loads((settings.root/'config/runtime-lock.json').read_text())


def version(executable, *args):
    return run([executable, *args], capture_output=True, timeout=20).stdout.strip()


def harness_check(settings):
    path = settings.path('harness')
    pin = lock(settings)['harness_commit']
    head = version(settings.tool('git'), '-C', path, 'rev-parse', 'HEAD')
    if head != pin: raise ValueError(f'Harness must be at {pin}; found {head}')
    if version(settings.tool('git'), '-C', path, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('Harness checkout has local changes; use a clean pinned checkout')
    return {'commit': head, 'path': str(path)}


def setup(settings, system=False, with_asic=False, python_only=False, dry_run=False):
    pins = lock(settings)
    harness = settings.path('harness')
    steps = []
    if system:
        steps += [(['sudo', 'apt-get', 'update'], settings.root),
                  (['sudo', 'apt-get', 'install', '-y', *pins['system_packages']], settings.root)]
    steps += [([settings.tool('uv'), 'sync', '--locked', '--extra', 'test', '--python', settings.tool('python')], settings.root)]
    if not python_only:
        if not harness.exists():
            steps += [([settings.tool('git'), 'clone', '--no-checkout', pins['harness_repository'], harness], settings.root),
                      ([settings.tool('git'), '-C', harness, 'checkout', '--detach', pins['harness_commit']], settings.root)]
        steps += [([settings.tool('pnpm'), 'install', '--frozen-lockfile'], harness),
                  ([settings.tool('pnpm'), 'run', 'build:native-system'], harness),
                  ([settings.tool('pnpm'), 'run', 'build:lib:host'], harness),
                  ([settings.tool('node'), settings.root/'harness/scripts/link-harness.mjs', harness], settings.root),
                  ([settings.tool('node'), settings.root/'harness/node_modules/typescript/bin/tsc', '-p', settings.root/'harness/tsconfig.json'], settings.root)]
    if with_asic: steps += [([settings.tool('docker'), 'pull', pins['orfs_image']], settings.root)]
    plan = [{'command': list(map(str, command)), 'cwd': str(cwd)} for command, cwd in steps]
    if dry_run: return {'status': 'dry-run', 'steps': plan, 'pin': pins}
    if sys.version_info[:2] != (3, 12): raise ValueError('Use Python 3.12 to bootstrap this project')
    if not python_only:
        actual_node = version(settings.tool('node'), '--version').removeprefix('v')
        if actual_node != pins['node']: raise ValueError(f'Install Node {pins["node"]}; found {actual_node}')
        actual_pnpm = version(settings.tool('pnpm'), '--version')
        if actual_pnpm != pins['pnpm']: raise ValueError(f'Install pnpm {pins["pnpm"]}; found {actual_pnpm}')
        if harness.exists(): harness_check(settings)
    child_env = dict(os.environ)
    if not python_only:
        node_path = Path(shutil.which(settings.tool('node'))).resolve()
        child_env['PATH'] = str(node_path.parent)+os.pathsep+child_env.get('PATH', '')
    for command, cwd in steps:
        if command[:2] == [settings.tool('pnpm'), 'install']:
            # The pinned source has a stale workspace specifier in its lock. Use
            # our retained install lock, then restore the exact source lock even
            # when installation fails. No Harness source files are changed.
            source_lock = harness/'pnpm-lock.yaml'
            retained_lock = settings.root/'config/harness-pnpm-lock.yaml'
            original = source_lock.read_bytes()
            if sha(source_lock) != pins['harness_source_lock_sha256']:
                raise ValueError('Unexpected Harness source lock')
            if sha(retained_lock) != pins['harness_install_lock_sha256']:
                raise ValueError('Retained Harness install lock checksum mismatch')
            try:
                source_lock.write_bytes(retained_lock.read_bytes())
                run(command, cwd=cwd, env=child_env)
            finally:
                source_lock.write_bytes(original)
        else:
            run(command, cwd=cwd, env=child_env)
        if command[0] == settings.tool('git') and 'checkout' in command: harness_check(settings)
    if not python_only: harness_check(settings)
    receipt = settings.path('work')/'setup.json'
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt, {'pins': pins, 'steps': plan})
    python = settings.root/'.venv/bin/python'
    command = [python, '-m', 'klayout_drc.handoff.cli', 'doctor', '--config', settings.config_file]
    for key in settings.values['paths']:
        command += ['--'+key+'-root', str(settings.path(key))]
    for key, value in settings.values['resources'].items():
        command += ['--'+key.replace('_','-'), str(value)]
    if python_only: command.append('--reports-only')
    if with_asic: command.append('--with-asic')
    run(command, cwd=settings.root, env={**child_env, 'PYTHONPATH': str(settings.root/'src')})
    return {'status': 'ready', 'steps': plan}


def doctor(settings, reports_only=False, with_asic=False):
    pins = lock(settings)
    checks = []
    def probe(name, operation, expected=None):
        try:
            value = operation()
            ok = value == expected if expected is not None else bool(value)
            checks.append({'name': name, 'ok': ok, 'actual': value, 'expected': expected})
        except Exception as exc:
            checks.append({'name': name, 'ok': False, 'error': str(exc)})
    probe('platform', lambda: platform.system()+' '+platform.machine(), 'Linux x86_64')
    probe('python_series', lambda: f'{sys.version_info.major}.{sys.version_info.minor}', pins['python_series'])
    def packages():
        from importlib.metadata import version as package_version
        actual = {p: package_version(p) for p in ('klayout', 'Pillow', 'reportlab', 'pypdf', 'pyyaml')}
        locked = {p['name'].lower():p.get('version') for p in tomllib.loads((settings.root/'uv.lock').read_text())['package']}
        changed = [p for p,v in actual.items() if locked.get(p.lower()) != v]
        if changed: raise ValueError('Installed dependencies differ from uv.lock: '+', '.join(changed))
        return actual
    probe('python_packages', packages)
    probe('python_klayout', lambda: __import__('klayout.db', fromlist=['db']).__version__, pins['klayout_python'])
    probe('fonts', lambda: all((settings.path('fonts')/name).is_file() for name in
                              ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSansMono.ttf')))
    probe('pdftoppm', lambda: bool(shutil.which('pdftoppm')))
    def export():
        import klayout.db as db
        import klayout.lay as lay
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            view = lay.LayoutView(); index = view.create_layout(1)
            layout = view.cellview(index).layout(); top = layout.create_cell('PROBE')
            top.shapes(layout.layer(19, 0)).insert(db.Box(0, 0, 100, 100))
            view.select_cell(top.cell_index(), index); view.add_missing_layers(); view.zoom_fit()
            path = Path(temp)/'probe.png'; view.save_image(str(path), 320, 240)
            with Image.open(path) as image: return image.size == (320, 240) and image.getbbox() is not None
    probe('headless_image_export', export)
    if not reports_only:
        probe('klayout_cli', lambda: version(settings.tool('klayout'), '-v').removeprefix('KLayout '), pins['klayout_cli'])
        probe('node', lambda: version(settings.tool('node'), '--version').removeprefix('v'), pins['node'])
        probe('pnpm', lambda: version(settings.tool('pnpm'), '--version'), pins['pnpm'])
        probe('harness', lambda: harness_check(settings))
        probe('harness_integration', lambda: (settings.root/'harness/lib/drc-operations.js').is_file())
        def sandbox():
            from .evaluation import apply_environment
            apply_environment(settings)
            from ..repair_executor import sandbox_availability
            sandbox_availability.cache_clear()
            problem = sandbox_availability()
            if problem: raise ValueError(problem)
            return 'Candidate worker policy and KLayout import passed in Bubblewrap'
        probe('candidate_sandbox', sandbox)
    if with_asic:
        probe('orfs_image', lambda: version(settings.tool('docker'), 'image', 'inspect', pins['orfs_image'], '--format', '{{.Id}}'))
    result = {'status': 'ready' if all(c['ok'] for c in checks) else 'missing-prerequisites',
              'checks': checks, 'runtime': {'python': sys.version, 'platform': platform.platform()},
              'configuration': settings.public()}
    return result
