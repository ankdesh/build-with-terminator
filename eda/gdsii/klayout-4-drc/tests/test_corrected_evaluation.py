"""Regression tests for the C1 review findings. No live model requests."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import klayout.db as db
import pytest
from klayout_drc.benchmark.scorer import BenchmarkScorer as Scorer
from klayout_drc.benchmark.types import BenchmarkVerdict as V, BenchmarkCaseSpec, DifficultyTier, EvaluationResult
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.layout_diff import LayoutDiffCalculator
from klayout_drc.validator import LayoutValidator
from klayout_drc.repair_executor import ExecutionResult, RepairExecutor, sandbox_availability
from klayout_drc.run_reporter import RunReporter
from klayout_drc.marker_comparison import compare_markers
from klayout_drc.marker_geometry import BoxMarker
from klayout_drc.parser import DRCReportData, RuleCategory, ViolationItem, ViolationGeometry
from klayout_drc.knowledge_loader import KnowledgeLoader
from klayout_drc.drc_context import DRCContextProcessor
from klayout_drc.profile import DRCProfileManager
from klayout_drc.rule_catalog import DRCRuleCatalog


@pytest.mark.parametrize('status,expected', [('invalid_patch', V.INVALID_PATCH), ('blocked',V.BLOCKED),
    ('model_error',V.MODEL_ERROR),('drc_error',V.CHECKER_ERROR),('timeout',V.EXECUTION_ERROR)])
def test_failure_gates_precede_counts(status,expected):
    assert Scorer.classify_verdict({'M1.W.1':1},None,pipeline_verdict=status)==expected
    assert Scorer.classify_verdict({}, {},pipeline_verdict=status)==expected


def test_missing_after_and_same_rule_regression():
    assert Scorer.classify_verdict({'M1.W.1':1},None)==V.CHECKER_ERROR
    assert Scorer.classify_verdict({'M1.W.1':5,'M2.W.1':1},{'M1.W.1':1,'M2.W.1':2})==V.REGRESSION
    assert Scorer.classify_verdict({}, {},changed=False)==V.CLEAN_UNCHANGED
    assert Scorer.classify_verdict({}, {},changed=True)==V.UNNECESSARY_EDIT


@pytest.mark.parametrize('mode',['agent','script_file','heuristic'])
def test_negative_case_honors_mode(mode,tmp_path,monkeypatch):
    import klayout_drc.benchmark.evaluator as module
    case=BenchmarkCaseSpec('clean','M1.W.1',DifficultyTier.NEGATIVE,'clean.gds','x',0,[],'clean',
                           acceptance={'observed_counts':{},'observed_markers':[],'preservation':{}})
    monkeypatch.setattr(module,'verify_case',lambda *args: None)
    summary=SimpleNamespace(violations_before={},violations_after=None,total_before=0,total_after=None,
        verdict='model_error',validation_result=None,diff_report=None,validation_level='not_run',error_message='test model failure')
    seen=[]
    class Fake:
        def __init__(self,spec,*args):
            seen.append(spec.candidate_mode);self.paths=SimpleNamespace(run_dir=tmp_path)
        def run(self):return summary
    monkeypatch.setattr(module,'SingleShotOrchestrator',Fake)
    result=BenchmarkEvaluator(tmp_path,tmp_path/'out').evaluate_case(case,mode)
    assert seen==[mode]
    assert result.verdict==V.MODEL_ERROR and result.final_total is None
    assert result.actual_mode==mode


def test_rejected_summary_cannot_become_success(tmp_path,monkeypatch):
    import klayout_drc.benchmark.evaluator as module
    case=BenchmarkCaseSpec('dirty','M1.W.1',DifficultyTier.ISOLATED,'dirty.gds','x',1,['M1.W.1'],'dirty',
        acceptance={'observed_counts':{'M1.W.1':1},'observed_markers':[],'preservation':{}})
    monkeypatch.setattr(module,'verify_case',lambda *args:None)
    invalid=SimpleNamespace(is_valid=False,to_dict=lambda:{'is_valid':False})
    summary=SimpleNamespace(violations_before={'M1.W.1':1},violations_after=None,total_before=1,total_after=None,
        verdict='invalid_patch',validation_result=invalid,diff_report=None,validation_level='not_run',error_message=None)
    fake=Mock(return_value=SimpleNamespace(paths=SimpleNamespace(run_dir=tmp_path),run=lambda:summary))
    monkeypatch.setattr(module,'SingleShotOrchestrator',fake)
    result=BenchmarkEvaluator(tmp_path,tmp_path/'out').evaluate_case(case,'script_file')
    assert result.verdict==V.INVALID_PATCH
    assert result.to_dict()['final_violations'] is None
    assert result.to_dict()['final_total'] is None


def test_recursive_diff_and_master_contents(tmp_path):
    l=db.Layout();l.dbu=.00025;t=l.create_cell('TOP');c=l.create_cell('MASTER');idx=l.layer(19,0)
    c.shapes(idx).insert(db.Box(0,0,100,100));t.insert(db.CellInstArray(c.cell_index(),db.Trans(1000,0)))
    a,b=tmp_path/'a.gds',tmp_path/'b.gds';l.write(str(a))
    assert LayoutValidator(a).validate().is_valid
    c.shapes(idx).insert(db.Box(25,25,30,30));l.write(str(b))
    assert not LayoutValidator(b,a,protected_cells={'MASTER'}).validate().is_valid
    # A contained added box has no physical XOR; remove material inside the same bbox.
    c.shapes(idx).clear();c.shapes(idx).insert(db.Region(db.Box(0,0,100,100))-db.Region(db.Box(25,25,30,30)))
    l.write(str(b))
    assert LayoutDiffCalculator(a,b).compute_diff().total_removed_area_um2>0
    assert not LayoutValidator(b,a,protected_cells={'MASTER'}).validate().is_valid


def test_component_preservation(tmp_path):
    l=db.Layout();l.dbu=.00025;t=l.create_cell('TOP');idx=l.layer(19,0)
    t.shapes(idx).insert(db.Box(0,0,100,100));p=tmp_path/'out.gds';l.write(str(p))
    v=LayoutValidator(p,preservation={'component_counts':{'19/0':2}}).validate()
    assert not v.is_valid and 'Component preservation' in v.violations[0]


def report(boxes):
    return DRCReportData(Path('test.lyrdb'),[RuleCategory('M1.W.1','',[
        ViolationItem(i,'M1.W.1','TOP',[ViolationGeometry('box',str(b),marker=BoxMarker(*b))]) for i,b in enumerate(boxes)])])


def test_marker_regression_with_unchanged_counts():
    comparison=compare_markers(report([(0,0,.01,.1)]),report([(1,1,1.01,1.1)]),.00025)
    assert comparison['introduced']==1 and comparison['resolved']==1
    assert Scorer.classify_verdict({'M1.W.1':1},{'M1.W.1':1},marker_comparison=comparison)==V.REGRESSION


def test_marker_tolerance_and_ambiguity():
    assert compare_markers(report([(0,0,.01,.1)]),report([(.00025,0,.01025,.1)]),.00025)['persisted']==1
    comparison=compare_markers(report([(0,0,.01,.1)]),report([(.0001,0,.0101,.1),(.0002,0,.0102,.1)]),.00025)
    assert comparison['ambiguous']>0


def test_active_profile_context():
    profile=DRCProfileManager().get_profile('asap7_curated')
    text=KnowledgeLoader(profile_name=profile.name).format_as_text()
    assert 'M1=19/0' in text and 'V1=21/0' in text
    assert 'layout.layer(18, 0)' not in text
    context=DRCContextProcessor(profile.deck_path).format_as_text(['M1.A.1','M1.S.1','V1.W.1'])
    assert '0.000504 um2' in context and '&gt;' not in context
    catalog=DRCRuleCatalog();catalog.bind_deck_provenance(DRCProfileManager().get_profile('asap7_public_full').deck_path)
    assert len(catalog.get_rule_by_id('V1.M1.EN.1').source_branches)==2


def test_empty_summary_exports(tmp_path):
    summary=Scorer.aggregate('1.1.0','agent',[],0.)
    Scorer.export_json(summary,tmp_path/'summary.json');Scorer.export_csv(summary,tmp_path/'summary.csv')
    assert summary.clean_success_rate==0 and '0/0' in Scorer.export_markdown(summary)
    assert json.loads((tmp_path/'summary.json').read_text())['dirty_cases']==0


def test_worker_blocked_is_explicit(tmp_path,monkeypatch):
    import klayout_drc.repair_executor as module
    script=tmp_path/'script.py';script.write_text('pass')
    monkeypatch.setattr(module,'sandbox_availability',lambda:'namespace unavailable')
    result=RepairExecutor(script,tmp_path/'in.gds',tmp_path/'out.gds').execute()
    assert result.status=='blocked' and result.output_gds is None


@pytest.mark.integration_sandbox
def test_worker_has_no_secrets_and_readonly_input(tmp_path,monkeypatch):
    if sandbox_availability():pytest.skip(sandbox_availability())
    source=tmp_path/'in.gds';source.write_bytes(b'immutable')
    secret=tmp_path/'secret';secret.write_text('private')
    monkeypatch.setenv('OPENAI_API_KEY','sentinel')
    script=tmp_path/'script.py'
    script.write_text('''import os,sys,socket
from pathlib import Path
assert 'OPENAI_API_KEY' not in os.environ
assert not Path('''+repr(str(secret))+''').exists()
try:
    Path(sys.argv[1]).write_bytes(b'changed')
except OSError:
    pass
else:
    raise AssertionError('input is writable')
try:
    socket.create_connection(('1.1.1.1',443),timeout=.1)
except OSError:
    pass
else:
    raise AssertionError('network is enabled')
Path(sys.argv[2]).write_bytes(b'output')
''')
    result=RepairExecutor(script,source,tmp_path/'out.gds').execute()
    assert result.status=='success',result
    assert source.read_bytes()==b'immutable'


def test_hash_scope_and_expectation_gates_before_synthesis(tmp_path,monkeypatch):
    from klayout_drc.benchmark.manifest import BenchmarkManifestManager
    root=Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    case=BenchmarkManifestManager.load(root/'manifest.json').cases[0]
    import klayout_drc.benchmark.evaluator as module
    synth=Mock(side_effect=AssertionError('synthesis must not start'))
    monkeypatch.setattr(module,'SingleShotOrchestrator',synth)
    evaluator=BenchmarkEvaluator(root,tmp_path/'eval')
    for broken in [replace(case,sha256='0'*64),replace(case,expected_initial_violations=999),
                   replace(case,acceptance={**case.acceptance,'deck_sha256':'0'*64})]:
        assert evaluator.evaluate_case(broken,'agent').verdict==V.ORACLE_MISMATCH
    synth.assert_not_called()


def test_checkpoint_resume_does_not_repeat_attempts(tmp_path,monkeypatch):
    from klayout_drc.benchmark.manifest import BenchmarkManifestManager
    root=Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    case=BenchmarkManifestManager.load(root/'manifest.json').cases[0]
    evaluator=BenchmarkEvaluator(root,tmp_path/'campaign')
    result=EvaluationResult(case.case_id,case.rule_id,case.tier,'agent',{'M1.W.1':1},None,1,None,
                            V.MODEL_ERROR,None,None,0.,initially_clean=False)
    called=Mock(return_value=result);monkeypatch.setattr(evaluator,'evaluate_case',called)
    evaluator.evaluate_batch([case],'agent',verbose=False)
    evaluator.evaluate_batch([case],'agent',verbose=False)
    assert called.call_count==1
    assert json.loads((tmp_path/'campaign/summary.json').read_text())['verdict_counts']['model_error']==1


@pytest.mark.integration_sandbox
@pytest.mark.parametrize('body,limit,expected',[
    ('while True: pass',120,'nonzero_exit'),
    ("from pathlib import Path\nPath('/output/large').write_bytes(b'x'*100000)",2048,'nonzero_exit'),
])
def test_worker_resource_limits(tmp_path,body,limit,expected):
    if sandbox_availability():pytest.skip(sandbox_availability())
    source=tmp_path/'in';source.write_text('input');script=tmp_path/'script.py';script.write_text(body)
    # CPU-burning workers receive a one-second CPU/wall limit. File limits are independent.
    timeout=1 if body.startswith('while') else 10
    result=RepairExecutor(script,source,tmp_path/'out',timeout_seconds=timeout,max_output_bytes=limit).execute()
    assert result.status in (expected,'timeout')


@pytest.mark.integration_sandbox
def test_real_benchmark_scope_rejection(tmp_path):
    if sandbox_availability():pytest.skip(sandbox_availability())
    from klayout_drc.benchmark.manifest import BenchmarkManifestManager
    root=Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    case=BenchmarkManifestManager.load(root/'manifest.json').cases[0]
    script=tmp_path/'feol.py';script.write_text('''import sys
import klayout.db as db
layout=db.Layout();layout.read(sys.argv[1])
layout.top_cell().shapes(layout.layer(7,0)).insert(db.Box(0,0,20,20))
layout.write(sys.argv[2])
''')
    result=BenchmarkEvaluator(root,tmp_path/'eval').evaluate_case(case,'script_file',script)
    assert result.verdict==V.INVALID_PATCH
    assert result.pipeline_verdict=='invalid_patch' and result.final_total is None


def test_protected_region_and_instance_placement(tmp_path):
    l=db.Layout();l.dbu=.00025;t=l.create_cell('TOP');c=l.create_cell('MASTER');idx=l.layer(19,0)
    c.shapes(idx).insert(db.Box(0,0,100,100));inst=t.insert(db.CellInstArray(c.cell_index(),db.Trans(1000,0)))
    a,b=tmp_path/'a.gds',tmp_path/'b.gds';l.write(str(a))
    inst.trans=db.Trans(2000,0);l.write(str(b))
    assert not LayoutValidator(b,a).validate().is_valid
    preservation={'protected_regions':[{'layer':[19,0],'box_dbu':[900,-100,1200,200]}]}
    assert not LayoutValidator(b,a,preservation=preservation).validate().is_valid


def test_clean_controls_excluded_from_repair_rate():
    dirty=EvaluationResult('dirty','M1.W.1',DifficultyTier.ISOLATED,'agent',{'M1.W.1':1},{},1,0,
                            V.CLEAN_SUCCESS,0.,0.,1.,initially_clean=False)
    clean=replace(dirty,case_id='clean',initial_violations={},initial_total=0,verdict=V.CLEAN_UNCHANGED,initially_clean=True)
    summary=Scorer.aggregate('1.1.0','agent',[dirty,clean],2.)
    assert summary.dirty_cases==1 and summary.clean_controls==1 and summary.clean_success_rate==1.


def test_failed_preflight_blocks_requests_for_remaining_cases(tmp_path,monkeypatch):
    from klayout_drc.benchmark.manifest import BenchmarkManifestManager
    root=Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    cases=BenchmarkManifestManager.load(root/'manifest.json').cases[:3]
    evaluator=BenchmarkEvaluator(root,tmp_path/'campaign')
    first=cases[0]
    result=EvaluationResult(first.case_id,first.rule_id,first.tier,'agent',None,None,None,None,
                            V.BLOCKED,None,None,0.,initially_clean=False)
    execute=Mock(return_value=result);monkeypatch.setattr(evaluator,'evaluate_case',execute)
    summary=evaluator.evaluate_batch(cases,'agent',verbose=False)
    assert execute.call_count==1 and summary.verdict_counts['blocked']==3
    assert summary.total_cases==3 and summary.clean_success_count==0


@pytest.mark.integration_sandbox
@pytest.mark.parametrize('body',[
    'data=bytearray(3*1024**3)',
    "import subprocess\nsubprocess.run(['/usr/bin/true'])",
    "while True:\n    print('x'*10000,flush=True)",
])
def test_worker_memory_process_and_log_limits(tmp_path,body):
    if sandbox_availability():pytest.skip(sandbox_availability())
    source=tmp_path/'in';source.write_text('input')
    script=tmp_path/'script.py';script.write_text(body)
    result=RepairExecutor(script,source,tmp_path/'out',timeout_seconds=5).execute()
    assert result.status=='nonzero_exit',result


def test_report_formats_agree(tmp_path):
    import csv
    result=EvaluationResult('dirty','M1.W.1',DifficultyTier.ISOLATED,'agent',{'M1.W.1':1},None,1,None,
                            V.INVALID_PATCH,None,None,1.,pipeline_verdict='invalid_patch')
    summary=Scorer.aggregate('1.1.0','agent',[result],1.)
    Scorer.export_json(summary,tmp_path/'summary.json');Scorer.export_csv(summary,tmp_path/'summary.csv')
    with (tmp_path/'summary.csv').open() as handle:row=next(csv.DictReader(handle))
    data=json.loads((tmp_path/'summary.json').read_text())
    assert row['verdict']==data['results'][0]['verdict']=='invalid_patch'
    assert data['results'][0]['final_total'] is None and row['final_total']==''
    assert '| invalid_patch | 1 |' in Scorer.export_markdown(summary)


def test_campaign_identity_records_bedrock_and_rejects_provider_change(tmp_path, monkeypatch):
    from klayout_drc.benchmark.manifest import BenchmarkManifestManager
    root = Path(__file__).resolve().parents[1]/'test_data/benchmark_v1'
    case = BenchmarkManifestManager.load(root/'manifest.json').cases[0]
    monkeypatch.setenv('KLAYOUT_DRC_MODEL_PROVIDER', 'bedrock')
    monkeypatch.setenv('BEDROCK_MODEL', 'openai.gpt-oss-120b-1:0')
    monkeypatch.setenv('BEDROCK_REGION', 'ap-southeast-2')
    monkeypatch.setenv('AWS_API_KEY', 'aws-test-secret')
    monkeypatch.delenv('BEDROCK_TEMPERATURE', raising=False)
    evaluator = BenchmarkEvaluator(root, tmp_path/'campaign')
    result = EvaluationResult(case.case_id, case.rule_id, case.tier, 'agent',
                              None, None, None, None, V.BLOCKED, None, None, 0.,
                              initially_clean=False)
    called = Mock(return_value=result)
    monkeypatch.setattr(evaluator, 'evaluate_case', called)
    evaluator.evaluate_batch([case], 'agent', verbose=False)
    path = tmp_path/'campaign/campaign.json'
    identity = json.loads(path.read_text())
    assert identity['model_config'] == {
        'provider': 'bedrock', 'region': 'ap-southeast-2',
        'endpoint': 'https://bedrock-runtime.ap-southeast-2.amazonaws.com/openai/v1/chat/completions',
        'model': 'openai.gpt-oss-120b-1:0', 'temperature': None}
    assert 'aws-test-secret' not in path.read_text()
    evaluator.evaluate_batch([case], 'agent', verbose=False)
    assert called.call_count == 1
    monkeypatch.setenv('BEDROCK_REGION', 'us-west-2')
    with pytest.raises(ValueError, match='configuration changed'):
        evaluator.evaluate_batch([case], 'agent', verbose=False)
    monkeypatch.setenv('KLAYOUT_DRC_MODEL_PROVIDER', 'openai')
    with pytest.raises(ValueError, match='configuration changed'):
        evaluator.evaluate_batch([case], 'agent', verbose=False)
    assert called.call_count == 1
