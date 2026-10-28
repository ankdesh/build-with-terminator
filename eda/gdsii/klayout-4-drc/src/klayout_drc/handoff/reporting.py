"""Render saved evidence without rescoring or calling a model."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .archive import new_output, Resolver, sha, verify, write_json

BUILDERS = {
    'c1-guide': 'capture_c1_examples.py',
    'c1-quick': 'build_c1_quick_review.py',
    'c1-bedrock': 'build_c1_bedrock_quick_review.py',
    'c2c3-results': 'report_c2c3_results.py',
    'c2c3-atlas': 'build_c2c3_snapshot_atlas.py',
    'c2c3-selected': 'build_c2c3_selected_review.py',
}


def table(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)


def saved_report(campaigns, output):
    """Use recorded numerators, denominators, classifications, and corrections."""
    records, paired, receipts = {}, {}, {}
    for path in campaigns:
        name = path.name
        if name in records: raise ValueError(f'Duplicate campaign name: {name}')
        source = path/'summary.json' if (path/'summary.json').is_file() else path/'results.json'
        summary = json.loads(source.read_text())
        records[name] = summary
        receipts[name] = {'path': str(source), 'sha256': sha(source)}
        dest = output/name; dest.mkdir()
        shutil.copy2(source, dest/source.name)
        rows = summary.get('results', [])
        table(dest/'results.csv', rows)
        # Preserve original Markdown and CSV, including historical corrections.
        for p in path.iterdir():
            if p.is_file() and p.suffix in ('.md', '.csv'):
                shutil.copy2(p, dest/p.name)
        for row in rows:
            cid = row.get('case_id') or row.get('run_id')
            if cid: paired.setdefault(cid, {'case_id': cid})[name] = {
                k: row.get(k) for k in ('verdict', 'passed', 'failure_stage', 'initial_total', 'final_total')}
    write_json(output/'comparison.json', {'recorded_outcomes': records, 'paired': list(paired.values())})
    table(output/'comparison.csv', list(paired.values()))
    lines = ['# Saved evaluation evidence', '', 'Values below come from saved summaries. No cases were rescored.', '']
    for name, summary in records.items():
        lines += [f'## {name}', '', '```json', json.dumps({k:v for k,v in summary.items() if k != 'results'}, indent=2), '```', '']
    (output/'report.md').write_text('\n'.join(lines))
    return receipts


def report(settings, args):
    output = Path(args.output).absolute() if args.output else settings.path('work')/'reports'/args.run_id
    output = new_output(output)
    if output.exists(): raise FileExistsError(f'Report output already exists: {output}')
    if output.is_relative_to(settings.path('archive')): raise ValueError('Reports cannot write into archives')
    snapshot = Path(args.snapshot).absolute() if args.snapshot else settings.path('archive')/'2026-10-28'
    resolver = Resolver(snapshot) if snapshot.exists() and (args.snapshot or not args.campaign) else None
    if args.snapshot and not resolver: raise ValueError('Snapshot does not exist')
    kinds = list(BUILDERS) if args.kind == 'all' else [args.kind]
    root = resolver.root if resolver else settings.root
    campaigns = []
    for item in args.campaign or []:
        if resolver:
            try: source = resolver.resolve(str(Path(item)/'summary.json'))
            except FileNotFoundError: source = resolver.resolve(str(Path(item)/'results.json'))
            campaigns.append(source.parent)
        else: campaigns.append(Path(item).absolute())
    if not campaigns and args.kind == 'saved':
        campaigns = sorted(p.parent for p in (root/'reports/runs').glob('*/summary.json'))
    if not campaigns and args.kind == 'saved': raise ValueError('No saved campaigns found')
    if args.campaign and args.kind not in ('saved', 'c1-bedrock'):
        raise ValueError('--campaign supports saved reports and the c1-bedrock visual builder')
    if args.kind == 'c1-bedrock' and args.campaign and len(campaigns) != 1:
        raise ValueError('c1-bedrock requires one campaign')
    plan = {'status': 'dry-run', 'kind': args.kind, 'output': str(output), 'source_root': str(root),
            'campaigns': list(map(str, campaigns)), 'builders': kinds}
    if args.dry_run: return plan
    if resolver: verify(snapshot)
    output.mkdir(parents=True, exist_ok=False)
    receipts = {}
    if args.kind == 'saved':
        receipts = saved_report(campaigns, output)
    else:
        # Builders keep their historical layout and selections. All writes occur in
        # a private copy. Symlinked datasets and runs are read-only inputs.
        workspace = output/'workspace'; workspace.mkdir()
        for name in ('test_data', 'reports'):
            source = root/resolver.manifest.get('data_prefix', 'test_data') if name == 'test_data' and resolver else root/name
            (workspace/name).symlink_to(source, target_is_directory=True)
        for name in ('docs', 'scripts'):
            source = root/name if name == 'docs' else settings.root/name
            shutil.copytree(source, workspace/name, ignore=shutil.ignore_patterns('__pycache__'))
        (workspace/'output').mkdir()
        if (root/'output/pdf').exists(): shutil.copytree(root/'output/pdf', workspace/'output/pdf')
        # The historical comparison publisher writes reports/runs/<comparison>.
        # Give it a writable reports tree while leaving raw campaigns untouched.
        (workspace/'reports').unlink(); (workspace/'reports/runs').mkdir(parents=True)
        for source in (root/'reports/runs').iterdir():
            if source.name != 'c2c3_v1_comparison':
                (workspace/'reports/runs'/source.name).symlink_to(source, target_is_directory=source.is_dir())
        if resolver:
            for alias in resolver.aliases:
                link = workspace/alias['prefix']
                if not link.exists():
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(resolver.root/alias['prefix'], target_is_directory=True)
        env = {**os.environ, 'DRC_REPORT_ROOT': str(workspace),
               'DRC_REPORT_ORIGINAL_ROOT': str(resolver.original if resolver else settings.root),
               'DRC_REPORT_PATH_MAP': json.dumps(resolver.aliases if resolver else []),
               'DRC_REPORT_FONTS': str(settings.path('fonts')), 'QT_QPA_PLATFORM': 'offscreen',
               'PYTHONPATH': str(settings.root/'src')}
        if args.campaign:
            if args.kind != 'c1-bedrock' or len(campaigns) != 1:
                raise ValueError('--campaign with a visual builder is supported only for c1-bedrock')
            campaign_link = workspace/'reports/runs'/campaigns[0].name
            if not campaign_link.exists(): campaign_link.symlink_to(campaigns[0], target_is_directory=True)
            env['DRC_REPORT_CAMPAIGN'] = str(campaign_link)
        for kind in kinds:
            command = [sys.executable, str(workspace/'scripts'/BUILDERS[kind])]
            with (output/f'{kind}.log').open('w') as log:
                subprocess.run(command, cwd=workspace, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        from pypdf import PdfReader
        for path in sorted((workspace/'output/pdf').glob('*.pdf')):
            receipts[path.name] = {'sha256': sha(path), 'pages': len(PdfReader(path).pages)}
        # Recheck the complete archive, including all original PDF/PPT bytes.
        if resolver: verify(snapshot)
    write_json(output/'rebuild.json', {'kind': args.kind, 'source_snapshot': str(snapshot) if resolver else None,
        'manifest_sha256': sha(snapshot/'manifest.json') if resolver else None,
        'receipts': receipts, 'model_requests': 0, 'scoring': 'recorded outcomes; no rescoring'})
    return {'status': 'complete', 'output': str(output), 'receipts': receipts}
