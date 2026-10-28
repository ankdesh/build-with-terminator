"""C2+C3 policy, context, qualification and scoring regression tests."""
from dataclasses import replace
import json
from pathlib import Path
import klayout.db as db
import pytest
from klayout_drc.edit_policy import EditPolicy, ContextIncomplete, policy_context, validate_edit_policy
from klayout_drc.benchmark.c2c3.contracts import Case, Manifest
from klayout_drc.benchmark.c2c3.generator import canonical_digest, save_layout
from klayout_drc.benchmark.c2c3.evaluator import summarize


def fixture():
    layout = db.Layout(); layout.dbu = .00025
    top = layout.create_cell('TOP'); route = layout.create_cell('ROUTE'); cell = layout.create_cell('PDK_CELL')
    layer = layout.layer(20, 0)
    route.shapes(layer).insert(db.Box(0, 0, 100, 500))
    cell.shapes(layer).insert(db.Box(500, 0, 700, 500))
    top.insert(db.CellInstArray(route.cell_index(), db.Trans(db.Trans.R90, 1000, 2000)))
    top.insert(db.CellInstArray(cell.cell_index(), db.Trans()))
    policy = EditPolicy({'ROUTE': {'layers': [[20, 0]], 'box_dbu': [-50, 50, 150, 450],
                                  'anchors': [{'layer': [20, 0], 'box_dbu': [0, 0, 100, 50]}]}}, [[0, 0, 1, 1]])
    return layout, policy


def copy(layout, tmp_path):
    path = tmp_path/'copy.gds'; save_layout(layout, path)
    result = db.Layout(); result.read(str(path)); return result


def test_transformed_route_and_complete_context(tmp_path):
    layout, policy = fixture(); path = tmp_path/'input.gds'; save_layout(layout, path)
    context = policy_context(path, policy)
    shape = next(s for s in context['shapes'] if s['editable'])
    assert shape['instance_path'][0][0] == 'ROUTE'
    assert db.Polygon.from_s(shape['polygon_dbu']).bbox() == db.Box(500, 2000, 1000, 2100)
    assert context['omitted_required_shapes'] == 0
    assert validate_edit_policy(layout, copy(layout, tmp_path), policy) == []


def test_context_budget_blocks_instead_of_truncating(tmp_path):
    layout, policy = fixture(); path = tmp_path/'input.gds'; save_layout(layout, path)
    with pytest.raises(ContextIncomplete):
        policy_context(path, replace(policy, max_context_shapes=1))


@pytest.mark.parametrize('change', ['cell', 'placement', 'boundary', 'anchor', 'delete', 'layer', 'new_cell', 'overlap'])
def test_forbidden_edits(tmp_path, change):
    before, policy = fixture(); after = copy(before, tmp_path); idx = after.layer(20, 0)
    route = after.cell('ROUTE')
    if change == 'cell': after.cell('PDK_CELL').shapes(idx).insert(db.Box(0, 0, 4, 4))
    elif change == 'placement': next(after.top_cell().each_inst()).trans = db.Trans(1, 1)
    elif change == 'boundary': route.shapes(idx).insert(db.Box(0, 600, 100, 700))
    elif change == 'anchor': route.shapes(idx).insert(db.Box(-4, 0, 0, 40))
    elif change == 'delete': route.shapes(idx).clear()
    elif change == 'layer': route.shapes(after.layer(30, 0)).insert(db.Box(0, 100, 100, 200))
    elif change == 'new_cell': after.create_cell('UNDECLARED')
    else:
        # Move a protected obstacle into the route neighborhood in both inputs.
        for layout in (before, after):
            cell = layout.cell('PDK_CELL'); cell.shapes(layout.layer(20, 0)).insert(db.Box(810, 2000, 820, 2150))
        route.shapes(idx).insert(db.Box(0, 180, 100, 200))
        route.shapes(idx).insert(db.Box(100, 180, 140, 200))
    assert validate_edit_policy(before, after, policy)


def test_local_edit_inside_mask_is_allowed(tmp_path):
    before, policy = fixture(); after = copy(before, tmp_path)
    idx = after.layer(20, 0); route = after.cell('ROUTE')
    region = db.Region(route.shapes(idx)) - db.Region(db.Box(0, 200, 4, 300))
    route.shapes(idx).clear(); route.shapes(idx).insert(region)
    assert validate_edit_policy(before, after, policy) == []


def test_repeated_master_is_not_editable(tmp_path):
    layout, policy = fixture()
    layout.top_cell().insert(db.CellInstArray(layout.cell('ROUTE').cell_index(), db.Trans(1000, 0)))
    assert any('instance-specific' in e for e in validate_edit_policy(layout, copy(layout, tmp_path), policy))


def test_array_context_identifies_elements_and_rejects_shared_edit(tmp_path):
    layout, policy = fixture()
    top = layout.top_cell()
    for inst in list(top.each_inst()):
        if layout.cell(inst.cell_index).name == 'ROUTE': inst.delete()
    top.insert(db.CellInstArray(layout.cell('ROUTE').cell_index(), db.Trans(),
                               db.Vector(1000, 0), db.Vector(0, 1000), 2, 2))
    path = tmp_path/'array.gds'; save_layout(layout, path)
    shapes = [s for s in policy_context(path, policy)['shapes'] if s['editable']]
    assert len(shapes) == 4
    assert {(s['instance_path'][0][1], s['instance_path'][0][2]) for s in shapes} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert any('instance-specific' in e for e in validate_edit_policy(layout, copy(layout, tmp_path), policy))


@pytest.mark.parametrize('name,layer', [('CLOCK_ROUTE', (30, 0)), ('POWER_ROUTE', (20, 0))])
def test_clock_and_power_routes_are_protected(tmp_path, name, layer):
    before, policy = fixture()
    cell = before.create_cell(name)
    cell.shapes(before.layer(*layer)).insert(db.Box(1000, 0, 1100, 500))
    before.cell('TOP').insert(db.CellInstArray(cell.cell_index(), db.Trans()))
    after = copy(before, tmp_path)
    after.cell(name).shapes(after.layer(*layer)).clear()
    assert any(f'protected cell changed: {name}' in e for e in validate_edit_policy(before, after, policy))


def test_missing_checker_dependency_is_an_explicit_error(tmp_path, monkeypatch):
    from klayout_drc.benchmark.acceptance import run_checker
    from klayout_drc.config import DRCExecutionError
    from klayout_drc.profile import DRCProfileManager
    import klayout_drc.runner as runner
    layout, _ = fixture(); path = tmp_path/'input.gds'; save_layout(layout, path)
    def missing(*args, **kwargs): raise FileNotFoundError('missing checker')
    monkeypatch.setattr(runner.subprocess, 'run', missing)
    with pytest.raises(DRCExecutionError, match='not found'):
        run_checker(path, DRCProfileManager().get_profile('asap7_c2c3_v1'), tmp_path/'missing.lyrdb')


def test_cli_reports_missing_python_dependency_as_blocked(tmp_path, monkeypatch, capsys):
    import builtins
    from klayout_drc.benchmark.c2c3.cli import main
    real_import = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'routed_generator': raise ModuleNotFoundError('Missing geometry dependency')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    assert main(['generate-routed', '--dataset', str(tmp_path), '--bundles', str(tmp_path/'sources.json'),
                 '--platform', str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'blocked'


def test_native_markers_can_persist_without_blocking_repair(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from klayout_drc.benchmark.c2c3 import evaluator
    from klayout_drc.marker_geometry import BoxMarker
    from klayout_drc.parser import DRCReportData, RuleCategory, ViolationItem, ViolationGeometry
    from klayout_drc.marker_comparison import marker_records
    native = ViolationGeometry('box', 'box: (10,10;11,11)', marker=BoxMarker(10., 10., 11., 11.))
    report = DRCReportData(Path('native'), [RuleCategory('M2.W.1', '', [ViolationItem(0, 'M2.W.1', 'TOP', [native])])])
    layout, _ = fixture(); save_layout(layout, tmp_path/'input.gds'); save_layout(layout, tmp_path/'patched.gds')
    case = SimpleNamespace(case_id='native', level=3, kind='repair', source_group='g0', metrics={},
        gds='input.gds', scope_box_um=[0, 0, 1, 1],
        evidence={'target_markers': [{'rule': 'M2.W.1'}], 'reference_report': 'baseline.lyrdb'})
    monkeypatch.setattr(evaluator.DRCParser, 'parse', lambda *args: report)
    summary = SimpleNamespace(verdict='geometry_only', validation_level='geometry_only', total_before=2, total_after=1,
        diff_report=None, execution_result=SimpleNamespace(status='success', peak_rss_bytes=None),
        validation_result=SimpleNamespace(is_valid=True))
    result = evaluator.score_case(case, summary, tmp_path, tmp_path)
    assert marker_records(report)
    assert result['passed'] and result['baseline_relative']['persisted'] == 1


def test_read_only_policy_rejects_changed_route(tmp_path):
    layout, policy = fixture(); after = copy(layout, tmp_path)
    after.cell('ROUTE').shapes(after.layer(20, 0)).clear()
    assert validate_edit_policy(layout, after, replace(policy, editable_cells={}))


def test_off_grid_candidate_is_rejected(tmp_path):
    before, policy = fixture(); after = copy(before, tmp_path)
    idx = after.layer(20, 0); route = after.cell('ROUTE')
    region = db.Region(route.shapes(idx))-db.Region(db.Box(0, 200, 3, 300))
    route.shapes(idx).clear(); route.shapes(idx).insert(region)
    assert any('manufacturing grid' in error for error in validate_edit_policy(before, after, policy))


def test_separate_denominators_and_no_false_completion():
    manifest = Manifest()
    result = {'level': 1, 'kind': 'no_edit', 'source_group': 'source', 'passed': True, 'verdict': 'unchanged_control'}
    summary = summarize(manifest, 'no_change', [result])
    assert summary['repair']['passed'] == 0
    assert summary['repair']['planned'] == 30
    assert summary['no_edit']['passed'] == 1
    assert not summary['dataset_complete']


def test_reports_state_primary_and_diagnostic_scopes(tmp_path):
    from klayout_drc.benchmark.c2c3.evaluator import export_report
    summary = summarize(Manifest(), 'no_change', [])
    export_report(tmp_path, summary)
    assert json.loads((tmp_path/'summary.json').read_text())['scopes']['public_audit_is_acceptance_gate'] is False
    assert 'scored_profile,public_audit_profile,public_audit_status' in (tmp_path/'summary.csv').read_text()
    text = (tmp_path/'report.md').read_text()
    assert 'asap7_c2c3_v1' in text and 'asap7_public_full' in text and 'diagnostic only' in text


def test_rule_profile_is_independent_of_c1():
    from klayout_drc.profile import DRCProfileManager
    manager = DRCProfileManager()
    assert manager.get_profile('asap7_curated').deck_path != manager.get_profile('asap7_c2c3_v1').deck_path
    provenance = json.loads(manager.get_profile('asap7_c2c3_v1').deck_path.with_suffix('.provenance.json').read_text())
    assert provenance['new_rules']['V2.M2.EN.1']['correction']


def test_corrected_enclosure_accepts_opposite_sides_and_rejects_adjacent_sides(tmp_path):
    from klayout_drc.benchmark.acceptance import run_checker
    from klayout_drc.profile import DRCProfileManager
    layout = db.Layout(); layout.dbu = .00025; top = layout.create_cell('ENCLOSURE_MATRIX')
    # left, bottom, right, top margins in DBU. 20 DBU = 5 nm.
    margins = [(20, 20, 20, 20), (20, 0, 20, 0), (0, 20, 0, 20),
               (20, 20, 0, 0), (19, 19, 19, 19), (0, 0, 0, 0), (20, 20, 20, 0)]
    expected = {3, 4, 5}
    for i, (left, bottom, right, upper) in enumerate(margins):
        x = i*2000
        top.shapes(layout.layer(25, 0)).insert(db.Box(x+200, 200, x+272, 272))
        top.shapes(layout.layer(20, 0)).insert(db.Box(x+200-left, 200-bottom, x+272+right, 272+upper))
    path = tmp_path/'matrix.gds'; save_layout(layout, path)
    report = run_checker(path, DRCProfileManager().get_profile('asap7_c2c3_v1'), tmp_path/'matrix.lyrdb')
    actual = {round(g.bbox_um[0]/layout.dbu/2000) for c in report.categories if c.name == 'V2.M2.EN.1'
              for v in c.violations for g in v.geometries}
    assert actual == expected


def test_missing_routed_build_is_not_a_pass(tmp_path):
    from klayout_drc.benchmark.c2c3.routed_generator import verified_bundle
    (tmp_path/'build.json').write_text(json.dumps({'status': 'failed'}))
    with pytest.raises(ValueError, match='incomplete'):
        verified_bundle(tmp_path)


def test_route_candidate_uses_actual_region_interior():
    from klayout_drc.benchmark.c2c3.routed_generator import segments, notch
    region = db.Region(db.Box(0, 0, 72, 800))
    boxes = segments(region)
    assert boxes
    assert (db.Region(notch(boxes[0]))-region).is_empty()
    assert (region-db.Region(notch(boxes[0]))).width_check(72).count() > 0


def test_incomplete_dataset_cannot_start_model_campaign(tmp_path, monkeypatch):
    from klayout_drc.benchmark.c2c3 import evaluator
    monkeypatch.setattr(evaluator, 'verify_dataset', lambda root: Manifest())
    with pytest.raises(ValueError, match='Freeze 50'):
        evaluator.evaluate(tmp_path, tmp_path/'campaign', 'agent', allow_incomplete=True)
    assert not (tmp_path/'campaign').exists()


def test_candidate_error_never_receives_restraint_credit(tmp_path):
    from types import SimpleNamespace
    from klayout_drc.benchmark.c2c3.evaluator import score_case
    case = SimpleNamespace(case_id='test', level=1, kind='clean_control', source_group='source', metrics={},
                           evidence={'target_markers': [], 'target_scope_rules': ['M2.W.1']})
    summary = SimpleNamespace(verdict='invalid_patch', validation_level='not_run', total_before=0, total_after=None,
        diff_report=None, execution_result=SimpleNamespace(status='nonzero_exit', peak_rss_bytes=None,
                                                         error_message='Missing API member'), error_message='Missing API member')
    result = score_case(case, summary, tmp_path, tmp_path/'run')
    assert not result['passed']
    assert result['failure_stage'] == 'python_execution'


def test_via_ownership_comes_from_explicit_regular_def_nets():
    from klayout_drc.benchmark.c2c3.routes import explicit_def_vias
    text = '''SPECIALNETS 1 ;
    - VDD + ROUTED M2 ( 1 2 ) VIA23 ;
END SPECIALNETS
NETS 2 ;
    - signal + USE SIGNAL + ROUTED M2 ( 10 20 ) VIA23
      NEW M2 ( 30 40 ) VIA23 ;
    - unknown + ROUTED M2 ( 50 60 ) VIA23 ;
END NETS
'''
    assert explicit_def_vias(text, {'signal'}, {'VIA_VIA23'}) == [
        ('signal', 'VIA_VIA23', 10, 20), ('signal', 'VIA_VIA23', 30, 40)]


@pytest.mark.parametrize('statement', ['( * 20 ) VIA23', '( 10 20 ) VIA23 S', '( 10 20 ) VIA23 DO 2 BY 2 STEP 1 1', '( 10 20 ) UNKNOWN'])
def test_unsupported_via_ownership_is_not_guessed(statement):
    from klayout_drc.benchmark.c2c3.routes import explicit_def_vias
    text = f'NETS 1 ;\n - signal + ROUTED M2 {statement} ;\nEND NETS\n'
    assert explicit_def_vias(text, {'signal'}, {'VIA_VIA23'}) == []
