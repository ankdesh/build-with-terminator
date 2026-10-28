"""Dispatch only never-requested cases after a campaign service interruption.

Keep all attempted outcomes, prompts, model settings, scoring code, and inputs.
Archive the prior undispatched records. Never retry an attempted request.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from klayout_drc.benchmark.acceptance import run_checker
from klayout_drc.benchmark.c2c3.contracts import sha256, write_json
from klayout_drc.benchmark.c2c3.evaluator import (
    verify_dataset, checker_identity, score_case, summarize, export_report,
)
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.profile import DRCProfileManager
from klayout_drc.run_manifest import RunSpec
from klayout_drc.single_shot import SingleShotOrchestrator


def main():
    os.environ['KLAYOUT_DRC_MODEL_PROVIDER'] = 'bedrock'
    os.environ.setdefault('BEDROCK_MODEL', 'qwen.qwen3-coder-next')
    root = Path('test_data/benchmark_c2c3').resolve()
    output = Path('reports/runs/c2c3_v1_agent').resolve()
    manifest = verify_dataset(root)
    identity = json.loads((output/'campaign.json').read_text())
    frozen = BenchmarkEvaluator._source_bundle()
    assert manifest.complete and sha256(root/'manifest.json') == identity['manifest_sha256']
    assert hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest() == identity['source_sha256']
    assert checker_identity() == identity['checker']
    config = json.loads(subprocess.check_output(['node', 'harness/scripts/model-config.mjs'], text=True))
    assert config == identity['model_config']
    prior = json.loads((output/'summary.json').read_text())
    requests = list((output/'runs').glob('*/model_attempt.json'))
    assert len(requests) == prior['model_requests'] == 40
    pending = []
    for case in manifest.cases:
        checkpoint = output/'cases'/f'{case.case_id}.json'
        row = json.loads(checkpoint.read_text())
        if row['verdict'] != 'blocked': continue
        assert not row.get('model_request_attempted') and row.get('run_dir') is None
        assert not checkpoint.with_suffix('.attempt.json').exists()
        pending.append(case)
    assert len(pending) == 10 and all(case.level == 5 for case in pending)
    archive = output/'continuations/001'
    assert not archive.exists(), 'A continuation cannot be replayed'
    lock = output/'.campaign.lock'
    with lock.open('x'): pass
    started = time.monotonic()
    try:
        archive.mkdir(parents=True)
        for name in ('summary.json', 'artifact_hashes.json', 'campaign.json'):
            shutil.copyfile(output/name, archive/name)
        shutil.copyfile(__file__, archive/'dispatcher.py')
        write_json(archive/'dispatch.json', {
            'reason': 'The original dispatcher stopped after one 90-second service timeout.',
            'policy': 'One attempt per unrequested case. Preserve every earlier attempt. No retries or patch feedback.',
            'prior_requests': 40, 'remaining_request_budget': 10,
            'case_ids': [c.case_id for c in pending], 'manifest_sha256': identity['manifest_sha256'],
            'source_sha256': identity['source_sha256'], 'dispatcher_sha256': sha256(__file__),
            'model_config': config, 'started_unix': time.time(),
        })
        profile = DRCProfileManager().get_profile(manifest.profile)
        for case in pending:
            checkpoint = output/'cases'/f'{case.case_id}.json'
            shutil.copyfile(checkpoint, archive/checkpoint.name)
            assert len(list((output/'runs').glob('*/model_attempt.json'))) < 50
            with checkpoint.with_suffix('.attempt.json').open('x') as handle:
                json.dump({'case_id': case.case_id, 'mode': 'agent', 'continuation': '001', 'started_unix': time.time()}, handle)
            case_started = time.monotonic()
            spec = RunSpec(case_name=case.case_id, input_gds=root/case.gds, drc_script=profile.deck_path,
                profile_name=profile.name, candidate_mode='agent', output_root=output/'runs',
                expected_markers=case.evidence['input_markers'], edit_policy=case.edit_policy)
            orchestrator = SingleShotOrchestrator(spec)
            summary = orchestrator.run()
            run = orchestrator.paths.run_dir
            row = score_case(case, summary, root, run)
            row.update(wall_seconds=time.monotonic()-case_started, continuation='001',
                       model_request_attempted=(run/'model_attempt.json').exists(),
                       model_response_received=(run/'model_response.json').exists())
            request = run/'model_request.json'
            row['model_request_bytes'] = request.stat().st_size if request.exists() else None
            generation = run/'generation_manifest.json'
            if generation.exists(): row['usage'] = json.loads(generation.read_text()).get('usage')
            if summary.execution_result.status == 'success' and summary.validation_result and summary.validation_result.is_valid:
                try:
                    audit = run/'public_after.lyrdb'
                    data = run_checker(orchestrator.paths.patched_gds, DRCProfileManager().get_profile('asap7_public_full'), audit)
                    row['public_audit'] = {'status': 'complete', 'counts': data.rule_summary,
                                           'sha256': sha256(audit), 'acceptance_gate': False}
                except Exception as exc:
                    row['public_audit'] = {'status': 'failed', 'error': str(exc), 'acceptance_gate': False}
            write_json(checkpoint, row)
            rows = [json.loads((output/'cases'/f'{c.case_id}.json').read_text()) for c in manifest.cases]
            export_report(output, summarize(manifest, 'agent', rows))
            print(f'continuation {case.case_id}: {row["verdict"]}', flush=True)
        rows = [json.loads((output/'cases'/f'{c.case_id}.json').read_text()) for c in manifest.cases]
        result = summarize(manifest, 'agent', rows)
        result['continuation'] = {'journal': 'continuations/001/dispatch.json', 'prior_requests': 40,
                                  'additional_requests': result['model_requests']-40,
                                  'preserved_failed_case': 'l4_g1_c4', 'retries': 0}
        result['this_invocation_wall_seconds'] = time.monotonic()-started
        result['prior_invocation_wall_seconds'] = prior['this_invocation_wall_seconds']
        result['summed_case_seconds'] = sum(r.get('wall_seconds', 0.) for r in rows)
        assert result['model_requests'] <= 50
        export_report(output, result)
        write_json(output/'artifact_hashes.json', {str(p.relative_to(output)): sha256(p)
            for p in sorted(output.rglob('*')) if p.is_file() and p != output/'artifact_hashes.json' and p != lock})
        print('REQUESTS', result['model_requests'], 'RESPONSES', result['model_responses'], flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
