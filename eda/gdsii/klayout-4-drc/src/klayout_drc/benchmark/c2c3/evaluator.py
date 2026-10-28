"""Serial, single-attempt campaigns with separate repair and restraint scoring."""
from collections import Counter
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import time
from .contracts import Manifest, sha256, safe_path, write_json
from .generator import added_records, canonical_digest, load_layout, scoped_records
from ..acceptance import run_checker
from ..evaluator import BenchmarkEvaluator
from ...marker_comparison import compare_markers, marker_records
from ...parser import DRCParser
from ...profile import DRCProfileManager
from ...run_manifest import RunSpec
from ...single_shot import SingleShotOrchestrator

NO_CHANGE = 'import sys\nimport klayout.db as db\nl=db.Layout(); l.read(sys.argv[1]); l.write(sys.argv[2])\n'


def checker_identity():
    """Freeze the actual host checker separately from the ORFS tools."""
    import klayout.db as db
    executable = shutil.which('klayout')
    if executable is None:
        raise ValueError('Missing KLayout checker executable')
    path = Path(executable).resolve()
    runtime = Path('/usr/lib/klayout/klayout')
    runtime = runtime if runtime.is_file() else path
    return {'path': str(path), 'sha256': sha256(path),
            'runtime_path': str(runtime), 'runtime_sha256': sha256(runtime),
            'version': subprocess.check_output([str(path), '-v'], text=True, timeout=10).strip(),
            'python_klayout_version': db.__version__}


def verify_dataset(root):
    root = Path(root)
    manifest = Manifest.load(root/'manifest.json')
    profile = DRCProfileManager().get_profile(manifest.profile)
    if sha256(profile.deck_path) != manifest.deck_sha256 or sha256(root/'qualification.json') != manifest.qualification_sha256:
        raise ValueError('Checker or qualification changed')
    if json.loads((root/'qualification.json').read_text()).get('checker') != checker_identity():
        raise ValueError('Missing or changed qualified checker identity; qualify the pinned checker first')
    for case in manifest.cases:
        if sha256(safe_path(root, case.gds)) != case.gds_sha256:
            raise ValueError(f'Changed input: {case.case_id}')
        for path_key, hash_key in [('reference_gds', 'reference_sha256'), ('reference_report', 'reference_report_sha256'),
                                   ('input_report', 'input_report_sha256')]:
            if sha256(safe_path(root, case.evidence[path_key])) != case.evidence[hash_key]:
                raise ValueError(f'Changed evidence: {case.case_id} {path_key}')
        audit = case.source.get('native_public_audit')
        if audit and sha256(safe_path(root, audit['report'])) != audit['report_sha256']:
            raise ValueError(f'Changed native public audit: {case.case_id}')
    return manifest


def score_case(case, summary, root, run_dir):
    """No repair or restraint credit is possible without a valid completed run."""
    result = {'case_id': case.case_id, 'level': case.level, 'kind': case.kind, 'source_group': case.source_group,
              'rule_ids': sorted({r['rule'] for r in case.evidence['target_markers']} or set(case.evidence['target_scope_rules'])),
              'passed': False, 'verdict': summary.verdict, 'validation_level': summary.validation_level,
              'run_dir': str(run_dir), 'failure_stage': None, 'metrics': case.metrics,
              'initial_total': summary.total_before, 'final_total': summary.total_after,
              'area_added_um2': summary.diff_report.total_added_area_um2 if summary.diff_report else None,
              'area_removed_um2': summary.diff_report.total_removed_area_um2 if summary.diff_report else None,
              'candidate_peak_rss_bytes': summary.execution_result.peak_rss_bytes,
              'memory_measurement': 'sampled process-tree RSS lower bound', 'cost': None, 'usage': None}
    if summary.execution_result.status != 'success':
        result['failure_stage'] = {'blocked': 'infrastructure', 'oracle_mismatch': 'oracle',
                                   'drc_error': 'checker', 'model_error': 'synthesis'}.get(summary.verdict, 'python_execution')
        result['error'] = summary.error_message or summary.execution_result.error_message
        return result
    if summary.validation_result is None or not summary.validation_result.is_valid:
        result.update(verdict='invalid_patch', failure_stage='edit_policy')
        return result
    if summary.total_after is None:
        result.update(verdict='checker_error', failure_stage='checker')
        return result
    after_layout = load_layout(Path(run_dir)/'patched.gds')
    before_layout = load_layout(Path(root)/case.gds)
    unchanged = canonical_digest(before_layout) == canonical_digest(after_layout)
    result['unchanged'] = unchanged
    if case.kind != 'repair':
        result.update(passed=unchanged, verdict='unchanged_control' if unchanged else 'unnecessary_edit',
                      failure_stage=None if unchanged else 'restraint')
        return result
    after = DRCParser().parse(Path(run_dir)/'after.lyrdb')
    baseline = DRCParser().parse(Path(root)/case.evidence['reference_report'])
    comparison = compare_markers(baseline, after, .00025)
    local = added_records(scoped_records(baseline, case.scope_box_um), scoped_records(after, case.scope_box_um))
    passed = not local and not comparison['introduced'] and not comparison['ambiguous']
    result.update(passed=passed, verdict='target_repaired_geometry_only' if passed else
                  'ambiguous' if comparison['ambiguous'] else 'regression' if comparison['introduced'] > len(local) else 'unresolved',
                  failure_stage=None if passed else 'geometry_reasoning', baseline_relative=comparison,
                  remaining_local_markers=local)
    return result


def summarize(manifest, mode, results):
    def group(items, planned):
        blocked = sum(r['verdict'] in ('blocked', 'oracle_mismatch') for r in items)
        return {'planned': planned, 'observed': len(items), 'passed': sum(r['passed'] for r in items),
                'blocked': blocked,
                'outcomes': dict(Counter(r['verdict'] for r in items)),
                'rate_observed': sum(r['passed'] for r in items)/len(items) if items and len(items) == planned and not blocked else None}
    rules = sorted({rule for r in results for rule in r.get('rule_ids', [])})
    sources = sorted({r['source_group'] for r in results})
    return {'mode': mode, 'validation_level': 'geometry_only', 'dataset_complete': manifest.complete,
            'scopes': {'primary': manifest.profile, 'public_audit': 'asap7_public_full',
                       'public_audit_is_acceptance_gate': False},
            'repair': group([r for r in results if r['kind'] == 'repair'], 30),
            'clean_control': group([r for r in results if r['kind'] == 'clean_control'], 10),
            'no_edit': group([r for r in results if r['kind'] == 'no_edit'], 10),
            'levels': {str(level): {kind: group([r for r in results if r['level'] == level and r['kind'] == kind],
                                              6 if kind == 'repair' else 2)
                                    for kind in ('repair', 'clean_control', 'no_edit')} for level in range(1, 6)},
            'outcomes': dict(Counter(r['verdict'] for r in results)), 'results': results,
            'failures': dict(Counter(r['failure_stage'] for r in results if r.get('failure_stage'))),
            'public_audits': dict(Counter(r.get('public_audit', {}).get('status', 'not_run') for r in results)),
            'model_requests': sum(r.get('model_request_attempted', False) for r in results),
            'model_responses': sum(r.get('model_response_received', False) for r in results),
            'rules': {rule: {kind: group([r for r in results if rule in r.get('rule_ids', []) and r['kind'] == kind],
                                         sum(c.kind == kind and rule in ({m['rule'] for m in c.evidence['target_markers']}
                                             or set(c.evidence['target_scope_rules'])) for c in manifest.cases))
                              for kind in ('repair', 'clean_control', 'no_edit')} for rule in rules},
            'sources': {source: {kind: group([r for r in results if r['source_group'] == source and r['kind'] == kind],
                                              sum(c.kind == kind and c.source_group == source for c in manifest.cases))
                                  for kind in ('repair', 'clean_control', 'no_edit')} for source in sources},
            'limits': ['One model attempt per case; no consistency estimate.',
                       'Connectivity and timing are unverified.', 'Few source designs; no broad generalization claim.']}


def export_report(output, summary):
    output = Path(output)
    write_json(output/'summary.json', summary)
    with (output/'summary.csv').open('w', newline='') as handle:
        fields = ['case_id', 'level', 'kind', 'source_group', 'passed', 'verdict', 'failure_stage', 'wall_seconds', 'run_dir',
                  'scored_profile', 'public_audit_profile', 'public_audit_status', 'rule_ids', 'initial_total', 'final_total',
                  'area_added_um2', 'area_removed_um2', 'candidate_peak_rss_bytes', 'context_shapes', 'model_request_bytes',
                  'instance_count', 'hierarchy_depth', 'route_segment_count', 'via_count', 'local_routing_occupancy',
                  'coupled_rules', 'prompt_tokens', 'completion_tokens', 'cost']
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for row in summary['results']:
            usage = row.get('usage') or {}
            writer.writerow({**row, **row.get('metrics', {}), 'rule_ids': '|'.join(row.get('rule_ids', [])),
                             'scored_profile': summary['scopes']['primary'],
                             'public_audit_profile': summary['scopes']['public_audit'],
                             'public_audit_status': row.get('public_audit', {}).get('status', 'not_run'),
                             'prompt_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
                             'completion_tokens': usage.get('completion_tokens', usage.get('output_tokens'))})
    breakdown = [{'dimension': dimension, 'value': value, 'kind': kind, **counts,
                  'scored_profile': summary['scopes']['primary'], 'public_audit_profile': summary['scopes']['public_audit']}
                 for dimension in ('levels', 'rules', 'sources') for value, groups in summary[dimension].items()
                 for kind, counts in groups.items()]
    with (output/'breakdown.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['dimension', 'value', 'kind', 'planned', 'observed', 'passed', 'blocked',
            'rate_observed', 'scored_profile', 'public_audit_profile'], extrasaction='ignore')
        writer.writeheader(); writer.writerows(breakdown)
    lines = ['# C2+C3 single-attempt geometry evaluation', '', f'Mode: {summary["mode"]}. Dataset complete: {summary["dataset_complete"]}.',
             'Primary scope: `asap7_c2c3_v1`. Full public audit: `asap7_public_full`, diagnostic only.',
             'Electrical connectivity and timing are unverified.', '', '| Measure | Passed | Observed | Planned |', '|---|---:|---:|---:|']
    for key in ('repair', 'clean_control', 'no_edit'):
        value = summary[key]; lines.append(f'| {key} | {value["passed"]} | {value["observed"]} | {value["planned"]} |')
    lines += ['', f'Model requests: {summary["model_requests"]}; parsed responses: {summary["model_responses"]}.',
              f'Failure stages: {json.dumps(summary["failures"], sort_keys=True)}.',
              f'Public audit statuses: {json.dumps(summary["public_audits"], sort_keys=True)}.']
    lines += ['', '| Dimension | Value | Kind | Passed | Observed | Planned | Rate |', '|---|---|---|---:|---:|---:|---:|']
    for row in breakdown:
        rate = f'{row["rate_observed"]:.1%}' if row['rate_observed'] is not None else 'unavailable'
        lines.append(f'| {row["dimension"]} | {row["value"]} | {row["kind"]} | {row["passed"]} | {row["observed"]} | {row["planned"]} | {rate} |')
    lines += ['', '| Case | Level | Kind | Result |', '|---|---:|---|---|']
    lines += [f'| {r["case_id"]} | {r["level"]} | {r["kind"]} | {r["verdict"]} |' for r in summary['results']]
    lines += ['', *summary['limits']]
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def evaluate(root, output, mode, allow_incomplete=False):
    invocation_started = time.monotonic()
    root, output = Path(root).resolve(), Path(output).resolve()
    if mode not in ('agent', 'heuristic', 'no_change'):
        raise ValueError('Unknown comparison mode')
    manifest = verify_dataset(root)
    if not manifest.complete and (mode == 'agent' or not allow_incomplete):
        raise ValueError('Freeze 50 qualified cases before the agent campaign; incomplete baselines require --allow-incomplete')
    if len(manifest.cases) > 50:
        raise ValueError('Campaign request budget exceeded')
    output.mkdir(parents=True, exist_ok=True)
    lock = output/'.campaign.lock'
    with lock.open('x'): pass
    try:
        model_config = None
        if mode == 'agent':
            config_script = Path(__file__).resolve().parents[4]/'harness/scripts/model-config.mjs'
            model_config = json.loads(subprocess.check_output(['node', str(config_script)], text=True))
            if model_config['provider'] != 'bedrock':
                raise ValueError('C2+C3 agent campaign requires explicit Bedrock configuration')
        frozen = BenchmarkEvaluator._source_bundle()
        identity = {'manifest_sha256': sha256(root/'manifest.json'), 'mode': mode,
                    'source_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(),
                    'model_config': model_config, 'checker': checker_identity(),
                    'case_ids': [c.case_id for c in manifest.cases], 'request_budget': 50}
        if (output/'campaign.json').exists():
            if json.loads((output/'campaign.json').read_text()) != identity:
                raise ValueError('Campaign changed; use a new directory')
        else:
            write_json(output/'campaign.json', identity); write_json(output/'frozen_source.json', frozen)
        noop = output/'no_change.py'
        if not noop.exists(): noop.write_text(NO_CHANGE)
        results = []
        stop_reason = None
        profile = DRCProfileManager().get_profile(manifest.profile)
        for case in manifest.cases:
            checkpoint = output/'cases'/f'{case.case_id}.json'
            claim = checkpoint.with_suffix('.attempt.json')
            if checkpoint.exists():
                saved = json.loads(checkpoint.read_text()); results.append(saved)
                if saved.get('stop_campaign'): stop_reason = saved['stop_campaign']
                continue
            checkpoint.parent.mkdir(exist_ok=True)
            if stop_reason:
                result = {'case_id': case.case_id, 'level': case.level, 'kind': case.kind,
                          'rule_ids': sorted({r['rule'] for r in case.evidence['target_markers']} or set(case.evidence['target_scope_rules'])),
                          'source_group': case.source_group, 'passed': False, 'verdict': 'blocked',
                          'failure_stage': 'infrastructure', 'error': stop_reason, 'run_dir': None,
                          'model_request_attempted': False, 'model_response_received': False, 'wall_seconds': 0.}
                write_json(checkpoint, result); results.append(result)
                continue
            with claim.open('x') as handle:
                json.dump({'case_id': case.case_id, 'mode': mode, 'started_unix': time.time()}, handle)
            started = time.monotonic()
            spec = RunSpec(case_name=case.case_id, input_gds=root/case.gds, drc_script=profile.deck_path,
                           profile_name=profile.name, candidate_mode='script_file' if mode == 'no_change' else mode,
                           candidate_script=noop if mode == 'no_change' else None, output_root=output/'runs',
                           expected_markers=case.evidence['input_markers'], edit_policy=case.edit_policy)
            orchestrator = SingleShotOrchestrator(spec)
            summary = orchestrator.run()
            result = score_case(case, summary, root, orchestrator.paths.run_dir)
            result['wall_seconds'] = time.monotonic()-started
            result['model_request_attempted'] = (orchestrator.paths.run_dir/'model_attempt.json').exists()
            result['model_response_received'] = (orchestrator.paths.run_dir/'model_response.json').exists()
            request = orchestrator.paths.run_dir/'model_request.json'
            result['model_request_bytes'] = request.stat().st_size if request.exists() else None
            if mode == 'agent' and (summary.verdict in ('blocked', 'oracle_mismatch', 'drc_error') or
                                    (summary.verdict == 'model_error' and not (orchestrator.paths.run_dir/'model_response.json').exists())):
                stop_reason = 'Campaign stopped after infrastructure or model-service failure; remaining cases were not dispatched'
                result['stop_campaign'] = stop_reason
            generation = orchestrator.paths.run_dir/'generation_manifest.json'
            if generation.exists():
                result['usage'] = json.loads(generation.read_text()).get('usage')
            if summary.execution_result.status == 'success' and summary.validation_result and summary.validation_result.is_valid:
                try:
                    audit = orchestrator.paths.run_dir/'public_after.lyrdb'
                    data = run_checker(orchestrator.paths.patched_gds, DRCProfileManager().get_profile('asap7_public_full'), audit)
                    result['public_audit'] = {'status': 'complete', 'counts': data.rule_summary, 'sha256': sha256(audit),
                                              'acceptance_gate': False}
                except Exception as exc:
                    result['public_audit'] = {'status': 'failed', 'error': str(exc), 'acceptance_gate': False}
            write_json(checkpoint, result); results.append(result)
            export_report(output, summarize(manifest, mode, results))
            print(f'{mode} {case.case_id}: {result["verdict"]}', flush=True)
        summary = summarize(manifest, mode, results)
        summary['this_invocation_wall_seconds'] = time.monotonic()-invocation_started
        summary['summed_case_seconds'] = sum(r.get('wall_seconds', 0.) for r in results)
        export_report(output, summary)
        write_json(output/'artifact_hashes.json', {str(p.relative_to(output)): sha256(p) for p in sorted(output.rglob('*'))
                   if p.is_file() and p.name not in ('artifact_hashes.json', '.campaign.lock')})
        return summary
    finally:
        lock.unlink()


def compare_campaigns(campaigns, output):
    """Compare only campaigns with identical frozen inputs and source contracts."""
    summaries, identities = {}, {}
    for path in map(Path, campaigns):
        identity = json.loads((path/'campaign.json').read_text())
        summary = json.loads((path/'summary.json').read_text())
        mode = identity['mode']
        if mode in identities:
            raise ValueError('Duplicate comparison mode')
        identities[mode], summaries[mode] = identity, summary
    if set(summaries) != {'agent', 'heuristic', 'no_change'}:
        raise ValueError('Comparison requires agent, heuristic, and no_change campaigns')
    agent = identities['agent']
    for identity in identities.values():
        if any(identity[key] != agent[key] for key in ('manifest_sha256', 'source_sha256', 'case_ids', 'checker')):
            raise ValueError('Comparison inputs or source contracts differ')
    by_mode = {mode: {row['case_id']: row for row in summary['results']} for mode, summary in summaries.items()}
    rows = []
    for case_id in agent['case_ids']:
        if any(case_id not in results for results in by_mode.values()):
            raise ValueError('Comparison has missing checkpoints')
        model, heuristic, noop = [by_mode[mode][case_id] for mode in ('agent', 'heuristic', 'no_change')]
        rows.append({'case_id': case_id, 'level': model['level'], 'kind': model['kind'],
                     'agent': model['verdict'], 'heuristic': heuristic['verdict'], 'no_change': noop['verdict'],
                     'agent_passed': model['passed'], 'heuristic_passed': heuristic['passed'], 'no_change_passed': noop['passed']})
    result = {'validation_level': 'geometry_only', 'model_config': agent['model_config'],
              'scopes': summaries['agent']['scopes'],
              'checker': agent['checker'],
              'manifest_sha256': agent['manifest_sha256'], 'case_count': len(rows),
              'measures': {mode: {key: summary[key] for key in ('repair', 'clean_control', 'no_edit', 'levels', 'outcomes', 'failures', 'public_audits')}
                           for mode, summary in summaries.items()},
              'request_attempts': sum(r.get('model_request_attempted', False) for r in summaries['agent']['results']),
              'responses_received': sum(r.get('model_response_received', False) for r in summaries['agent']['results']),
              'rows': rows, 'cost': None,
              'limits': ['One attempt per case.', 'Electrical connectivity and timing unverified.',
                         'Few designs and six repair cases per level; no consistency or broad generalization claim.']}
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    write_json(output/'comparison.json', result)
    with (output/'comparison.csv').open('w', newline='') as handle:
        fields = (list(rows[0]) if rows else ['case_id']) + ['scored_profile', 'public_audit_profile', 'public_audit_is_acceptance_gate']
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({**row, 'scored_profile': result['scopes']['primary'],
                         'public_audit_profile': result['scopes']['public_audit'],
                         'public_audit_is_acceptance_gate': False} for row in rows)
    lines = ['# C2+C3 matched comparison', '', 'All results are geometry-only.',
             'Primary scope: `asap7_c2c3_v1`. Full public audit: `asap7_public_full`, diagnostic only.', '',
             '| Mode | Repairs / 30 | Clean controls / 10 | Read-only controls / 10 |', '|---|---:|---:|---:|']
    for mode, measures in result['measures'].items():
        lines.append(f'| {mode} | {measures["repair"]["passed"]} | {measures["clean_control"]["passed"]} | {measures["no_edit"]["passed"]} |')
    lines += ['', f'Model request attempts: {result["request_attempts"]}; responses: {result["responses_received"]}.', '',
              'Blocked cases are completion accounting, not model-performance observations.', '',
              '| Case | Level | Kind | Agent | Heuristic | No change |', '|---|---:|---|---|---|---|']
    lines += [f'| {r["case_id"]} | {r["level"]} | {r["kind"]} | {r["agent"]} | {r["heuristic"]} | {r["no_change"]} |' for r in rows]
    lines += ['', *result['limits']]
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return result
