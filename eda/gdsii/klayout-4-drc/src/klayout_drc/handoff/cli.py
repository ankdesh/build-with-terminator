"""Portable setup, evidence, evaluation, and reporting front door."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from .config import load


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--config', type=Path)
    common.add_argument('--dry-run', action='store_true')
    for key in ('harness', 'fonts', 'data', 'work', 'archive'):
        common.add_argument('--'+key+'-root', dest='path_'+key)
    for key in ('cpus', 'workers', 'memory-mb', 'timeout-seconds'):
        common.add_argument('--'+key, type=int)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('setup', 'doctor'):
        cmd = sub.add_parser(command, parents=[common]); cmd.add_argument('--with-asic', action='store_true')
        if command == 'setup':
            cmd.add_argument('--system-packages', action='store_true'); cmd.add_argument('--python-only', action='store_true')
        else: cmd.add_argument('--reports-only', action='store_true')
    archive = sub.add_parser('archive').add_subparsers(dest='action', required=True)
    for action in ('create', 'pack', 'restore', 'verify', 'list'):
        cmd = archive.add_parser(action, parents=[common])
        cmd.add_argument('--snapshot', default='2026-10-28')
        if action == 'create': cmd.add_argument('--move-reports', action='store_true')
        if action in ('pack','restore'): cmd.add_argument('--bundle', type=Path, required=True)
        if action == 'restore':
            cmd.add_argument('--output', type=Path, required=True); cmd.add_argument('--sha256')
    datasets = sub.add_parser('datasets').add_subparsers(dest='action', required=True)
    for action in ('list','restore','verify'):
        cmd = datasets.add_parser(action, parents=[common]); cmd.add_argument('--snapshot', type=Path)
        cmd.add_argument('--suite', choices=('ab','c1','c2c3','all'), default='all')
        if action == 'restore': cmd.add_argument('--output', type=Path, required=True)
    cmd = sub.add_parser('evaluate', parents=[common])
    cmd.add_argument('--suite', choices=('ab','c1','c2c3')); cmd.add_argument('--experiment')
    cmd.add_argument('--dataset', type=Path); cmd.add_argument('--output', type=Path); cmd.add_argument('--run-id')
    cmd.add_argument('--mode', choices=('heuristic','no_change','script_file','agent'))
    cmd.add_argument('--provider', choices=('openai','bedrock')); cmd.add_argument('--model'); cmd.add_argument('--region'); cmd.add_argument('--temperature', type=float)
    cmd.add_argument('--case', action='append'); cmd.add_argument('--rule', action='append'); cmd.add_argument('--tier', action='append')
    cmd.add_argument('--limit', type=int); cmd.add_argument('--profile', choices=('legacy_mini','asap7_curated'))
    cmd.add_argument('--candidate-script', type=Path); cmd.add_argument('--allow-incomplete', action='store_true')
    cmd = sub.add_parser('report', parents=[common])
    from .reporting import BUILDERS
    cmd.add_argument('--kind', choices=('saved','all', *BUILDERS), default='saved')
    cmd.add_argument('--snapshot', type=Path); cmd.add_argument('--campaign', action='append')
    cmd.add_argument('--output', type=Path); cmd.add_argument('--run-id', default=None)
    return p


def dispatch(args):
    overrides = {'paths.'+k: getattr(args, 'path_'+k, None) for k in ('harness','fonts','data','work','archive')}
    overrides.update({'resources.'+k: getattr(args,k,None) for k in ('cpus','workers','memory_mb','timeout_seconds')})
    settings = load(args.config, overrides)
    if args.command == 'setup':
        from .environment import setup
        return setup(settings, args.system_packages, args.with_asic, args.python_only, args.dry_run)
    if args.command == 'doctor':
        from .environment import doctor
        return {'status':'dry-run'} if args.dry_run else doctor(settings, args.reports_only, args.with_asic)
    if args.command == 'archive':
        from . import archive
        path = settings.path('archive')/args.snapshot
        if args.dry_run:
            return {'status':'dry-run', 'action':args.action, 'snapshot':str(path),
                    'files':archive.inventory(settings.root, settings.path('data'), settings.path('work')) if args.action == 'create' else None}
        if args.action == 'create': return archive.create(settings.root, settings.path('archive'), args.snapshot, args.move_reports, settings.path('data'), settings.path('work'))
        if args.action == 'verify':
            index_path = settings.path('archive')/'index.json'
            entries = json.loads(index_path.read_text()).get('snapshots', []) if index_path.exists() else []
            expected = next((e['manifest_sha256'] for e in entries if e['snapshot'] == args.snapshot), None)
            return archive.verify(path, expected)
        if args.action == 'pack': return archive.pack(path, args.bundle)
        if args.action == 'restore': return archive.restore(args.bundle, args.output, args.sha256)
        index = settings.path('archive')/'index.json'
        return json.loads(index.read_text()) if index.exists() else {'snapshots': []}
    if args.command == 'datasets':
        from .archive import Resolver, dataset_catalog, restore_datasets
        from .datasets import verify_data
        if args.dry_run: return {'status':'dry-run', 'action':args.action}
        if args.action == 'list':
            return {'datasets':Resolver(args.snapshot).manifest['datasets'] if args.snapshot else dataset_catalog(settings.root, settings.path('data'))}
        if args.action == 'restore':
            if not args.snapshot: raise ValueError('datasets restore requires --snapshot')
            return restore_datasets(args.snapshot, args.output)
        from .evaluation import apply_environment
        apply_environment(settings)
        resolver = Resolver(args.snapshot) if args.snapshot else None
        return verify_data(resolver.root/resolver.manifest.get('data_prefix', 'test_data') if resolver else settings.path('data'), args.suite)
    if args.command == 'evaluate':
        from .evaluation import evaluate
        return evaluate(settings, args)
    if args.command == 'report':
        from datetime import datetime, timezone
        from .reporting import report
        if args.run_id is None: args.run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        if Path(args.run_id).name != args.run_id or args.run_id in ('.','..'): raise ValueError('Invalid run ID')
        return report(settings, args)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
        print(json.dumps(result, indent=2, default=str))
        return 1 if result.get('status') in ('missing-prerequisites','failed','blocked') else 0
    except (ValueError, OSError, KeyError, ImportError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status':'blocked', 'error':str(exc)}), file=sys.stderr)
        return 1

if __name__ == '__main__': raise SystemExit(main())
