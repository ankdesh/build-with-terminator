"""Run ten C1 cases: one dirty input and one clean control per rule family."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.benchmark.types import DifficultyTier
from klayout_drc.profile import DRCProfileManager


def select_cases(manifest):
    selected = []
    for rule in manifest.rule_families:
        selected.append(next(case for case in manifest.cases
                             if case.rule_id == rule and case.tier == DifficultyTier.ISOLATED
                             and case.expected_initial_violations > 0))
        selected.append(next(case for case in manifest.cases
                             if case.rule_id == rule and case.tier == DifficultyTier.NEGATIVE
                             and case.expected_initial_violations == 0))
    if len(selected) != 10:
        raise ValueError('The pilot requires exactly five rule families')
    return selected


def check_comparison(root, manifest, baseline, config):
    """Require the original experiment's cases, model, deck, and dataset."""
    campaign = json.loads((baseline/'campaign.json').read_text())
    if config != campaign['model_config']:
        raise ValueError('Model/provider/region/temperature differs from the original pilot')
    if BenchmarkManifestManager.compute_sha256(root/'manifest.json') != campaign['manifest_sha256']:
        raise ValueError('Dataset manifest differs from the original pilot')
    if campaign['profile'] != 'asap7_curated':
        raise ValueError('Profile differs: original pilot must use asap7_curated')
    ids = campaign['case_ids']
    if len(ids) != 10 or len(set(ids)) != 10:
        raise ValueError('Original pilot must contain exactly ten distinct case IDs')
    by_id = {case.case_id: case for case in manifest.cases}
    selected = [by_id[case_id] for case_id in ids]
    if sum(case.expected_initial_violations == 0 for case in selected) != 5:
        raise ValueError('Original pilot must have five dirty cases and five clean controls')
    summary = json.loads((baseline/'summary.json').read_text())
    results = {result['case_id']: result for result in summary['results']}
    deck = DRCProfileManager().get_profile('asap7_curated').deck_path
    deck_hash = BenchmarkManifestManager.compute_sha256(deck)
    for case in selected:
        run_dir = Path(results[case.case_id]['run_dir'])
        audit = json.loads((run_dir/'run_manifest.json').read_text())
        if audit['hashes']['drc_script_sha256'] != deck_hash:
            raise ValueError('Checker deck differs from the original pilot')
        if audit['hashes']['input_gds_sha256'] != case.sha256:
            raise ValueError(f'Input geometry differs for {case.case_id}')
        if BenchmarkManifestManager.compute_sha256(root/case.gds_rel_path) != case.sha256:
            raise ValueError(f'Dataset geometry hash mismatch for {case.case_id}')
        if not (run_dir/'model_response.json').exists():
            raise ValueError(f'Original pilot has no completed response for {case.case_id}')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-to', type=Path, help='Original ten-case pilot; require matched experiment settings')
    args = parser.parse_args()
    if not all(os.environ.get(name) for name in ('AWS_API_KEY', 'BEDROCK_MODEL')):
        parser.error('AWS_API_KEY and BEDROCK_MODEL must be set in the environment')
    os.environ['KLAYOUT_DRC_MODEL_PROVIDER'] = 'bedrock'
    root = Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    manifest = BenchmarkManifestManager.load(root/'manifest.json')
    try:
        if args.compare_to:
            if args.output.resolve() == args.compare_to.resolve():
                raise ValueError('Use a new output directory; preserve the original pilot')
            script = root.parents[1]/'harness/scripts/model-config.mjs'
            config = json.loads(subprocess.check_output(['node', str(script)], text=True, timeout=10))
            selected = check_comparison(root, manifest, args.compare_to, config)
        else:
            selected = select_cases(manifest)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    evaluator = BenchmarkEvaluator(root, args.output)
    if args.compare_to:
        (args.output/'comparison_baseline.json').write_text(json.dumps({
            'baseline_dir': str(args.compare_to.resolve()),
            'baseline_campaign_sha256': BenchmarkManifestManager.compute_sha256(args.compare_to/'campaign.json'),
            'baseline_summary_sha256': BenchmarkManifestManager.compute_sha256(args.compare_to/'summary.json'),
        }, indent=2))
    (args.output/'pilot_runner.py').write_text(Path(__file__).read_text())
    summary = evaluator.evaluate_batch(selected, mode='agent')
    print(json.dumps({'output_dir': str(args.output.resolve()),
                      'total_cases': summary.total_cases,
                      'verdict_counts': summary.to_dict()['verdict_counts']}, indent=2))


if __name__ == '__main__':
    main()
