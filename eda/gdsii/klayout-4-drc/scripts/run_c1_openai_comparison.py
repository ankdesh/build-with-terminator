"""Run the saved 100-case Bedrock setup with the environment's OpenAI model.

Create a separate workspace from the Bedrock campaign's frozen source. This
preserves the original prompt and execution rules without resetting live files.
Credentials stay in the environment. Each case receives at most one attempt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


FROZEN_RUNNER = '''from pathlib import Path
import hashlib,json,os,sys,subprocess
from klayout_drc.api_reference import verify_api_reference
from klayout_drc.benchmark.acceptance import verify_case
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.benchmark.manifest import BenchmarkManifestManager as M
from klayout_drc.profile import DRCProfileManager
from klayout_drc.repair_executor import sandbox_availability

workspace=Path(__file__).resolve().parent
settings=json.loads((workspace.parent/'setup.json').read_text())
baseline=Path(settings['baseline'])
output=Path(settings['output'])
campaign=json.loads((baseline/'campaign.json').read_text())
base=workspace/'test_data/benchmark_v1'
manifest=M.load(base/'manifest.json')
assert M.compute_sha256(base/'manifest.json')==campaign['manifest_sha256']
assert [c.case_id for c in manifest.cases]==campaign['case_ids']
assert len(manifest.cases)==100
assert BenchmarkEvaluator._source_digest()==campaign['source_sha256']
profile=DRCProfileManager().get_profile(campaign['profile'])
for case in manifest.cases: verify_case(case,base,profile)
reference=verify_api_reference()
baseline_metadata=json.loads(next((baseline/'runs').glob('*/api_reference_check.json')).read_text())
assert reference==baseline_metadata
config=json.loads(subprocess.check_output(['node',str(workspace/'harness/scripts/model-config.mjs')],text=True))
assert config['provider']=='openai' and config['model']
assert config['endpoint']=='https://api.openai.com/v1/chat/completions'
assert config['temperature']==campaign['temperature']
preflight={'cases':100,'dirty_cases':sum(c.expected_initial_violations>0 for c in manifest.cases),
 'clean_controls':sum(c.expected_initial_violations==0 for c in manifest.cases),
 'model_config':config,'reference':reference,'source_digest_matches_bedrock':True,
 'case_ids_match_bedrock':True,'deck_and_dataset_match_bedrock':True}
(workspace.parent/'preflight.json').write_text(json.dumps(preflight,indent=2))
print(json.dumps(preflight,indent=2),flush=True)
if '--prepare-only' in sys.argv: sys.exit(0)
if not os.environ.get('OPENAI_API_KEY'): raise ValueError('OPENAI_API_KEY is required')
blocked=sandbox_availability()
if blocked: raise ValueError(blocked)
if output.exists(): raise ValueError('Use a fresh output directory; no automatic repeats')
evaluator=BenchmarkEvaluator(base,output,profile_name=campaign['profile'])
metadata={'baseline_dir':str(baseline),'baseline_campaign_sha256':M.compute_sha256(baseline/'campaign.json'),
 'baseline_summary_sha256':M.compute_sha256(baseline/'summary.json'),
 'setup_dir':str(workspace.parent),'scope':'all_100_cases','reference':reference,
 'controlled_changes':['model','provider','endpoint','region'],
 'model_defaults':'Reasoning and sampling defaults are provider/model specific and are not overridden.'}
(output/'comparison_baseline.json').write_text(json.dumps(metadata,indent=2))
summary=evaluator.evaluate_batch(manifest.cases,mode='agent')
print(json.dumps({'output_dir':str(output),'cases':summary.total_cases,
 'verdict_counts':summary.to_dict()['verdict_counts']},indent=2),flush=True)
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    baseline, output, setup = [p.resolve() for p in (args.baseline,args.output,args.setup)]
    if output.exists():
        parser.error('Use a fresh campaign output directory')
    if not os.environ.get('OPENAI_MODEL'):
        parser.error('OPENAI_MODEL must be set in the environment')
    source = json.loads((baseline/'frozen_source.json').read_text())
    campaign = json.loads((baseline/'campaign.json').read_text())
    source_digest = hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    if source_digest != campaign['source_sha256'] or len(campaign['case_ids']) != 100:
        parser.error('Baseline must have a valid frozen source bundle and 100 cases')
    if digest(project/'test_data/benchmark_v1/manifest.json') != campaign['manifest_sha256']:
        parser.error('Live dataset differs from the saved Bedrock dataset')
    settings = {'baseline':str(baseline),'output':str(output),'source_sha256':source_digest}
    workspace = setup/'workspace'
    if setup.exists():
        if json.loads((setup/'setup.json').read_text()) != settings:
            parser.error('Prepared setup configuration differs')
    else:
        workspace.mkdir(parents=True)
        for name,content in source.items():
            target = workspace/name
            if not target.resolve().is_relative_to(workspace) or Path(name).is_absolute():
                raise ValueError('Snapshot source path escapes workspace')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content)
        shutil.copytree(project/'test_data/benchmark_v1',workspace/'test_data/benchmark_v1')
        shutil.copytree(project/'test_data/rules',workspace/'test_data/rules')
        (workspace/'.venv').symlink_to(project/'.venv',target_is_directory=True)
        (workspace/'harness/node_modules').symlink_to(project/'harness/node_modules',target_is_directory=True)
        (setup/'setup.json').write_text(json.dumps(settings,indent=2))
        (setup/'original_bedrock_hashes.json').write_text(json.dumps(
            {str(p.relative_to(baseline)):digest(p) for p in baseline.rglob('*') if p.is_file()},indent=2))
    for name,content in source.items():
        if (workspace/name).read_text() != content:
            raise ValueError(f'Prepared source changed: {name}')
    runner = workspace/'run_openai.py'
    runner.write_text(FROZEN_RUNNER)
    (setup/'comparison_runner.py').write_text(Path(__file__).read_text())
    env = os.environ.copy()
    env['KLAYOUT_DRC_MODEL_PROVIDER'] = 'openai'
    env['PYTHONPATH'] = str(workspace/'src')
    env['KLAYOUT_DRC_PYTHON'] = str(project/'.venv/bin/python')
    command = [str(project/'.venv/bin/python'),str(runner)]
    if args.prepare_only:
        command.append('--prepare-only')
    subprocess.run(command,cwd=workspace,env=env,check=True)


if __name__ == '__main__':
    main()
