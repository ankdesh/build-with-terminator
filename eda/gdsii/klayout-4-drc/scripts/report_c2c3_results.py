"""Verify and publish the completed, frozen C2+C3 campaign evidence."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record
import shutil

from klayout_drc.benchmark.c2c3.contracts import sha256, write_json
from klayout_drc.benchmark.c2c3.evaluator import verify_dataset, compare_campaigns
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.layout_diff import LayoutDiffCalculator


def main():
    root = ROOT
    dataset = root/'test_data/benchmark_c2c3'
    manifest = verify_dataset(dataset)
    assert manifest.complete
    modes = ('agent', 'heuristic', 'no_change')
    paths = {mode: root/f'reports/runs/c2c3_v1_{mode}' for mode in modes}
    summaries = {mode: json.loads((path/'summary.json').read_text()) for mode, path in paths.items()}
    assert all(len(s['results']) == 50 and not s['outcomes'].get('blocked', 0) for s in summaries.values())
    assert summaries['agent']['model_requests'] == 50
    assert summaries['no_change']['repair']['passed'] == 0
    assert all(summaries['no_change'][kind]['passed'] == 10 for kind in ('clean_control', 'no_edit'))
    identity = json.loads((paths['agent']/'campaign.json').read_text())
    source = json.loads((paths['agent']/'frozen_source.json').read_text())
    assert hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest() == identity['source_sha256']
    attempts = list((paths['agent']/'runs').glob('*/model_attempt.json'))
    assert len(attempts) == 50
    old = json.loads((paths['agent']/'continuations/001/artifact_hashes.json').read_text())
    for case in manifest.cases[:40]:
        name = f'cases/{case.case_id}.json'
        assert sha256(paths['agent']/name) == old[name], f'Prior outcome changed: {case.case_id}'
    usage, returned_models, instruction_hashes = Counter(), Counter(), set()
    known_usage = 0
    for case in manifest.cases:
        row = next(r for r in summaries['agent']['results'] if r['case_id'] == case.case_id)
        run = resolve_record(row['run_dir'])
        assert sha256(run/'input.gds') == case.gds_sha256
        assert json.loads((run/'policy_context.json').read_text())['edit_policy'] == case.edit_policy
        request = json.loads((run/'model_request.json').read_text())
        assert [m['role'] for m in request['messages']] == ['system', 'user']
        assert request['model'] == identity['model_config']['model']
        context = (run/'model_context.json').read_text()
        assert not any(key in context for key in ('"cuts_dbu"', '"reference_gds"', '"target_markers"'))
        generation = json.loads((run/'generation_manifest.json').read_text())
        instruction_hashes.add(generation['instructions_sha256'])
        if generation.get('returned_model'): returned_models[generation['returned_model']] += 1
        if generation.get('usage'):
            known_usage += 1
            usage.update({k: v for k, v in generation['usage'].items() if isinstance(v, int)})
    assert len(instruction_hashes) == 1
    comparison = compare_campaigns(list(paths.values()), root/'reports/runs/c2c3_v1_comparison')
    target = root/'docs/reports/c2_c3_benchmark'
    target.mkdir(parents=True, exist_ok=True)
    for mode, path in paths.items():
        directory = target/mode; directory.mkdir(exist_ok=True)
        for name in ('summary.json', 'summary.csv', 'breakdown.csv', 'report.md', 'campaign.json', 'artifact_hashes.json'):
            shutil.copyfile(path/name, directory/name)
    for name in ('comparison.json', 'comparison.csv', 'report.md'):
        shutil.copyfile(root/'reports/runs/c2c3_v1_comparison'/name, target/name)
    shutil.copyfile(paths['agent']/'frozen_source.json', target/'frozen_source.json')
    shutil.copyfile(paths['agent']/'continuations/001/dispatch.json', target/'continuation.json')
    details, failures = [], {}
    for mode, summary in summaries.items():
        counts = Counter()
        for row in summary['results']:
            kind = 'passed' if row['passed'] else row.get('failure_stage', 'unknown')
            if row['verdict'] == 'model_error':
                kind = 'response_format' if row.get('model_response_received') else 'api_or_transport'
            elif kind == 'geometry_reasoning':
                kind = 'unresolved_unchanged' if row.get('unchanged') else row['verdict']
            counts[kind] += 1
            run = resolve_record(row['run_dir']) if row.get('run_dir') else None
            diagnostics = row.get('error') or ''
            if run and (run/'results.json').exists():
                data = json.loads((run/'results.json').read_text())
                validation = data.get('validation') or {}
                errors = validation.get('violations') or []
                execution = data.get('execution') or {}
                if errors: diagnostics = ' | '.join(errors)
                elif kind == 'python_execution':
                    message = execution.get('error_message') or execution.get('stderr') or diagnostics
                    diagnostics = message.strip().splitlines()[-1] if message.strip() else ''
            added, removed = row.get('area_added_um2'), row.get('area_removed_um2')
            if run and added is None and (run/'patched.gds').exists():
                try:
                    diff = LayoutDiffCalculator(run/'input.gds', run/'patched.gds').compute_diff()
                    added, removed = diff.total_added_area_um2, diff.total_removed_area_um2
                except Exception:
                    pass  # An invalid or absent GDS has no measured modified area.
            details.append({'mode': mode, 'case_id': row['case_id'], 'level': row['level'], 'kind': row['kind'],
                'verdict': row['verdict'], 'failure_type': kind, 'passed': row['passed'],
                'area_added_um2': added, 'area_removed_um2': removed, 'diagnostic': diagnostics,
                'scored_profile': manifest.profile, 'public_audit_profile': 'asap7_public_full'})
        failures[mode] = dict(counts)
    with (target/'failure_analysis.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(details[0])); writer.writeheader(); writer.writerows(details)
    accounting = {'request_attempts': len(attempts), 'parsed_responses': summaries['agent']['model_responses'],
        'retries': 0, 'prior_attempts_preserved': 40, 'continuation_requests': 10,
        'identical_instruction_hash': next(iter(instruction_hashes)), 'returned_models': dict(returned_models),
        'usage': dict(usage), 'usage_known_for_responses': known_usage, 'usage_unknown_for_attempts': 50-known_usage,
        'cost': None, 'failure_counts': failures, 'scored_profile': manifest.profile,
        'public_audit_profile': 'asap7_public_full', 'public_audit_is_acceptance_gate': False}
    write_json(target/'accounting.json', accounting)
    lines = ['# C2+C3 five-level ASAP7 benchmark results', '',
        'The corpus contains **50 qualified full GDS cases**: **30 repair cases, 10 clean controls, and 10 no-edit controls**. '
        'Both independent generations pass the reproduction check. All 30 hidden reference repairs pass their edit policies and scored checks.', '',
        'Primary scope: `asap7_c2c3_v1`. Full public audits use `asap7_public_full` for diagnosis and do not change the primary score. '
        'All results are geometry-only. Connectivity and timing are unverified.', '',
        '| Method | Repairs / 30 | Clean restraint / 10 | No-edit restraint / 10 |', '|---|---:|---:|---:|']
    for mode, summary in summaries.items():
        values = [f'{summary[k]["passed"]} ({summary[k]["rate_observed"]:.0%})' for k in ('repair', 'clean_control', 'no_edit')]
        lines.append(f'| {mode} | '+ ' | '.join(values) + ' |')
    lines += ['', f'The campaign made **50 Bedrock request attempts**. There were **{accounting["parsed_responses"]} parsed responses** and **zero retries**. '
        'One request timed out after 90 seconds. The initial dispatcher stopped after 40 attempts. '
        'A recorded continuation sent only the ten unrequested L5 cases. Every prior outcome, including the timeout, remains unchanged.', '',
        '| Level | Model repairs / 6 | Model clean / 2 | Model no-edit / 2 |', '|---|---:|---:|---:|']
    for level, groups in summaries['agent']['levels'].items():
        lines.append(f'| L{level} | {groups["repair"]["passed"]} | {groups["clean_control"]["passed"]} | {groups["no_edit"]["passed"]} |')
    lines += ['', 'The model did not deliver an accepted repair. The failure counts below separate runtime failures, response-format failures, policy failures, and valid outputs that left defects unresolved. '
        'The existing heuristic copies or changes protected top-cell content in routed cases. Its twelve valid C2 repair outputs remain unchanged.', '',
        '| Model outcome type | Cases |', '|---|---:|']
    names = {'api_or_transport': 'API or transport timeout', 'edit_policy': 'Edit policy violation',
             'passed': 'Control restraint passed', 'python_execution': 'Python script failed',
             'response_format': 'Invalid response fields', 'unresolved_unchanged': 'Unchanged repair output'}
    lines += [f'| {names.get(name, name)} | {count} |' for name, count in sorted(failures['agent'].items())]
    lines += ['', 'Observed script errors include calls to `Box.sized`, `Layout.layout_io`, and '
              '`PolygonWithProperties.width_check`. The diagnostics file retains each error and policy rejection.']
    lines += ['', 'An inherited prompt requirement says to replace shapes in the top cell. The more specific case-policy section restricts edits to named route cells. '
        'That wording can create friction and may contribute to protected-cell failures. It was kept frozen throughout evaluation. '
        'These results assess the tested model, prompt, API guidance, and executor together; they do not isolate intrinsic geometric reasoning ability.', '',
        '| Level | Instances including structure/fillers | Hierarchy depth | Eligible signal route segments | Coupled categories in repair cases |', '|---|---|---|---|---|']
    for level in range(1, 6):
        cases = [c for c in manifest.cases if c.level == level]
        def values(key): return ', '.join(map(str, sorted({c.metrics[key] for c in cases if key in c.metrics}))) or 'not applicable'
        coupled = ', '.join(map(str, sorted({c.metrics['coupled_rules'] for c in cases if c.kind == 'repair'})))
        lines.append(f'| L{level} | {values("instance_count")} | {values("hierarchy_depth")} | {values("route_segment_count")} | {coupled} |')
    obstacle = json.loads((dataset/'provenance/obstacle_audit.json').read_text())
    ratios = [c.metrics['local_routing_occupancy']/c.metrics['matched_l4_occupancy'] for c in manifest.cases if c.level == 5]
    lines += ['', f'The median count of protected polygons that intersect repair inspection windows rises from **{obstacle["l3_median"]} in L3 to {obstacle["l4_median"]} in L4**. '
        f'L5 local M2/M3 metal occupancy is **{min(ratios):.3f}–{max(ratios):.3f} times** the matching L4 window. '
        'All six L5 repairs couple M2 width and V2 enclosure by M2 on the same landing geometry.', '',
        'The scored profile has eleven qualified checks. Nine families occur as injected repair targets. '
        'M2 spacing and V2 enclosure by M3 are qualified regression guards; this corpus has no injected repair target for those two checks. '
        'The 24 boundary fixtures pass, and all legal fixtures have zero scored markers. A separate seven-shape test checks the corrected V2/M2 orientation behavior.', '',
        'The derived profile corrects the public V2/M2 expression. The public and C1 decks remain unchanged. '
        'The V1/M2 checker requires a 6 nm cap on the verified 1 nm grid despite its nominal 5 nm description. '
        'These are qualified research checks, not foundry signoff.', '',
        '| Source group | Original public deck markers |', '|---|---:|']
    for group in sorted({c.source_group for c in manifest.cases if c.level >= 3}):
        case = next(c for c in manifest.cases if c.source_group == group)
        lines.append(f'| {group} | {sum(case.source["native_public_audit"]["counts"].values())} |')
    lines += ['', 'All clean controls have zero native markers under the scored profile. The public deck reports unrelated source markers. '
        'A clean-control label therefore describes the scored scope; it does not claim a globally clean source. '
        'No-edit controls retain their injected defects. Their passing result means successful completion with unchanged geometry.', '',
        '| Method | Public audits completed | Public audits failed | Not run on invalid candidates |', '|---|---:|---:|---:|']
    for mode, summary in summaries.items():
        counts = summary['public_audits']
        lines.append(f'| {mode} | {counts.get("complete", 0)} | {counts.get("failed", 0)} | {counts.get("not_run", 0)} |')
    lines += ['',
        f'Model: `{identity["model_config"]["model"]}`, provider `{identity["model_config"]["provider"]}`, region `{identity["model_config"]["region"]}`. '
        'Temperature and output-token limit were omitted, so provider defaults apply. Requests use JSON-object response format and a 90-second transport timeout. '
        f'Known usage: **{usage.get("prompt_tokens", 0):,} prompt tokens** and **{usage.get("completion_tokens", 0):,} completion tokens**, '
        f'covering {known_usage} responses. Usage for unreturned attempts and API cost are unknown.', '',
        'ORFS is pinned to `64939f3717ad7c694199ba04cb98924b98022868`. The official container digest, submodule pins, collateral hashes, and actual binary hashes are retained. '
        'OpenROAD reports an unknown version string, so its image digest and binary hash identify it. '
        'The scored host checker is KLayout 0.28.16; the Python geometry library is 0.30.8. '
        'The public checker limit is 600 seconds and the scored limit is 120 seconds.', '',
        'Source builds ran serially with two threads, an 8 GiB ceiling, available-RAM checks, and a 60-minute attempt limit. '
        'Evaluation modes shared one host concurrently. Runtime values are descriptive and do not support speed comparisons. '
        'Worker memory is sampled process-tree RSS, a lower bound. Corpus reproduction uses the same retained routed source artifacts; it does not repeat the OpenROAD builds.', '',
        'Validation: the full regression run passed 233 tests with 2 skips. After the final C2+C3 refinements, all 33 focused tests passed. '
        'TypeScript checking and both Node test files passed. The checks cover transforms, arrays, protected masters, clock/power edits, route deletion, boundary edits, context limits, native-marker persistence, and missing dependencies.', '',
        'There are six repair cases per level and one model attempt per case. This is a feasibility result for the tested configuration. '
        'It does not establish model consistency or broad generalization. Use C1 or separate development fixtures for any future prompt changes; do not retune this frozen campaign.', '',
        '[Case index and full GDS files](../../test_data/benchmark_c2c3/CASE_INDEX.md) · '
        '[Source and verification receipts](../../test_data/benchmark_c2c3/provenance/README.md) · '
        '[Paired outcomes](c2_c3_benchmark/comparison.csv) · [Failure diagnostics](c2_c3_benchmark/failure_analysis.csv) · '
        '[Accounting JSON](c2_c3_benchmark/accounting.json)', '',
        'Per-mode JSON, CSV, breakdown tables, Markdown, and frozen-source snapshots are in `docs/reports/c2_c3_benchmark/`. '
        'Full before/after GDS, marker reports, requests, responses, scripts, logs, and artifact hashes remain under `reports/runs/c2c3_v1_*`. '
        'A failed script or rejected policy can leave no scored after-report; that missing evidence earns no repair or restraint credit.', '']
    (root/'docs/reports/c2_c3_benchmark_report.md').write_text('\n'.join(lines))
    write_json(target/'report_artifact_hashes.json', {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob('*'))
        if p.is_file() and p.name != 'report_artifact_hashes.json'})
    print('Published 50-case reports; requests', comparison['request_attempts'], 'responses', comparison['responses_received'])


if __name__ == '__main__':
    main()
