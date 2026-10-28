"""Thin dispatch to existing evaluators. Keep campaign gates and retry policy."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from .archive import new_output, sha, write_json


def apply_environment(settings):
    # PATH shims make legacy subprocess tool names use exactly the configured executables.
    directory = settings.path('work')/'tools'
    directory.mkdir(parents=True, exist_ok=True)
    for key in ('node', 'klayout', 'bwrap'):
        executable = shutil.which(settings.tool(key))
        if not executable: raise ValueError(f'Missing configured executable: {key}={settings.tool(key)}')
        target = directory/key
        if target.exists() and not target.is_symlink(): raise ValueError(f'Tool shim collision: {target}')
        executable = Path(executable).resolve()
        target.unlink(missing_ok=True); target.symlink_to(executable)
    os.environ['PATH'] = str(directory)+os.pathsep+os.environ.get('PATH', '')
    os.environ['KLAYOUT_DRC_TIMEOUT_SECONDS'] = str(settings.values['resources']['timeout_seconds'])
    os.environ['KLAYOUT_DRC_MEMORY_MB'] = str(settings.values['resources']['memory_mb'])
    os.environ['KLAYOUT_DRC_KLAYOUT_BIN'] = str(directory/'klayout')
    os.environ['OMP_NUM_THREADS'] = str(settings.values['resources']['cpus'])
    if hasattr(os, 'sched_getaffinity'):
        available = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, available[:settings.values['resources']['cpus']])


def provider_environment(provider, model, region, temperature=None):
    if provider is not None: os.environ['KLAYOUT_DRC_MODEL_PROVIDER'] = provider
    if model is not None:
        if provider is None: raise ValueError('--model requires --provider')
        os.environ['BEDROCK_MODEL' if provider == 'bedrock' else 'OPENAI_MODEL'] = model
    if temperature is not None:
        import math
        if not provider or not math.isfinite(temperature): raise ValueError('Temperature requires a provider and a finite number')
        os.environ['BEDROCK_TEMPERATURE' if provider == 'bedrock' else 'OPENAI_TEMPERATURE'] = str(temperature)
    if region is not None:
        if provider != 'bedrock': raise ValueError('--region requires --provider bedrock')
        os.environ['BEDROCK_REGION'] = region


def evaluate(settings, args):
    if args.experiment:
        definition = json.loads((settings.root/'experiments/historical.json').read_text())['experiments'].get(args.experiment)
        if not definition: raise ValueError('Unknown experiment ID; see experiments/historical.json')
        suite = definition['suite']
    else: definition, suite = None, args.suite
    if not suite: raise ValueError('Supply --suite or --experiment')
    mode = args.mode or 'heuristic'
    if mode != 'agent' and (any((args.provider, args.model, args.region)) or args.temperature is not None):
        raise ValueError('Provider options require explicit --mode agent')
    if mode == 'agent' and not args.provider:
        raise ValueError('Live calls require explicit --mode agent and --provider')
    if suite != 'ab' and args.profile:
        raise ValueError('--profile is only supported for A/B fixtures')
    if suite == 'c2c3':
        if args.case or args.rule or args.tier or args.limit is not None or args.candidate_script:
            raise ValueError('C2+C3 campaigns do not support filters, limits, or candidate scripts')
        if mode == 'agent' and args.provider != 'bedrock':
            raise ValueError('C2+C3 agent campaigns require Bedrock')
        if args.workers is not None and args.workers != 1:
            raise ValueError('C2+C3 campaigns are serial; use --workers 1')
    elif args.allow_incomplete:
        raise ValueError('--allow-incomplete is only supported for C2+C3 local baselines')
    if mode == 'script_file' and not args.candidate_script:
        raise ValueError('--mode script_file requires --candidate-script')
    if args.candidate_script and mode != 'script_file':
        raise ValueError('--candidate-script requires --mode script_file')
    if suite != 'c2c3' and mode == 'no_change':
        raise ValueError('Use --mode script_file for a custom A/B or C1 candidate')
    if args.temperature is not None:
        import math
        if not math.isfinite(args.temperature): raise ValueError('Temperature must be finite')
    if args.limit is not None and args.limit < 1: raise ValueError('--limit must be positive')
    run_id = args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if Path(run_id).name != run_id or run_id in ('.', '..'): raise ValueError('Invalid run ID')
    output = Path(args.output).absolute() if args.output else settings.path('work')/'runs'/run_id
    output = new_output(output)
    if output.exists(): raise FileExistsError(f'Run output already exists: {output}')
    if output.is_relative_to(settings.path('archive')): raise ValueError('Fresh runs cannot write into archives')
    dataset = Path(args.dataset).absolute() if args.dataset else settings.path('data')/{'c1':'benchmark_v1','c2c3':'benchmark_c2c3','ab':'layouts'}[suite]
    plan = {'suite': suite, 'mode': mode, 'dataset': str(dataset), 'output': str(output),
            'run_id': run_id, 'provider': args.provider, 'model': args.model, 'region': args.region, 'temperature': args.temperature,
            'historical_definition': args.experiment, 'configuration': settings.public(),
            'effective_workers': 1 if suite == 'c2c3' else settings.values['resources']['workers']}
    if suite == 'ab':
        if args.rule or args.tier: raise ValueError('A/B fixtures support --case and --limit only')
        profile_name = args.profile or (definition or {}).get('profile', 'legacy_mini')
        subdir = 'legacy_mini_v2' if profile_name == 'legacy_mini' else 'asap7_beol_v1'
        cases = sorted((dataset/subdir).glob('*.gds'))
        if args.case: cases = [p for p in cases if p.stem in args.case]
        if args.case and set(args.case)-{p.stem for p in cases}: raise ValueError('Unknown or excluded case ID')
        if args.limit: cases = cases[:args.limit]
        if not cases: raise ValueError('No A/B fixtures selected')
        plan['case_ids'] = [p.stem for p in cases]
    elif suite == 'c1':
        from ..benchmark.manifest import BenchmarkManifestManager as Manifests
        from ..benchmark.types import DifficultyTier
        manifest = Manifests.load(dataset/'manifest.json')
        cases = Manifests.filter_cases(manifest, rules=args.rule, tiers=[DifficultyTier(t) for t in args.tier] if args.tier else None)
        if definition: cases = [c for c in cases if c.case_id in definition['case_ids']]
        if args.case: cases = [c for c in cases if c.case_id in args.case]
        if args.case and set(args.case)-{c.case_id for c in cases}: raise ValueError('Unknown or excluded case ID')
        if args.limit: cases = cases[:args.limit]
        if not cases: raise ValueError('No C1 cases selected')
        plan['case_ids'] = [c.case_id for c in cases]
    else:
        if mode == 'script_file': raise ValueError('C2+C3 supports heuristic, no_change, and agent')
        plan['case_ids'] = [c['case_id'] for c in json.loads((dataset/'manifest.json').read_text())['cases']]
    if args.dry_run: return {'status': 'dry-run', **plan}
    apply_environment(settings)
    provider_environment(args.provider, args.model, args.region, args.temperature)
    from ..repair_executor import sandbox_availability
    sandbox_availability.cache_clear()
    if problem := sandbox_availability(): raise ValueError(problem)
    from ..benchmark.evaluator import BenchmarkEvaluator
    from ..profile import DRCProfileManager
    from .environment import doctor
    runtime = doctor(settings)
    if runtime['status'] != 'ready':
        raise ValueError('Run doctor and resolve missing prerequisites before evaluation: '+json.dumps(runtime['checks']))
    # Exclusive directory creation also rejects concurrent requests using the same output.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'handoff_run.json', {**plan, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'python': sys.version, 'runtime': runtime['checks'],
        'runtime_lock_sha256': sha(settings.root/'config/runtime-lock.json'),
        'harness_install_lock_sha256': sha(settings.root/'config/harness-pnpm-lock.yaml'),
        'dataset_sha256': sha(dataset/'manifest.json') if (dataset/'manifest.json').exists() else None,
        'source_sha256': BenchmarkEvaluator._source_digest(), 'definition': definition,
        'cli_options': {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
        'fixture_sha256': {str(p.relative_to(dataset)): sha(p) for p in cases} if suite == 'ab' else None})
    if suite == 'c1':
        evaluator = BenchmarkEvaluator(dataset, output, workers=settings.values['resources']['workers'])
        result = evaluator.evaluate_batch(cases, mode=mode, candidate_script=args.candidate_script).to_dict()
    elif suite == 'c2c3':
        from ..benchmark.c2c3.evaluator import evaluate as c2c3_evaluate
        result = c2c3_evaluate(dataset, output, mode, args.allow_incomplete)
    else:
        from ..cli import execute_single_shot
        profile = DRCProfileManager().get_profile(profile_name)
        result = {'results': [execute_single_shot(p, profile.deck_path, profile.name, mode,
                   args.candidate_script, run_id=f'{i:03}_{p.stem}', runs_dir=output/'runs') for i,p in enumerate(cases)]}
        write_json(output/'summary.json', result)
    write_json(output/'handoff_complete.json', {'completed_utc': datetime.now(timezone.utc).isoformat(),
                'summary_sha256': sha(output/'summary.json')})
    failures = {'blocked', 'checker_error', 'drc_error', 'model_error', 'execution_error'}
    recorded = result.get('results', [])
    infrastructure_failed = any(r.get('verdict') in failures for r in recorded)
    return {'status': 'failed' if infrastructure_failed else 'complete', 'output': str(output), 'summary': result}
