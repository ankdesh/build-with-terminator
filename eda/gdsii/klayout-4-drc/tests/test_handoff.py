"""Transfer and dispatch checks. No provider request is made by these tests."""
import io
import os
import json
from pathlib import Path
import tarfile
from unittest.mock import Mock
import pytest

from klayout_drc.handoff import archive
from klayout_drc.handoff.config import load
from klayout_drc.handoff.cli import parser, dispatch
from klayout_drc.handoff.reporting import saved_report


@pytest.fixture(autouse=True)
def restore_process_environment():
    original = os.environ.copy()
    affinity = os.sched_getaffinity(0)
    yield
    os.environ.clear(); os.environ.update(original)
    os.sched_setaffinity(0, affinity)


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path/'old-checkout'; root.mkdir()
    for name, content in {'test_data/benchmark_v1/manifest.json': '{"cases":[]}',
                          'reports/runs/old/summary.json': '{"results":[],"clean_success_rate":0.25}',
                          'docs/reports/old.pdf': 'PDF bytes',
                          'output/slides/build/source.mjs': 'original source',
                          'output/slides/final.pptx': 'PPT bytes',
                          'output/c2c3/toolchain/orfs/excluded': 'checkout',
                          'output/c2c3/toolchain/builds/excluded': 'ASIC build',
                          'output/c2c3/secondary/.staging/unfinished.gds': 'partial',
                          'config/local.toml': 'private machine information'}.items():
        path = root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    return root


def test_config_precedence_and_cwd(tmp_path, monkeypatch):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/local.toml').write_text('[paths]\nwork="custom"\n[resources]\nworkers=2\n')
    monkeypatch.chdir('/')
    config = load(root=tmp_path, overrides={'resources.workers':3})
    assert config.path('work') == tmp_path/'custom'
    assert config.values['resources']['workers'] == 3
    assert config.path('data') == tmp_path/'test_data'
    with pytest.raises(ValueError,match='1 to 4'): load(root=tmp_path,overrides={'resources.workers':5})
    (tmp_path/'config/local.toml').write_text('[credentials]\nkey="do not store"')
    with pytest.raises(ValueError,match='Unknown'): load(root=tmp_path)


def test_archive_transfer_and_resolver(evidence, tmp_path):
    target = tmp_path/'archives'
    result = archive.create(evidence,target,'dated',move_reports=True)
    snap = target/'dated'
    assert result['status'] == 'verified'
    assert not (evidence/'docs/reports/old.pdf').exists()
    assert (evidence/'reports/runs/old/summary.json').exists()
    assert (evidence/'test_data/benchmark_v1/manifest.json').exists()
    resolver = archive.Resolver(snap)
    assert resolver.resolve(str(evidence/'docs/reports/old.pdf')).read_text() == 'PDF bytes'
    assert not (snap/'root/config/local.toml').exists()
    assert not (snap/'root/output/c2c3/toolchain/orfs').exists()
    assert (snap/'root/output/c2c3/secondary/.staging/unfinished.gds').exists()
    with pytest.raises(FileExistsError): archive.create(evidence,target,'dated')
    bundle = tmp_path/'transfer.tar.gz'
    archive.pack(snap,bundle)
    restored = tmp_path/'different/repository/archives/dated'
    archive.restore(bundle,restored)
    assert archive.verify(restored)['manifest_sha256'] == result['manifest_sha256']
    assert archive.Resolver(restored).resolve(str(evidence/'docs/reports/old.pdf')).read_text() == 'PDF bytes'
    with pytest.raises(FileExistsError): archive.restore(bundle,restored)
    (restored/'root/docs/reports/old.pdf').write_text('changed')
    with pytest.raises(ValueError,match='changed'): archive.verify(restored)


def test_interruption_preserves_originals(evidence,tmp_path,monkeypatch):
    original = archive.shutil.copy2
    def interrupt(source,target):
        original(source,target)
        raise KeyboardInterrupt()
    monkeypatch.setattr(archive.shutil,'copy2',interrupt)
    with pytest.raises(KeyboardInterrupt): archive.create(evidence,tmp_path/'archive','failed',True)
    assert (evidence/'docs/reports/old.pdf').read_text() == 'PDF bytes'
    assert not (tmp_path/'archive/failed').exists()


def test_verify_failure_cannot_move_originals(evidence,tmp_path,monkeypatch):
    monkeypatch.setattr(archive,'verify',Mock(side_effect=ValueError('bad copy')))
    with pytest.raises(ValueError,match='bad copy'): archive.create(evidence,tmp_path/'archive','bad',True)
    assert (evidence/'docs/reports/old.pdf').exists()


@pytest.mark.parametrize('name,kind', [('../escape','file'),('/absolute','file'),('root/link','symlink')])
def test_unsafe_bundles_rejected(tmp_path,name,kind):
    bundle=tmp_path/'bad.tar.gz'
    with tarfile.open(bundle,'w:gz') as tar:
        item=tarfile.TarInfo(name)
        if kind=='symlink': item.type=tarfile.SYMTYPE; item.linkname='/etc/passwd'; tar.addfile(item)
        else: item.size=1; tar.addfile(item,io.BytesIO(b'x'))
    with pytest.raises(ValueError): archive.restore(bundle,tmp_path/'restore',archive.sha(bundle))
    assert not (tmp_path/'restore').exists()


def test_saved_results_never_rescored(evidence,tmp_path):
    output=tmp_path/'reports'; output.mkdir()
    campaign=evidence/'reports/runs/old'
    original=(campaign/'summary.json').read_bytes()
    saved_report([campaign],output)
    assert (output/'old/summary.json').read_bytes()==original
    assert json.loads((output/'comparison.json').read_text())['recorded_outcomes']['old']['clean_success_rate']==0.25


@pytest.mark.parametrize('options,match',[
    ('--suite c2c3 --mode agent --provider openai','Bedrock'),
    ('--suite c2c3 --limit 1','filters'),
    ('--suite c2c3 --workers 2','serial'),
    ('--suite c1 --provider openai','explicit'),
    ('--suite c1 --mode agent','explicit'),
    ('--suite c1 --mode script_file','candidate-script'),
    ('--suite ab --allow-incomplete','only supported'),
])
def test_unsupported_evaluation_options(options,match):
    with pytest.raises(ValueError,match=match): dispatch(parser().parse_args(['evaluate',*options.split(),'--dry-run']))


def test_c1_provider_dispatch_without_network(tmp_path,monkeypatch):
    from klayout_drc.handoff import evaluation
    from klayout_drc.handoff import environment
    from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
    from klayout_drc.repair_executor import sandbox_availability
    from klayout_drc.handoff.config import ROOT
    monkeypatch.setattr(evaluation,'apply_environment',lambda s:None)
    for key in ('KLAYOUT_DRC_MODEL_PROVIDER','BEDROCK_MODEL'):
        monkeypatch.setenv(key, __import__('os').environ.get(key, ''))
    sandbox=Mock(return_value=None); sandbox.cache_clear=Mock()
    monkeypatch.setattr('klayout_drc.repair_executor.sandbox_availability',sandbox)
    monkeypatch.setattr(environment,'doctor',lambda s:{'status':'ready','checks':[]})
    def fake(self,cases,mode,candidate_script):
        assert mode=='agent'
        assert __import__('os').environ['KLAYOUT_DRC_MODEL_PROVIDER']=='bedrock'
        archive.write_json(self.output_dir/'summary.json',{'results':[]})
        return Mock(to_dict=lambda:{'results':[]})
    monkeypatch.setattr(BenchmarkEvaluator,'evaluate_batch',fake)
    args=parser().parse_args(['evaluate','--suite','c1','--mode','agent','--provider','bedrock','--model','mock-model','--limit','1','--output',str(tmp_path/'run')])
    result=evaluation.evaluate(load(root=ROOT),args)
    assert result['status']=='complete'
    assert (tmp_path/'run/handoff_run.json').exists()
    with pytest.raises(FileExistsError): evaluation.evaluate(load(root=ROOT),args)


def test_missing_tool_fails_closed(tmp_path):
    from klayout_drc.handoff.evaluation import apply_environment
    settings=load(root=tmp_path); settings.values['tools']['bwrap']='nonexistent-bwrap'
    with pytest.raises(ValueError,match='bwrap'): apply_environment(settings)


def test_no_model_import_in_setup_dryrun():
    result=dispatch(parser().parse_args(['setup','--dry-run']))
    assert all('run-flow' not in ' '.join(s['command']) for s in result['steps'])


def test_repeated_tool_resolution_does_not_make_self_links(tmp_path, monkeypatch):
    from klayout_drc.handoff.evaluation import apply_environment
    monkeypatch.setenv('PATH', __import__('os').environ['PATH'])
    settings=load(root=tmp_path)
    apply_environment(settings); apply_environment(settings)
    for key in ('node','klayout','bwrap'):
        assert (settings.path('work')/'tools'/key).resolve().is_file()


def test_bootstrap_without_site_packages():
    import subprocess, sys
    from klayout_drc.handoff.config import ROOT
    result = subprocess.run([sys.executable, '-S', '-m', 'klayout_drc.handoff.cli',
                             'setup', '--python-only', '--dry-run'],
                            env={**os.environ, 'PYTHONPATH':str(ROOT/'src')},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'dry-run'


def test_harness_install_failure_restores_source_lock(tmp_path,monkeypatch):
    import hashlib, subprocess
    from klayout_drc.handoff import environment
    settings=load(root=tmp_path)
    harness=settings.path('harness'); harness.mkdir(parents=True)
    (tmp_path/'config').mkdir()
    source=harness/'pnpm-lock.yaml'; source.write_bytes(b'original source lock')
    install=tmp_path/'config/harness-pnpm-lock.yaml'; install.write_bytes(b'retained install lock')
    pins={'node':'22.23.2','pnpm':'11.7.0', 'harness_source_lock_sha256':archive.sha(source),
          'harness_install_lock_sha256':archive.sha(install)}
    monkeypatch.setattr(environment,'lock',lambda s:pins)
    monkeypatch.setattr(environment,'version',lambda cmd,*a:'v22.23.2' if cmd==settings.tool('node') else '11.7.0')
    monkeypatch.setattr(environment,'harness_check',lambda s:True)
    def fake(command,**kwargs):
        if command[:2]==[settings.tool('pnpm'),'install']:
            assert source.read_bytes()==install.read_bytes()
            raise subprocess.CalledProcessError(1,command)
    monkeypatch.setattr(environment,'run',fake)
    with pytest.raises(subprocess.CalledProcessError): environment.setup(settings)
    assert source.read_bytes()==b'original source lock'


def test_archive_root_cannot_capture_itself(evidence):
    with pytest.raises(ValueError, match='captured'):
        archive.create(evidence,evidence/'reports/archive','recursive')


def test_snapshot_output_guard_resolves_symlink(evidence,tmp_path):
    archive.create(evidence,tmp_path/'archives','frozen')
    snapshot=tmp_path/'archives/frozen'
    link=tmp_path/'alias'; link.symlink_to(snapshot/'root',target_is_directory=True)
    with pytest.raises(ValueError,match='immutable'): archive.new_output(link/'new-run')
    with pytest.raises(ValueError,match='immutable'): archive.pack(snapshot,snapshot/'bundle.tar.gz')
    bundle=tmp_path/'guard.tar.gz'; archive.pack(snapshot,bundle)
    with pytest.raises(ValueError,match='immutable'): archive.restore(bundle,snapshot/'root/restore')


def test_setup_forwards_resolved_settings_to_doctor(tmp_path,monkeypatch):
    from klayout_drc.handoff import environment
    settings=load(root=tmp_path,overrides={'paths.harness':'custom-harness','resources.workers':2})
    monkeypatch.setattr(environment,'lock',lambda s:{})
    commands=[]
    monkeypatch.setattr(environment,'run',lambda command,**kw:commands.append(command))
    environment.setup(settings,python_only=True)
    command=commands[-1]
    assert command[command.index('--harness-root')+1]==str(tmp_path/'custom-harness')
    assert command[command.index('--workers')+1]=='2'


@pytest.mark.parametrize('provider,key',[('openai','OPENAI_TEMPERATURE'),('bedrock','BEDROCK_TEMPERATURE')])
def test_provider_temperature_dispatch_without_network(provider,key):
    from klayout_drc.handoff.evaluation import provider_environment
    provider_environment(provider,'mock-model',None,0.)
    assert os.environ[key]=='0.0'
    with pytest.raises(ValueError,match='finite'): provider_environment(provider,None,None,float('nan'))


def test_configured_external_data_and_new_run_evidence_are_archived(evidence,tmp_path):
    data=tmp_path/'external-data'; data.mkdir(); (data/'case.gds').write_bytes(b'case')
    work=tmp_path/'external-work'; (work/'runs/new').mkdir(parents=True)
    (work/'runs/new/summary.json').write_text('{"results":[]}')
    archive.create(evidence,tmp_path/'snapshots','configured',data_root=data,work_root=work)
    snap=tmp_path/'snapshots/configured'; resolver=archive.Resolver(snap)
    assert resolver.resolve(data/'case.gds').read_bytes()==b'case'
    assert resolver.resolve(work/'runs/new/summary.json').is_file()
    restored=tmp_path/'restored-data'; archive.restore_datasets(snap,restored)
    assert (restored/'case.gds').read_bytes()==b'case'


def test_default_fresh_runs_are_in_later_snapshots(evidence,tmp_path):
    run=evidence/'work/runs/new/summary.json'; run.parent.mkdir(parents=True); run.write_text('{}')
    archive.create(evidence,tmp_path/'snapshots','later')
    assert archive.Resolver(tmp_path/'snapshots/later').resolve(run).read_text()=='{}'


def test_fresh_report_does_not_default_to_historical_snapshot(evidence,tmp_path):
    from klayout_drc.handoff.reporting import report
    archive.create(evidence,evidence/'archives','2026-10-28')
    fresh=evidence/'work/runs/new'; fresh.mkdir(parents=True)
    (fresh/'summary.json').write_text('{"results":[{"case_id":"new","verdict":"model_error"}]}')
    settings=load(root=tmp_path); settings.root=evidence
    args=parser().parse_args(['report','--campaign',str(fresh),'--output',str(tmp_path/'new-report')])
    result=report(settings,args)
    assert result['status']=='complete'
    assert (tmp_path/'new-report/new/summary.json').read_bytes()==(fresh/'summary.json').read_bytes()
    assert json.loads((tmp_path/'new-report/rebuild.json').read_text())['source_snapshot'] is None


def test_archive_alias_cannot_escape_report_workspace(evidence,tmp_path):
    archive.create(evidence,tmp_path/'archives','alias')
    snapshot=tmp_path/'archives/alias'
    path=snapshot/'manifest.json'; manifest=json.loads(path.read_text())
    manifest['path_aliases']=[{'original':'/old/data','prefix':'../outside'}]
    archive.write_json(path,manifest)
    with pytest.raises(ValueError,match='Unsafe'): archive.Resolver(snapshot)


@pytest.mark.parametrize('suite,cases', [
    ('ab', ['a_dbu_1_high_res','a_e_1_via_enclosure']),
    ('c1', ['m1_w1_iso_01','m1_w1_iso_02']),
])
def test_case_filters_can_be_combined_with_a_limit(suite,cases):
    result=dispatch(parser().parse_args(['evaluate','--suite',suite,'--case',cases[0],
        '--case',cases[1],'--limit','1','--dry-run']))
    assert len(result['case_ids'])==1
    assert result['case_ids'][0] in cases
