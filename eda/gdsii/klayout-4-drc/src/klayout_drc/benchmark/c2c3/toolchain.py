"""Pinned, serial ORFS builds with retained artifacts and resource guards."""
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import time
from .contracts import IMAGE, ORFS_COMMIT, sha256, write_json


def available_memory():
    values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(values['MemAvailable'].split()[0])*1024


def prepare(root):
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=True)
    repo = root/'orfs'
    if not (repo/'.git').exists():
        subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                        'https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'sparse-checkout', 'set', 'flow/designs/asap7/gcd',
                    'flow/designs/asap7/uart', 'flow/designs/src/gcd', 'flow/designs/src/uart',
                    'flow/scripts', 'flow/util', 'flow/platforms/asap7', 'flow/platforms/common'], check=True)
    subprocess.run(['git', '-C', str(repo), 'checkout', ORFS_COMMIT], check=True)
    pinned = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if pinned != ORFS_COMMIT:
        raise ValueError('ORFS revision mismatch')
    submodules = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', 'HEAD', 'tools/'], text=True)
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE], text=True))[0]
    probe = subprocess.check_output(['docker', 'run', '--rm', '--network=none', '--entrypoint', 'bash', IMAGE,
        '-lc', 'source /OpenROAD-flow-scripts/env.sh; openroad -version; yosys -V; klayout -v; sha256sum /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad /OpenROAD-flow-scripts/tools/install/yosys/bin/yosys'], text=True)
    collateral = repo/'flow/platforms/asap7'
    hashes = {str(p.relative_to(collateral)): sha256(p) for p in sorted(collateral.rglob('*')) if p.is_file()}
    result = {'orfs_commit': pinned, 'image': IMAGE, 'image_id': image['Id'], 'submodules': submodules,
              'tool_versions': probe, 'collateral_sha256': hashes}
    write_json(root/'toolchain.json', result)
    return result


def build_source(root, design, group, factor=1., density=None, attempt=1):
    """Run one complete source build. Resume only a verified completed build."""
    root = Path(root).resolve()
    if design not in ('gcd', 'uart') or group not in (0, 1) or factor not in (1., .9, .8):
        raise ValueError('Unsupported source configuration')
    lock = root/'.build.lock'
    with lock.open('x'): pass
    try:
        density = density if density is not None else ((.35, .45) if design == 'gcd' else (.55, .65))[group]
        identity = f'{design}_g{group}' + (f'_stress_{factor:.2f}' if density == .75 else '')
        work = root/'builds'/(identity + (f'_attempt{attempt}' if attempt > 1 else '')); work.mkdir(parents=True, exist_ok=True)
        receipt = work/'build.json'
        if receipt.exists():
            previous = json.loads(receipt.read_text())
            old_config = (work/'config.mk').read_text() if (work/'config.mk').exists() else ''
            width = re.search(r'VERILOG_TOP_PARAMS\s*=\s*DATA_WIDTH\s+(\d+)', old_config)
            utilization = re.search(r'CORE_UTILIZATION\s*=\s*(\d+)', old_config)
            if (previous.get('image') != IMAGE or previous.get('density') != density or
                    (design == 'uart' and (int(width.group(1)) if width else 8) != (12 if group else 8)) or
                    (design == 'gcd' and (int(utilization.group(1)) if utilization else 65) != (50 if group else 65))):
                raise ValueError('Source configuration changed; retain the old build and use a new --attempt')
            if previous['status'] == 'complete' and all(sha256(work/p) == digest for p, digest in previous['artifacts'].items()):
                return previous
            raise ValueError(f'Build already attempted: {identity}; inspect its retained log')
        memory = min(8*1024**3, available_memory()-1024**3)
        if memory < 1024**3:
            result = {'status': 'blocked', 'identity': identity, 'reason': 'Less than 2 GiB available RAM', 'artifacts': {}}
            write_json(receipt, result); return result
        repo = root/'orfs'
        config = work/'config.mk'
        upstream = f'/repo/flow/designs/asap7/{design}/config.mk'
        density = density if density is not None else ((.35, .45) if design == 'gcd' else (.55, .65))[group]
        lines = [f'include {upstream}', f'export PLACE_DENSITY = {density}',
                 f'export FLOW_VARIANT = c2c3_{identity}', 'export NUM_CORES = 2',
                 'export CORNER = TC', 'export ASAP7_USE_VT = RVT', 'export SYNTH_USE_SYN = 0']
        if design == 'gcd' and group == 1:
            lines += ['export CORE_UTILIZATION = 50']
        if design == 'uart' and group == 1:
            lines += ['export VERILOG_TOP_PARAMS = DATA_WIDTH 12']
        if design == 'uart':
            lower, upper = 1.08, 16.
            scaled = lower+(upper-lower)*factor
            lines += [f'export DIE_AREA = 0 0 {scaled+1.0:.6f} {scaled+1.0:.6f}',
                      f'export CORE_AREA = {lower} {lower} {scaled:.6f} {scaled:.6f}']
        config.write_text('\n'.join(lines)+'\n')
        work_mount = '/work'
        command = ['docker', 'run', '--rm', '--network=none', '--cpus=2', f'--memory={memory}',
                   f'--memory-swap={memory}', '--user', f'{os.getuid()}:{os.getgid()}',
                   '--mount', f'type=bind,src={repo},dst=/repo', '--mount', f'type=bind,src={work},dst={work_mount}',
                   '--entrypoint', 'bash', IMAGE, '-lc',
                   'source /OpenROAD-flow-scripts/env.sh; cd /repo/flow; '
                   'make FLOW_HOME=/repo/flow DESIGN_CONFIG=/work/config.mk WORK_HOME=/work NUM_CORES=2 '
                   'OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad '
                   'YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys all']
        result = {'status': 'running', 'identity': identity, 'design': design, 'group': group,
                  'factor': factor, 'density': density, 'image': IMAGE, 'orfs_commit': ORFS_COMMIT,
                  'source_parameters': {'data_width': (12 if group else 8) if design == 'uart' else None,
                                        'core_utilization': (50 if group else 65) if design == 'gcd' else None},
                  'config_sha256': sha256(config), 'memory_limit_bytes': memory, 'threads': 2, 'artifacts': {}}
        write_json(receipt, result)
        started = time.monotonic()
        try:
            with (work/'build.log').open('w') as log:
                run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
            result['exit_code'] = run.returncode
            # GDS is mandatory. A successful global-route stage is insufficient.
            gds = sorted(work.glob('results/**/6_final.gds'))
            required = {suffix: sorted(work.glob(f'results/**/6_final.{suffix}')) for suffix in ('gds', 'def', 'odb', 'v', 'sdc')}
            result['status'] = 'complete' if run.returncode == 0 and all(required.values()) else 'failed'
            result['final'] = {suffix: str(paths[0].relative_to(work)) for suffix, paths in required.items() if paths}
        except subprocess.TimeoutExpired:
            result.update(status='timeout', reason='Flow exceeded 60 minutes')
        except OSError as exc:
            result.update(status='blocked', reason=str(exc))
        result['wall_seconds'] = time.monotonic()-started
        result['artifacts'] = {str(p.relative_to(work)): sha256(p) for p in sorted(work.rglob('*'))
                               if p.is_file() and p != receipt}
        write_json(receipt, result)
        return result
    finally:
        lock.unlink()
