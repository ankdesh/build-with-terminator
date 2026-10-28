"""Copy, hash, verify, and transfer immutable evidence with original path names."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile

SCHEMA = 1
SKIP_NAMES = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache',
              '.env', '.tools', '.cache'}
EXCLUDED = ('output/c2c3/toolchain/builds', 'output/c2c3/toolchain/orfs', 'output/picorv32_asap7')
INCLUDE = ('test_data', 'reports', 'docs', 'scripts', 'src', 'tests', 'knowledge',
           'harness', 'flows/picorv32_asap7', 'output/c2c3', 'output/pdf', 'output/slides',
           'experiments', 'config', 'README.md', 'pyproject.toml', 'uv.lock', '.python-version',
           '.gitignore', '.codex-finalizer/klayout_slides_validation.json')
RENDERED = {'.pdf', '.ppt', '.pptx', '.png', '.jpg', '.jpeg', '.webp', '.svg'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def safe_relative(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or str(p) != value or '\\' in value:
        raise ValueError(f'Unsafe archive path: {value}')
    return Path(value)


def scoped_sources(root, data_root=None, work_root=None):
    root = Path(root).resolve()
    data_root = Path(data_root or root/'test_data').resolve()
    work_root = Path(work_root or root/'work').resolve()
    specs = [(root/name, name) for name in INCLUDE]
    aliases = []
    data_prefix = 'test_data'
    for fallback, source in [('external/data', data_root), ('external/runs', work_root/'runs'),
                             ('external/reports', work_root/'reports')]:
        prefix = source.relative_to(root).as_posix() if source.is_relative_to(root) else fallback
        if source == data_root: data_prefix = prefix
        specs.append((source, prefix))
        if source.exists(): aliases.append({'original': str(source), 'prefix': prefix})
    files = {}
    for start, prefix in specs:
        if not start.exists(): continue
        candidates = [start] if start.is_file() else []
        if start.is_dir():
            for directory, dirs, names in os.walk(start, followlinks=False):
                base = Path(directory)
                dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES and not (base/d).is_symlink()
                                  and not any((base/d).is_relative_to(root/e) for e in EXCLUDED))
                candidates.extend(base/n for n in sorted(names))
        for path in candidates:
            rel = prefix if path == start else (Path(prefix)/path.relative_to(start)).as_posix()
            if path.name in SKIP_NAMES or path.name == 'local.toml' or path.suffix in ('.pyc', '.pyo'): continue
            if any(path.is_relative_to(root/e) for e in EXCLUDED): continue
            if path.is_symlink(): raise ValueError(f'Unexpected evidence symlink (not copied): {path}')
            if path.is_file(): files[rel] = path
    return files, aliases, data_prefix, specs


def inventory(root, data_root=None, work_root=None):
    return sorted(scoped_sources(root, data_root, work_root)[0])


def dataset_catalog(root, data_root=None):
    root = Path(root)
    data_root = Path(data_root or root/'test_data')
    def location(path):
        return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    records = [{'id': 'ab', 'path': location(data_root/'layouts'), 'status': 'fixtures',
                'note': 'A/B legacy and ASAP7 fixtures; retain profiles and creators.'}]
    manifests = sorted(data_root.rglob('manifest.json'))
    manifests += sorted((root/'output/c2c3').glob('*/manifest.json'))
    for path in manifests:
        data = json.loads(path.read_text())
        count = len(data.get('cases', []))
        rel = location(path.parent)
        accepted = path.parent == data_root/'benchmark_c2c3' and data.get('complete') and count == 50
        status = ('accepted' if accepted else 'historical' if path.parent == data_root/'benchmark_v1'
                  else 'experimental-complete' if data.get('complete') else 'experimental-incomplete')
        records.append({'id': rel, 'path': rel, 'manifest_sha256': sha(path), 'entries': count,
                        'status': status, 'complete': data.get('complete'),
                        'note': 'Preserved as generated; no rescoring or relabeling of case outcomes.'})
    return records


def verify(snapshot, expected_manifest=None):
    snapshot = Path(snapshot)
    digest = sha(snapshot/'manifest.json')
    recorded = (snapshot/'manifest.sha256').read_text().split()[0]
    if digest != recorded or (expected_manifest and digest != expected_manifest):
        raise ValueError('Archive manifest checksum mismatch')
    manifest = json.loads((snapshot/'manifest.json').read_text())
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported archive schema')
    seen = set()
    for item in manifest['files']:
        rel = safe_relative(item['path'])
        if item['path'] in seen:
            raise ValueError(f'Duplicate file: {rel}')
        seen.add(item['path'])
        path = snapshot/'root'/rel
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError(f'Archive symlink: {rel}')
        if not path.is_file() or path.stat().st_size != item['size'] or sha(path) != item['sha256']:
            raise ValueError(f'Archive file missing or changed: {rel}')
    actual = {p.relative_to(snapshot/'root').as_posix() for p in (snapshot/'root').rglob('*') if p.is_file()}
    if actual != seen:
        raise ValueError(f'Unlisted archive files: {sorted(actual-seen)[:5]}')
    return {'status': 'verified', 'snapshot': manifest['snapshot'], 'files': len(seen),
            'bytes': sum(i['size'] for i in manifest['files']), 'manifest_sha256': digest,
            'datasets': manifest['datasets']}


def new_output(path):
    path = Path(path).resolve()
    if path.exists(): raise FileExistsError(f'Output already exists: {path}')
    for parent in path.parents:
        if (parent/'manifest.sha256').is_file() and (parent/'root').is_dir():
            raise ValueError(f'Output would change an immutable snapshot: {path}')
    return path


def create(root, archive_root, snapshot, move_reports=False, data_root=None, work_root=None):
    root, archive_root = Path(root).resolve(), Path(archive_root).resolve()
    safe_relative(snapshot)
    if len(Path(snapshot).parts) != 1 or snapshot.startswith('.'):
        raise ValueError('Snapshot ID must be one visible directory name')
    sources, aliases, data_prefix, specs = scoped_sources(root, data_root, work_root)
    if any(archive_root.is_relative_to(source) for source, _ in specs if source.is_dir()):
        raise ValueError('Archive root cannot be inside a captured evidence directory')
    dest = archive_root/snapshot
    archive_root.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f'Snapshot already exists: {dest}')
    stage = Path(tempfile.mkdtemp(prefix=f'.{snapshot}-', dir=archive_root))
    try:
        files = []
        paths = sorted(sources)
        for rel in paths:
            source, target = sources[rel], stage/'root'/rel
            before = sha(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha(target) != before or sha(source) != before:
                raise ValueError(f'Source changed while copying: {rel}')
            files.append({'path': rel, 'original_path': str(source), 'size': source.stat().st_size,
                          'sha256': before, 'mode': source.stat().st_mode & 0o777})
        datasets = dataset_catalog(root, Path(data_root).resolve() if data_root else None)
        for record in datasets:
            if Path(record['path']).is_absolute():
                for alias in aliases:
                    if Path(record['path']).is_relative_to(alias['original']):
                        record['original_path'] = record['path']
                        record['path'] = (Path(alias['prefix'])/Path(record['path']).relative_to(alias['original'])).as_posix()
                        break
        manifest = {'schema': SCHEMA, 'snapshot': snapshot, 'created_utc': datetime.now(timezone.utc).isoformat(),
                    'original_root': str(root), 'scope': 'evaluation-evidence',
                    'exclusions': [*EXCLUDED, *sorted(SKIP_NAMES), 'config/local.toml'],
                    'datasets': datasets, 'files': files,
                    'path_aliases': aliases, 'data_prefix': data_prefix}
        write_json(stage/'manifest.json', manifest)
        (stage/'manifest.sha256').write_text(f'{sha(stage/"manifest.json")}  manifest.json\n')
        result = verify(stage)
        # mkdir is exclusive; a competing creator cannot replace an existing snapshot.
        dest.mkdir()
        try:
            for child in stage.iterdir():
                child.rename(dest/child.name)
        except BaseException:
            shutil.rmtree(dest)
            raise
        index_path = archive_root/'index.json'
        index = json.loads(index_path.read_text()) if index_path.exists() else {'schema': SCHEMA, 'snapshots': []}
        index['snapshots'].append({k: result[k] for k in ('snapshot', 'files', 'bytes', 'manifest_sha256')})
        temp_index = archive_root/'.index.tmp'
        write_json(temp_index, index); temp_index.replace(index_path)
        if move_reports:
            move_rendered(dest, root)
        return result
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def move_rendered(snapshot, original_root):
    """Remove only originals that already have a verified, byte-identical copy."""
    verify(snapshot)
    manifest = json.loads((Path(snapshot)/'manifest.json').read_text())
    originals = []
    for item in manifest['files']:
        rel = item['path']
        if (rel.startswith(('docs/reports/', 'output/pdf/', 'output/slides/'))
                and Path(rel).suffix.lower() in RENDERED):
            path = Path(original_root)/safe_relative(rel)
            if path.exists():
                if path.is_symlink() or sha(path) != item['sha256']:
                    raise ValueError(f'Report changed before move; kept original: {path}')
                originals.append(path)
    # Check the complete set before removing any original.
    for path in originals: path.unlink()
    return {'status': 'moved', 'files': len(originals), 'snapshot': str(snapshot)}


def pack(snapshot, output):
    snapshot, output = Path(snapshot), new_output(output)
    result = verify(snapshot)
    if output.exists() or output.with_name(output.name+'.sha256').exists():
        raise FileExistsError(f'Bundle already exists: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name+'.partial')
    with temp.open('xb') as stream:
        try:
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                for name in ('manifest.json', 'manifest.sha256', 'root'):
                    tar.add(snapshot/name, arcname=name, recursive=True)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    # Use a link so publication fails if another pack command won the race.
    os.link(temp, output); temp.unlink()
    output.with_name(output.name+'.sha256').write_text(f'{sha(output)}  {output.name}\n')
    index_path = snapshot.parent/'index.json'
    if index_path.exists():
        index = json.loads(index_path.read_text())
        for entry in index['snapshots']:
            if entry['manifest_sha256'] == result['manifest_sha256']:
                entry['bundle'] = {'name': output.name, 'sha256': sha(output), 'bytes': output.stat().st_size}
        temporary = index_path.with_name('.index.tmp')
        write_json(temporary, index); temporary.replace(index_path)
    return {**result, 'bundle': str(output), 'bundle_sha256': sha(output)}


def restore(bundle, destination, expected_sha=None):
    bundle, destination = Path(bundle), new_output(destination)
    checksum = bundle.with_name(bundle.name+'.sha256')
    if not expected_sha:
        if not checksum.is_file():
            raise ValueError('Supply --sha256 or the bundle .sha256 sidecar')
        expected_sha = checksum.read_text().split()[0]
    if sha(bundle) != expected_sha:
        raise ValueError('Bundle checksum mismatch')
    if destination.exists():
        raise FileExistsError(f'Restore destination already exists: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.restore-', dir=destination.parent))
    try:
        with tarfile.open(bundle, 'r:gz') as tar:
            seen = set()
            for member in tar:
                rel = safe_relative(member.name)
                if member.name in seen or not (member.isfile() or member.isdir()):
                    raise ValueError(f'Unsafe or duplicate bundle member: {member.name}')
                seen.add(member.name)
                if rel.parts[0] not in ('root', 'manifest.json', 'manifest.sha256'):
                    raise ValueError(f'Unexpected bundle member: {member.name}')
                target = stage/rel
                if member.isdir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as handle:
                        shutil.copyfileobj(tar.extractfile(member), handle)
                    target.chmod(member.mode & 0o777)
        result = verify(stage)
        destination.mkdir()
        for child in stage.iterdir(): child.rename(destination/child.name)
        return {**result, 'destination': str(destination)}
    finally:
        shutil.rmtree(stage, ignore_errors=True)


class Resolver:
    """Map old absolute paths without altering frozen JSON or its hashes."""
    def __init__(self, snapshot):
        self.snapshot = Path(snapshot).resolve()
        self.manifest = json.loads((self.snapshot/'manifest.json').read_text())
        self.original = Path(self.manifest['original_root'])
        self.root = self.snapshot/'root'
        self.paths = {i['path'] for i in self.manifest['files']}
        self.aliases = sorted(self.manifest.get('path_aliases', []), key=lambda a: len(a['original']), reverse=True)
        safe_relative(self.manifest.get('data_prefix', 'test_data'))
        for alias in self.aliases:
            safe_relative(alias['prefix'])
            if not Path(alias['original']).is_absolute():
                raise ValueError('Archive aliases require an absolute original root')

    def resolve(self, value, expected_sha256=None):
        path = Path(value)
        if path.is_absolute():
            for alias in self.aliases:
                if path.is_relative_to(alias['original']):
                    path = Path(alias['prefix'])/path.relative_to(alias['original'])
                    break
        if path.is_absolute():
            try: path = path.relative_to(self.original)
            except ValueError:
                try: path = path.relative_to(self.root)
                except ValueError: raise ValueError(f'Path is outside archived project: {value}')
        rel = safe_relative(path.as_posix())
        if str(rel) not in self.paths:
            raise FileNotFoundError(f'Path is not in snapshot: {value}')
        target = self.root/rel
        if expected_sha256 and sha(target) != expected_sha256:
            index = self.root/'reports/handoff_original_report_sources/index.json'
            sources = json.loads(index.read_text()).get('files', {}) if index.exists() else {}
            retained = sources.get(str(rel), {})
            if retained.get('sha256') != expected_sha256:
                raise ValueError(f'Archived evidence hash mismatch: {value}')
            target = self.root/safe_relative(retained['retained_copy'])
            if sha(target) != expected_sha256:
                raise ValueError(f'Retained source hash mismatch: {value}')
        return target


def restore_datasets(snapshot, destination):
    verify(snapshot)
    resolver = Resolver(snapshot)
    destination = new_output(destination)
    if destination.exists():
        raise FileExistsError(f'Dataset destination already exists: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.datasets-', dir=destination.parent))
    try:
        prefix = resolver.manifest.get('data_prefix', 'test_data')
        for item in resolver.manifest['files']:
            if item['path'].startswith(prefix+'/'):
                target = stage/Path(item['path']).relative_to(prefix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolver.resolve(item['path']), target)
                if sha(target) != item['sha256']: raise ValueError('Dataset copy changed')
        stage.rename(destination)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return {'status': 'restored', 'data_root': str(destination)}
