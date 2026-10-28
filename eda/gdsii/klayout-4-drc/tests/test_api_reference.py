"""Executable API guidance and pre-dispatch failure gates. No model requests."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import klayout.db as db
import pytest

from klayout_drc import api_reference as reference
from klayout_drc.benchmark.evaluator import BenchmarkEvaluator
from klayout_drc.benchmark.manifest import BenchmarkManifestManager as Manifests
from klayout_drc.benchmark.types import BenchmarkVerdict
from klayout_drc.knowledge_loader import KnowledgeLoader
from klayout_drc.profile import DRCProfileManager

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_reference_cache():
    reference.verify_api_reference.cache_clear()
    yield
    reference.verify_api_reference.cache_clear()


@pytest.mark.parametrize('example', reference.EXAMPLES, ids=lambda example: example.name)
def test_every_published_example_executes(example, tmp_path):
    reference.validate_example(example, tmp_path)


def example_functions(name):
    namespace = {'db': db}
    exec(next(example.code for example in reference.EXAMPLES if example.name == name), namespace)
    return namespace


@pytest.mark.parametrize('dbu,grid,length,expected', [
    (0.00025, 0.00025, 0.018, 72),
    (0.00025, 0.0005, 0.018000001, 74),
    (0.001, 0.002, 0.0181, 20),
])
def test_manufacturing_grid_ceil(dbu, grid, length, expected):
    assert example_functions('units_and_grid')['length_on_grid'](length, dbu, grid) == expected


@pytest.mark.parametrize('length,dbu,grid', [(-1, 0.001, 0.001), (1, 0, 0.001),
                                           (1, 0.001, 0), (1, 0.001, 0.0015)])
def test_invalid_unit_or_grid_input(length, dbu, grid):
    with pytest.raises(ValueError):
        example_functions('units_and_grid')['length_on_grid'](length, dbu, grid)


def test_edge_overload_trap_and_boundaries():
    edges = db.Region(db.Box(0, 0, 144, 400)).edges()
    select = example_functions('edge_length_filter')['edges_in_range']
    assert sorted(edge.length() for edge in select(edges, 144, None).each()) == [144, 144, 400, 400]
    assert sorted(edge.length() for edge in select(edges, None, 144).each()) == []
    assert sorted(edge.length() for edge in select(edges, 144, 145).each()) == [144, 144]
    assert edges.with_length(144, None).count() != select(edges, 144, None).count()


def test_area_holes_and_components_are_not_total_layer_area():
    ring = db.Region(db.Box(0, 0, 100, 100)) - db.Region(db.Box(20, 20, 80, 80))
    separate = ring + db.Region(db.Box(200, 0, 210, 10))
    areas = example_functions('polygon_iteration_and_area')['component_areas'](separate)
    assert sorted(areas) == [100, 6400]
    assert sum(areas) > 500 and min(areas) < 500
    assert next(ring.each()).holes() == 1
    with pytest.raises(ValueError):
        example_functions('rectangle_measurement')['rectangle_width'](next(ring.each()))


def test_digest_and_runtime_are_in_knowledge_context(monkeypatch):
    expected = reference.render_api_reference()
    text = KnowledgeLoader(profile_name='asap7_curated').format_as_text()
    assert text.count(expected) == 1
    assert db.__version__ in text and reference.reference_digest() in text
    assert 'M1=19/0' in text
    original = reference.reference_digest()
    monkeypatch.setattr(reference, 'EXAMPLES', (replace(reference.EXAMPLES[0], notes='changed'),))
    assert reference.reference_digest() != original


def test_runtime_check_fails_on_broken_example(monkeypatch):
    bad = replace(reference.EXAMPLES[0], code='db.Region().each_polygon()', checks='')
    monkeypatch.setattr(reference, 'EXAMPLES', (bad,))
    with pytest.raises(reference.APIReferenceError, match='layout_io'):
        reference.verify_api_reference()


def test_reference_failure_blocks_campaign_without_synthesis(tmp_path, monkeypatch):
    import klayout_drc.single_shot as pipeline
    root = ROOT/'test_data/benchmark_v1'
    cases = Manifests.load(root/'manifest.json').cases[:3]
    def fail():
        raise reference.APIReferenceError('KLayout API reference check failed: test incompatibility')
    monkeypatch.setattr(pipeline, 'verify_api_reference', fail)
    monkeypatch.setattr(pipeline, 'sandbox_availability', lambda: None)
    synthesis = Mock(side_effect=AssertionError('No model request may be sent'))
    monkeypatch.setattr(pipeline.SingleShotOrchestrator, '_acquire_candidate_script', synthesis)
    summary = BenchmarkEvaluator(root, tmp_path/'blocked').evaluate_batch(cases, mode='agent', verbose=False)
    assert all(result.verdict == BenchmarkVerdict.BLOCKED for result in summary.results)
    assert 'API reference' in summary.results[0].error_message
    synthesis.assert_not_called()
    assert not list((tmp_path/'blocked').rglob('model_request.json'))


def test_cli_returns_reference_configuration_stage(monkeypatch, capsys):
    from klayout_drc import cli
    bad = replace(reference.EXAMPLES[0], code='raise ValueError("incompatible")', checks='')
    monkeypatch.setattr(reference, 'EXAMPLES', (bad,))
    monkeypatch.setattr('sys.argv', ['klayout-drc', '--mode', 'load-knowledge', '--json'])
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().err)['stage'] == 'api_reference'


def load_pilot_runner():
    spec = importlib.util.spec_from_file_location('pilot_runner', ROOT/'scripts/run_c1_bedrock_pilot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def comparison_fixture(tmp_path):
    runner = load_pilot_runner()
    root = ROOT/'test_data/benchmark_v1'
    manifest = Manifests.load(root/'manifest.json')
    selected = runner.select_cases(manifest)
    config = {'provider': 'bedrock', 'region': 'ap-southeast-2', 'model': 'test-model',
              'endpoint': 'https://bedrock-runtime.ap-southeast-2.amazonaws.com/openai/v1/chat/completions',
              'temperature': None}
    baseline = tmp_path/'baseline'; baseline.mkdir()
    campaign = {'model_config': config, 'manifest_sha256': Manifests.compute_sha256(root/'manifest.json'),
                'profile': 'asap7_curated', 'case_ids': [case.case_id for case in selected]}
    (baseline/'campaign.json').write_text(json.dumps(campaign))
    results = []
    for case in selected:
        directory = baseline/case.case_id; directory.mkdir()
        (directory/'run_manifest.json').write_text(json.dumps({'hashes': {
            'drc_script_sha256': Manifests.compute_sha256(DRCProfileManager().get_profile('asap7_curated').deck_path),
            'input_gds_sha256': case.sha256}}))
        (directory/'model_response.json').write_text('{}')
        results.append({'case_id': case.case_id, 'run_dir': str(directory)})
    (baseline/'summary.json').write_text(json.dumps({'results': results}))
    return runner, root, manifest, baseline, config


def test_comparison_keeps_exact_original_case_ids(comparison_fixture):
    runner, root, manifest, baseline, config = comparison_fixture
    selected = runner.check_comparison(root, manifest, baseline, config)
    assert [case.case_id for case in selected] == json.loads((baseline/'campaign.json').read_text())['case_ids']


@pytest.mark.parametrize('setting', ['model', 'region', 'endpoint', 'temperature'])
def test_comparison_rejects_changed_provider_settings(comparison_fixture, setting):
    runner, root, manifest, baseline, config = comparison_fixture
    with pytest.raises(ValueError, match='differs'):
        runner.check_comparison(root, manifest, baseline, {**config, setting: 'changed'})


@pytest.mark.parametrize('setting', ['manifest_sha256', 'profile', 'deck', 'input'])
def test_comparison_rejects_changed_inputs(comparison_fixture, setting):
    runner, root, manifest, baseline, config = comparison_fixture
    if setting in ('manifest_sha256', 'profile'):
        path = baseline/'campaign.json'
        data = json.loads(path.read_text()); data[setting] = 'changed'
    else:
        first = runner.select_cases(manifest)[0]
        path = baseline/first.case_id/'run_manifest.json'
        data = json.loads(path.read_text())
        data['hashes']['drc_script_sha256' if setting == 'deck' else 'input_gds_sha256'] = 'changed'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='differs'):
        runner.check_comparison(root, manifest, baseline, config)


def test_failed_marker_calls_have_verified_replacements():
    helpers = example_functions('edge_pair_inspection')
    markers = db.Region(db.Box(0, 0, 40, 400)).width_check(72)
    with pytest.raises(AttributeError):
        markers.empty()
    pair = next(markers.each())
    with pytest.raises(TypeError):
        pair.first()
    assert helpers['has_markers'](markers)
    assert not helpers['has_markers'](db.EdgePairs())
    first, second = helpers['marker_edges'](markers)[0]
    assert first == pair.first and second == pair.second
    assert {x for edge in (first, second) for x, _ in helpers['edge_endpoints'](edge)} == {0, 40}
    polygon = db.Polygon(db.Box(0, 0, 40, 400))
    with pytest.raises(AttributeError):
        polygon.contains(first.p1)
    assert example_functions('polygon_iteration_and_area')['polygon_contains_or_touches'](polygon, first.p1)


def test_failed_region_insertions_have_preserving_replacements():
    helpers = example_functions('region_construction_and_insertion')
    layout = db.Layout(); top = layout.create_cell('TOP'); layer = layout.layer(7, 3)
    top.shapes(layer).insert(db.Box(0, 0, 10, 10))
    shape = next(top.shapes(layer).each())
    source = helpers['region_from_shapes'](top.shapes(layer))
    destination = db.Region(db.Box(20, 0, 30, 10))
    with pytest.raises(TypeError):
        destination.insert(shape)
    with pytest.raises(TypeError):
        destination.insert(source.each_merged())
    assert destination.area() == 100
    helpers['append_region'](destination, source)
    assert destination.area() == 200 and len(list(destination.each_merged())) == 2
    assert source.area() == 100


@pytest.mark.parametrize('contract', reference.CONTRACTS, ids=lambda contract: contract.call)
def test_every_published_call_has_a_behavior_check(contract, tmp_path):
    assert contract.check.strip()
    reference.validate_contract(contract, tmp_path)


def test_generated_document_is_current_complete_and_bounded():
    rendered = reference.render_api_reference()
    assert (ROOT/'knowledge/klayout_api_patterns.md').read_text() == rendered
    assert len(rendered) <= reference.MAX_REFERENCE_CHARACTERS == 18000
    assert len({contract.call for contract in reference.CONTRACTS}) == len(reference.CONTRACTS)
    assert all(contract.example in {example.name for example in reference.EXAMPLES} for contract in reference.CONTRACTS)
    for contract in reference.CONTRACTS:
        assert contract.call.replace('|', r'\|') in rendered
    assert '## 4. Hierarchy and safe editing' in rendered
    assert rendered.count('=== Verified KLayout Python API Reference ===') == 1


@pytest.mark.parametrize('custom_reserved', [False, True])
def test_custom_knowledge_still_contains_one_canonical_document(tmp_path, custom_reserved):
    if custom_reserved:
        (tmp_path/'klayout_api_patterns.md').write_text('stale unverified API notes')
    (tmp_path/'custom.md').write_text('# Notes\n```python\nraise RuntimeError("Never execute Markdown")\n```')
    loader = KnowledgeLoader(tmp_path, profile_name='asap7_curated')
    docs = loader.load_documents()
    assert [doc.filename for doc in docs].count('klayout_api_patterns.md') == 1
    text = loader.format_as_text()
    assert text.count(reference.render_api_reference()) == 1
    assert 'stale unverified API notes' not in text


def test_empty_knowledge_keeps_canonical_trailing_newline(tmp_path):
    text = KnowledgeLoader(tmp_path).format_as_text()
    assert text.count(reference.render_api_reference()) == 1


def test_contracts_and_document_rules_are_bound_to_digest(monkeypatch):
    original = reference.reference_digest()
    monkeypatch.setattr(reference, 'CONTRACTS', (replace(reference.CONTRACTS[0], result='changed'),) + reference.CONTRACTS[1:])
    assert reference.reference_digest() != original
    original = reference.reference_digest()
    monkeypatch.setattr(reference, 'HIERARCHY_RULES', reference.HIERARCHY_RULES + '\nchanged')
    assert reference.reference_digest() != original


def test_bad_contract_blocks_reference(monkeypatch):
    monkeypatch.setattr(reference, 'CONTRACTS', (replace(reference.CONTRACTS[0], check='assert False, "bad API contract"'),))
    with pytest.raises(reference.APIReferenceError, match='bad API contract'):
        reference.verify_api_reference()


def test_reference_export_formats_are_identical():
    import subprocess
    import sys
    command = [sys.executable, '-m', 'klayout_drc.api_reference']
    document = subprocess.check_output(command + ['--format', 'markdown'], cwd=ROOT, text=True)
    response = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
    assert document == response['reference_text'] == reference.render_api_reference()
    assert response['contracts_checked'] == len(reference.CONTRACTS)
    assert response['examples_checked'] == len(reference.EXAMPLES)


def test_hierarchy_examples_preserve_masters_and_definitions(tmp_path):
    example = next(example for example in reference.EXAMPLES if example.name == 'hierarchy_read')
    values = reference.validate_example(example, tmp_path)
    leaf, block, top, layer = (values[name] for name in ('leaf', 'block', 'top', 'layer'))
    before = db.Region(leaf.shapes(layer))
    definitions = [(instance.cell_index, str(instance.cplx_trans)) for cell in (top, block) for instance in cell.each_inst()]
    polygons = values['recursive_polygons'](top, layer)
    assert len(polygons) == 8
    assert sorted(str(polygon.bbox()) for polygon in polygons) == sorted(str(box) for box in values['expected_boxes'])
    detached = db.Region(polygons).moved(50, 60)
    assert detached.area() == db.Region(polygons).area()
    assert (db.Region(leaf.shapes(layer)) ^ before).is_empty()
    assert definitions == [(instance.cell_index, str(instance.cplx_trans)) for cell in (top, block) for instance in cell.each_inst()]


def test_component_replacement_preserves_unaffected_holes():
    helpers = example_functions('geometry_values')
    ring = db.Region(db.Box(0, 0, 100, 100)) - db.Region(db.Box(20, 20, 80, 80))
    source = ring + db.Region(db.Box(200, 0, 210, 10))
    before = source.dup()
    target = next(polygon for polygon in source.each_merged() if polygon.is_box())
    result = helpers['replace_component'](source, target, db.Region(db.Box(200, 0, 220, 10)))
    assert (source ^ before).is_empty()
    assert result.area() == 6600 and sorted(p.holes() for p in result.each_merged()) == [0, 1]
    assert (ring - result).is_empty()
