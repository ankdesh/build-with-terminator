"""Checker-backed acceptance records, kept outside candidate prompt inputs.

References are synthetic legal seeds for the curated scope, not recovered source
layouts or connectivity references. A recorded region replacement maps each seed
back to the preserved v1 case geometry.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import klayout.db as db
from ..config import DRCJobConfig, DRCConfigurationError
from ..marker_comparison import marker_records
from ..parser import DRCParser
from ..profile import DRCProfileManager
from ..runner import DRCRunner
from .manifest import BenchmarkManifestManager as Manifests


def geometry_parameters(layout):
    top = layout.top_cell()
    return {'dbu_um': layout.dbu, 'top_cell': top.name,
            'regions': {str(layout.get_info(i)): str(db.Region(top.begin_shapes_rec(i)).merged())
                        for i in layout.layer_indexes()}}


def run_checker(path, profile, report):
    cfg = DRCJobConfig(input_gds=path, drc_script=profile.deck_path, output_lyrdb=report,
                       param_in_gds=profile.param_in_gds, param_report=profile.param_report,
                       extra_params=profile.extra_params,
                       timeout_seconds=600 if profile.name == 'asap7_public_full' else 120)
    DRCRunner(cfg).run()
    return DRCParser().parse(report)


def accept_manifest(manifest, base_dir):
    """Validate every case and seed before returning a publishable manifest."""
    base_dir = Path(base_dir)
    profile = DRCProfileManager().get_profile('asap7_curated')
    evidence = base_dir/'oracle'; evidence.mkdir(exist_ok=True)
    references = base_dir/'references'; references.mkdir(exist_ok=True)
    deck_hash = Manifests.compute_sha256(profile.deck_path)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        accepted = list(pool.map(lambda case: _accept_case(case, base_dir, profile, evidence, references, deck_hash), manifest.cases))
    return replace(manifest, benchmark_version='1.1.0', cases=accepted, acceptance={
        'schema_version': 2, 'profile': profile.name, 'deck_sha256': deck_hash,
        'klayout_version': db.__version__, 'validation_scope': 'geometry_only',
        'generator_sha256': Manifests.compute_sha256(Path(__file__).with_name('generator.py')),
        'seed_policy': 'Fixed deterministic catalog. No random seed.',
        'deviations': ['V1.W.1 replaces planned enclosure coverage. Enclosure is not evaluated.'],
        'distinct_layouts': len({c.acceptance['duplicate_group'] for c in accepted})})


def safe_path(base, relative):
    path = (base/relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Artifact path escapes benchmark directory')
    return path


def verify_case(case, base_dir, profile):
    """Fail closed before synthesis if any accepted input/evidence was changed."""
    record = case.acceptance
    required = {'profile', 'deck_sha256', 'observed_counts', 'expected_counts', 'observed_markers',
                'reference_gds', 'reference_sha256', 'reference_report', 'reference_report_sha256',
                'report', 'report_sha256', 'preservation', 'duplicate_group'}
    if not required <= record.keys():
        raise ValueError(f'{case.case_id}: missing accepted C1 metadata; regenerate the dataset')
    if record['profile'] != profile.name or record['deck_sha256'] != Manifests.compute_sha256(profile.deck_path):
        raise ValueError('Checker scope or deck hash mismatch')
    counts = record['observed_counts']
    if (record['expected_counts'] != counts or sum(counts.values()) != case.expected_initial_violations
            or set(counts) != set(case.expected_rules)):
        raise ValueError('Expected baseline counts disagree with accepted evidence')
    for path_key, digest_key in [('reference_gds', 'reference_sha256'), ('reference_report', 'reference_report_sha256'), ('report', 'report_sha256')]:
        if Manifests.compute_sha256(safe_path(base_dir, record[path_key])) != record[digest_key]:
            raise ValueError(f'{case.case_id}: {path_key} hash mismatch')
    if Manifests.compute_sha256(safe_path(base_dir, case.gds_rel_path)) != case.sha256:
        raise ValueError('Case GDS hash mismatch')
    if DRCParser().parse(safe_path(base_dir, record['reference_report'])).total_violations:
        raise ValueError('Reference evidence is not clean')


def _accept_case(case, base_dir, profile, evidence, references, deck_hash):
    source = base_dir/case.gds_rel_path
    if Manifests.compute_sha256(source) != case.sha256:
        raise ValueError(f'Input hash mismatch: {case.case_id}')
    layout = db.Layout(); layout.read(str(source)); top = layout.top_cell()
    parameters = geometry_parameters(layout)
    observed = run_checker(source, profile, evidence/f'{case.case_id}.lyrdb')
    if observed.total_violations != case.expected_initial_violations or set(observed.rule_summary) != set(case.expected_rules):
        raise ValueError(f'Oracle mismatch: {case.case_id}: {observed.rule_summary}')
    # Distinct connected features receive legal rectangular seeds, on the same
    # physical layers and grid. Exact region deltas document the mutation.
    legal = db.Layout(); legal.dbu = layout.dbu; seed_top = legal.create_cell(top.name)
    minimum = int(round(.024/layout.dbu)); length = int(round(.040/layout.dbu))
    counts, mutation = {}, {}
    for idx in layout.layer_indexes():
        info = layout.get_info(idx); key = f'{info.layer}/{info.datatype}'
        region = db.Region(top.begin_shapes_rec(idx)).merged()
        counts[key] = region.count()
        legal_idx = legal.layer(info)
        if not case.expected_initial_violations:
            seed_top.shapes(legal_idx).insert(region)
        else:
            cursor = 0
            for polygon in region.each():
                bounds = polygon.bbox()
                width, height = max(minimum, bounds.width()), max(length, bounds.height())
                seed_top.shapes(legal_idx).insert(db.Box(cursor, 0, cursor+width, height))
                cursor += width + 2*minimum
        seed = db.Region(seed_top.shapes(legal_idx)).merged()
        added, removed = region-seed, seed-region
        if not (((seed-removed)|added)^region).is_empty():
            raise ValueError('Mutation round-trip failed')
        mutation[key] = {'added': str(added), 'removed': str(removed)}
    reference = references/f'{case.case_id}.gds'
    options = db.SaveLayoutOptions(); options.gds2_write_timestamps = False
    legal.write(str(reference), options)
    reference_report = evidence/f'{case.case_id}.reference.lyrdb'
    clean = run_checker(reference, profile, reference_report)
    if clean.total_violations:
        raise ValueError(f'Legal reference is dirty: {case.case_id}: {clean.rule_summary}')
    group = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    record = {'profile': profile.name, 'deck_sha256': deck_hash,
              'generator': 'klayout_drc.benchmark.generator:deterministic_catalog_v1',
              'constructor_parameters': parameters, 'generation_seed': None,
              'reference_kind': 'synthetic_legal_component_seed',
              'reference_gds': str(reference.relative_to(base_dir)),
              'reference_sha256': Manifests.compute_sha256(reference),
              'reference_report': str(reference_report.relative_to(base_dir)),
              'reference_report_sha256': Manifests.compute_sha256(reference_report),
              'observed_counts': observed.rule_summary,
              'expected_counts': observed.rule_summary,
              'observed_markers': json.loads(json.dumps(marker_records(observed))),
              'report': f'oracle/{case.case_id}.lyrdb',
              'report_sha256': Manifests.compute_sha256(evidence/f'{case.case_id}.lyrdb'),
              'mutation': mutation, 'preservation': {'component_counts': counts, 'protected_regions': []},
              'duplicate_group': group}
    return replace(case, acceptance=record)
