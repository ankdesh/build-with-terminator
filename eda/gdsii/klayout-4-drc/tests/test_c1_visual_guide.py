"""Evidence and rendering acceptance for the C1 learning guide.

Requires the optional document dependencies Pillow and reportlab. These tests
use saved checker evidence and never call a model or run a repair.
"""
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip('PIL')
pytest.importorskip('reportlab')
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_c1', ROOT / 'scripts/capture_c1_examples.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)


def test_sources_and_counts_are_verified_before_capture(tmp_path):
    prepared, verified, _, _ = guide.prepare()
    assert len(prepared) == 10
    assert len(verified) >= 100
    source = tmp_path / 'source.gds'
    source.write_bytes(b'original')
    expected = guide.sha(source)
    source.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        guide.check_hash(source, expected)


def test_missing_after_report_stays_unknown():
    prepared, _, _, _ = guide.prepare()
    rejected = [item for item in prepared if item[2]['verdict'] == 'invalid_patch']
    assert len(rejected) == 2
    for _, _, run, _, _, reports in rejected:
        assert reports['output'] is None
        assert guide.report_counts(reports['output']) is None
        assert run['final_total'] is None
        assert run['validation']['is_valid'] is False


def test_dimension_arrows_measure_integer_geometry():
    prepared, _, _, _ = guide.prepare()
    expected = ['10 nm','12 nm','17.75 nm','18 nm','12 nm','18 nm',
                '10 nm gap','12 nm gap','10 nm','12 nm']
    for item, label in zip(prepared, expected):
        spec, _, _, _, paths, _ = item
        layout, regions, stats, _ = guide.geometry(paths['input'])
        ruler = guide.input_ruler(spec[0],stats,regions,layout.dbu)
        assert ruler[-1] == label


def test_native_export_places_real_marker_at_shape_edges(tmp_path):
    prepared, _, _, _ = guide.prepare()
    _, _, _, _, paths, reports = prepared[0]
    target = tmp_path / 'smoke.png'
    _, _, stats, _ = guide.geometry(paths['input'])
    result = guide.render(paths['input'],reports['input'],[-.02,-.02,.04,.12],target,
                          'Smoke test','1 scoped marker',stats)
    image = Image.open(target)
    assert image.size == (720,750)
    pixels = image.load()
    red = [(x,y) for y in range(90,560) for x in range(720)
           if pixels[x,y][0] > 150 and pixels[x,y][1] < 90 and pixels[x,y][2] < 110]
    assert len(red) > 100
    left,bottom,right,top = result['actual_window_um']
    # A width marker is the two vertical edges x = 0 and x = 10 nm.
    expected_x = [(x-left)/(right-left)*720 for x in (0,.01)]
    assert all(min(abs(x-px) for x,y in red) < 4 for px in expected_x)


def test_delivered_images_share_windows_and_match_manifest():
    # Finished artifacts moved into the verified handoff snapshot. Historical
    # builder hashes refer to the retained pre-port source, not today's builder.
    from klayout_drc.handoff.archive import Resolver
    snapshot = ROOT / 'archives/2026-10-28'
    resolver = Resolver(snapshot) if snapshot.exists() else None
    evidence = resolver.root if resolver else ROOT
    path = evidence / 'docs/reports/c1_visual_guide/image_manifest.json'
    manifest = json.loads(path.read_text())
    assert len(manifest['cases']) == 10
    count = 0
    for case in manifest['cases']:
        images = list(case['images'].values())
        assert len({tuple(img['actual_window_um']) for img in images}) == 1
        if case['verdict'] == 'invalid_patch':
            assert case['images']['output']['counts'] is None
            assert case['images']['output']['report'] is None
        if 'edge_detail' in case:
            images.append(case['edge_detail'])
        for img in images:
            image_path = evidence / img['image']
            guide.check_hash(image_path,img['sha256'])
            with Image.open(image_path) as picture:
                assert list(picture.size) == img['size_px']
            count += 1
    assert count == manifest['images_count'] == 32
    guide.check_hash(evidence / manifest['pdf']['path'],manifest['pdf']['sha256'])
    assert manifest['pdf']['pages'] == 15
    for path, expected in manifest['verified_sources'].items():
        guide.check_hash(resolver.resolve(path, expected) if resolver else ROOT / path, expected)
