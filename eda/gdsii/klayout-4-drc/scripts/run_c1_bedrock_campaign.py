"""Run all 100 C1 cases once with the environment's Bedrock model."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess

from klayout_drc.api_reference import verify_api_reference
from klayout_drc.benchmark.acceptance import verify_case
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.benchmark.manifest import BenchmarkManifestManager
from klayout_drc.profile import DRCProfileManager
from klayout_drc.repair_executor import sandbox_availability
from run_c1_bedrock_pilot import check_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-to', type=Path, required=True,
                        help='Preserved ten-case pilot; require its model, deck, and dataset')
    args = parser.parse_args()
    if not all(os.environ.get(name) for name in ('AWS_API_KEY', 'BEDROCK_MODEL')):
        parser.error('AWS_API_KEY and BEDROCK_MODEL must be set in the environment')
    os.environ['KLAYOUT_DRC_MODEL_PROVIDER'] = 'bedrock'
    project = Path(__file__).resolve().parents[1]
    root = project/'test_data/benchmark_v1'
    manifest = BenchmarkManifestManager.load(root/'manifest.json')
    try:
        if args.output.exists():
            raise ValueError('Use a new output directory; existing campaigns must be preserved')
        config = json.loads(subprocess.check_output(
            ['node', str(project/'harness/scripts/model-config.mjs')], text=True, timeout=10))
        check_comparison(root, manifest, args.compare_to, config)
        selected = list(manifest.cases)
        counts = Counter(case.rule_id for case in selected)
        if len(selected) != 100 or counts != Counter({rule: 20 for rule in manifest.rule_families}):
            raise ValueError('Require exactly 100 cases, twenty per rule family')
        profile = DRCProfileManager().get_profile('asap7_curated')
        for case in selected:
            verify_case(case, root, profile)
        reference = verify_api_reference()
        blocked = sandbox_availability()
        if blocked:
            raise ValueError(f'Candidate sandbox unavailable: {blocked}')
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    evaluator = BenchmarkEvaluator(root, args.output)
    (args.output/'comparison_baseline.json').write_text(json.dumps({
        'baseline_dir': str(args.compare_to.resolve()),
        'baseline_campaign_sha256': BenchmarkManifestManager.compute_sha256(args.compare_to/'campaign.json'),
        'baseline_summary_sha256': BenchmarkManifestManager.compute_sha256(args.compare_to/'summary.json'),
        'scope': 'all_100_cases',
        'initially_dirty': sum(case.expected_initial_violations > 0 for case in selected),
        'clean_controls': sum(case.expected_initial_violations == 0 for case in selected),
        'api_reference': reference,
    }, indent=2))
    (args.output/'campaign_runner.py').write_text(Path(__file__).read_text())
    (args.output/'comparison_helper.py').write_text((project/'scripts/run_c1_bedrock_pilot.py').read_text())
    print(json.dumps({'output_dir': str(args.output.resolve()), 'config': config,
                      'selected_cases': len(selected), 'rule_counts': dict(counts)}, indent=2), flush=True)
    summary = evaluator.evaluate_batch(selected, mode='agent')
    print(json.dumps({'output_dir': str(args.output.resolve()),
                      'total_cases': summary.total_cases,
                      'verdict_counts': summary.to_dict()['verdict_counts']}, indent=2))


if __name__ == '__main__':
    main()
