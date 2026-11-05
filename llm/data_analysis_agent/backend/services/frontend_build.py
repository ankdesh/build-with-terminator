"""Keep both frontend bundles in sync with the checked-out source."""

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger(__name__)


def tree_hash(directory: Path, excluded: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    excluded = excluded or set()
    files: list[Path] = []
    for base, directories, names in os.walk(directory):
        directories[:] = sorted(name for name in directories if name not in excluded)
        files.extend(Path(base) / name for name in names if name not in excluded)
    for path in sorted(files):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def read_stamp(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def ensure_frontend(root: Path) -> None:
    """Install changed dependencies and build stale bundles; fail closed on error."""
    frontend = root / 'frontend'
    if not (frontend / 'package.json').is_file() or not (frontend / 'pnpm-lock.yaml').is_file():
        raise RuntimeError('Frontend source or pnpm-lock.yaml is missing. Launch from a complete checkout.')
    source = tree_hash(frontend, {'node_modules', '.git', '.pnpm-store', 'dist'})
    stamp_path = root / 'runtime_cache' / 'frontend-build.json'
    stamp = read_stamp(stamp_path)
    outputs = [root / 'backend/static', root / 'runtime_static']
    entries = [outputs[0] / 'index.html', outputs[1] / 'runtime.html']
    if (stamp.get('source') == source and all(path.is_file() for path in entries)
            and stamp.get('outputs') == [tree_hash(path) for path in outputs]):
        logger.info('Builder and dashboard UI files are current.')
        return
    pnpm = shutil.which('pnpm')
    if not pnpm or not shutil.which('node'):
        raise RuntimeError('UI files need rebuilding. Install Node.js and pnpm, then launch again.')
    # Invalidate first: a partial build must never be treated as current.
    stamp_path.unlink(missing_ok=True)
    dependency_stamp = frontend / 'node_modules' / '.wps-dependencies.json'
    dependency_hash = hashlib.sha256((frontend / 'package.json').read_bytes()
        + b'\0' + (frontend / 'pnpm-lock.yaml').read_bytes()).hexdigest()
    def run(arguments: list[str]) -> None:
        logger.info('Frontend: pnpm %s', ' '.join(arguments))
        try:
            subprocess.run([pnpm, *arguments], cwd=frontend, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"Frontend command failed: pnpm {' '.join(arguments)}. Fix the error above and launch again.") from exc
    if (read_stamp(dependency_stamp).get('dependencies') != dependency_hash
            or not (frontend / 'node_modules/.bin/vite').is_file()):
        run(['install', '--frozen-lockfile'])
        dependency_stamp.parent.mkdir(parents=True, exist_ok=True)
        dependency_stamp.write_text(json.dumps({'dependencies': dependency_hash}))
    run(['exec', 'vite', 'build'])
    run(['exec', 'vite', 'build', '--mode', 'runtime'])
    if not all(path.is_file() for path in entries):
        raise RuntimeError('Frontend build did not produce both UI entry files. Server startup stopped.')
    if tree_hash(frontend, {'node_modules', '.git', '.pnpm-store', 'dist'}) != source:
        raise RuntimeError('Frontend source changed during the build. Launch again to build a consistent UI.')
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(json.dumps({'source': source, 'outputs': [tree_hash(path) for path in outputs]}))
    logger.info('Builder and dashboard UI files rebuilt successfully.')
