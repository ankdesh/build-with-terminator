"""Deterministic real-cell fixtures and independently qualified mutation cases."""
import hashlib
import json
from pathlib import Path
import klayout.db as db
from .contracts import Case, Manifest, sha256, write_json
from .rules import PROFILE
from ..acceptance import run_checker
from ...edit_policy import EditPolicy, policy_context, validate_edit_policy
from ...marker_comparison import marker_records
from ...profile import DRCProfileManager


def save_layout(layout, path):
    options = db.SaveLayoutOptions(); options.gds2_write_timestamps = False
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(path), options)


def load_layout(path):
    layout = db.Layout(); layout.read(str(path)); return layout


def canonical_digest(layout):
    cells = []
    for cell in sorted(layout.each_cell(), key=lambda c: c.name):
        layers = []
        for idx in layout.layer_indexes():
            if not cell.shapes(idx).is_empty():
                layers.append((str(layout.get_info(idx)), str(db.Region(cell.shapes(idx)).merged())))
        instances = sorted((layout.cell(i.cell_index).name, str(i.cplx_trans), str(i.a), str(i.b), i.na, i.nb)
                           for i in cell.each_inst())
        cells.append((cell.name, sorted(layers), instances))
    return hashlib.sha256(json.dumps([layout.dbu, cells], sort_keys=True).encode()).hexdigest()


def scoped_records(report, box):
    def intersects(bounds):
        return bounds[0] <= box[2] and bounds[2] >= box[0] and bounds[1] <= box[3] and bounds[3] >= box[1]
    return [r for r in json.loads(json.dumps(marker_records(report))) if any(intersects(b) for b in r['boxes'])]


def records_key(record):
    return json.dumps(record, sort_keys=True)


def added_records(before, after):
    from collections import Counter
    counts = Counter(records_key(r) for r in before)
    result = []
    for record in after:
        key = records_key(record)
        if counts[key]: counts[key] -= 1
        else: result.append(record)
    return result


def recipe_hashes():
    from ... import edit_policy
    paths = [Path(__file__), Path(__file__).with_name('routes.py'), Path(__file__).with_name('routed_generator.py'),
             Path(edit_policy.__file__)]
    return {p.name: sha256(p) for p in paths}


def layout_metrics(layout):
    def count(cell):
        return sum(max(1,i.na)*max(1,i.nb) * (1 + count(layout.cell(i.cell_index))) for i in cell.each_inst())
    def depth(cell):
        return 1 + max((depth(layout.cell(i.cell_index)) for i in cell.each_inst()), default=0)
    top = layout.top_cell()
    return {'cell_definitions': layout.cells(), 'instance_count': count(top), 'hierarchy_depth': depth(top),
            'shape_count': sum(db.Region(top.begin_shapes_rec(idx)).count() for idx in layout.layer_indexes()),
            'dbu_um': layout.dbu}


def cell_source(library_path, level, group):
    library = load_layout(library_path)
    if library.dbu != .00025:
        raise ValueError('Unverified ASAP7 GDS units')
    layout = db.Layout(); layout.dbu = library.dbu
    top = layout.create_cell('BENCHMARK_TOP')
    prefixes = ('INV', 'BUF', 'NAND2', 'NOR2', 'DFFHQN')
    masters = []
    for prefix in prefixes:
        choices = sorted((c for c in library.each_cell() if c.name.startswith(prefix)), key=lambda c: c.name)
        if len(choices) <= group:
            raise ValueError(f'Missing real cell family: {prefix}')
        original = choices[group]
        copied = layout.create_cell(original.name); copied.copy_tree(original); masters.append(copied)
    block = top if level == 1 else layout.create_cell('REPEATED_BLOCK')
    for i in range(10 if group == 0 else 15):
        master = masters[i % len(masters)]
        block.insert(db.CellInstArray(master.cell_index(), db.Trans((i % 5)*8000, (i//5)*2400)))
    if level == 2:
        cluster = layout.create_cell('CLUSTER')
        cluster.insert(db.CellInstArray(block.cell_index(), db.Trans(), db.Vector(44000, 0), db.Vector(0, 9000), 2, 2))
        top.insert(db.CellInstArray(cluster.cell_index(), db.Trans()))
        top.insert(db.CellInstArray(cluster.cell_index(), db.Trans(db.Trans.R90, 110000, 0)))
        top.insert(db.CellInstArray(block.cell_index(), db.Trans(db.Trans.M0, 0, -8000)))
    return layout


def test_route(layout, name, rule, dirty, coupled=False):
    route = layout.create_cell(name)
    def box(layer, coords):
        route.shapes(layout.layer(layer, 0)).insert(db.Box(*coords))
    anchors = []
    if rule.endswith('W.1') and rule != 'V1.W.1':
        layer = 19 if rule == 'M1.W.1' else 20
        polygon = db.Region(db.Box(0, 0, 96, 400))
        if dirty:
            polygon -= db.Region(db.Box(0, 100, 24, 300))
            polygon -= db.Region(db.Box(72, 100, 96, 300))
        route.shapes(layout.layer(layer, 0)).insert(polygon)
        anchors = [{'layer': [layer, 0], 'box_dbu': [0, 0, 96, 24]},
                   {'layer': [layer, 0], 'box_dbu': [0, 376, 96, 400]}]
    elif rule == 'M1.S.1':
        box(19, (0, 0, 240, 400))
        x = 288 if dirty else 320
        box(19, (x, 0, x+240, 400))
    elif rule == 'M1.A.1':
        box(19, (0, 0, 48 if dirty and coupled else 72, 96 if dirty else 128))
    elif rule == 'V1.W.1':
        box(21, (0, 0, 48 if dirty else 72, 72))
        box(20, (-28, -28, 100, 100))
    else:
        cap = 8 if dirty else 28
        box(21, (0, 0, 72, 72))
        box(20, (0, -cap, 72, 72+cap))
    if coupled:
        box(30, (1000, 0, 1048 if dirty else 1096, 400))
    return route, anchors


def qualify_case(root, case_id, level, kind, source_group, legal, dirty, policy, scope, source, metrics, mutation):
    published = Path(root)
    root = published/'.staging'/case_id
    profile = DRCProfileManager().get_profile(PROFILE)
    relative = f'cases/{case_id}.gds'; reference = f'oracle/{case_id}.reference.gds'
    save_layout(legal, root/reference); save_layout(dirty, root/relative)
    # Validate the serialized artifacts, including GDS polygon/box normalization.
    legal, dirty = load_layout(root/reference), load_layout(root/relative)
    ref_report, case_report = f'oracle/{case_id}.reference.lyrdb', f'oracle/{case_id}.lyrdb'
    clean = run_checker(root/reference, profile, root/ref_report)
    observed = run_checker(root/relative, profile, root/case_report)
    left, right = scoped_records(clean, scope), scoped_records(observed, scope)
    target = added_records(left, right)
    intended = set(mutation.get('target_rules', [mutation.get('constructor')])) - {None}
    if any(r['rule'] in intended for r in left):
        raise ValueError(f'{case_id}: source target region is not clean: {sorted({r["rule"] for r in left})}')
    if kind == 'clean_control' and target:
        raise ValueError('Clean control has target markers')
    if kind != 'clean_control' and not target:
        raise ValueError('Mutation has no checker-observed target markers')
    if kind != 'clean_control' and not intended <= {r['rule'] for r in target}:
        raise ValueError('Mutation did not trigger the intended checker categories')
    if level == 5 and kind == 'repair' and len({r['rule'] for r in target}) < 2:
        raise ValueError('L5 requires coupled rule categories')
    errors = validate_edit_policy(dirty, legal, policy)
    if kind != 'no_edit' and errors:
        raise ValueError(f'Reference repair fails the policy: {errors}')
    if kind == 'no_edit' and not errors:
        raise ValueError('Read-only challenge permits its reference repair')
    context = policy_context(root/relative, policy)
    # References and mutation records are evaluator-only files.
    evidence = {'reference_gds': reference, 'reference_sha256': sha256(root/reference),
                'recipe_hashes': recipe_hashes(), 'deck_sha256': sha256(profile.deck_path),
                'reference_report': ref_report, 'reference_report_sha256': sha256(root/ref_report),
                'input_report': case_report, 'input_report_sha256': sha256(root/case_report),
                'native_markers': json.loads(json.dumps(marker_records(clean))),
                'target_scope_rules': sorted(intended),
                'input_markers': json.loads(json.dumps(marker_records(observed))),
                'target_markers': target, 'mutation': mutation,
                'reference_policy_errors': errors, 'canonical_geometry_sha256': canonical_digest(dirty)}
    case = Case(case_id, level, kind, source_group, relative, sha256(root/relative), policy.to_dict(),
                scope, evidence, {**metrics, 'context_shapes': context['shape_count'],
                                 'protected_obstacle_count': sum(not s['editable'] for s in context['shapes']),
                                 'editable_shape_count': sum(s['editable'] for s in context['shapes']),
                                 'target_markers': len(target), 'coupled_rules': len({r['rule'] for r in target})}, source)
    for path in (relative, reference, ref_report, case_report):
        destination = published/path; destination.parent.mkdir(parents=True, exist_ok=True)
        (root/path).replace(destination)
    write_json(published/f'oracle/{case_id}.case.json', case.to_dict())
    return case


def generate_cells(root, library_path, qualification_path):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    qualification = json.loads(Path(qualification_path).read_text())
    profile = DRCProfileManager().get_profile(PROFILE)
    if not qualification['passed'] or qualification['deck_sha256'] != sha256(profile.deck_path):
        raise ValueError('Rule qualification is missing, failed, or stale')
    manifest = Manifest(deck_sha256=sha256(profile.deck_path), qualification_sha256=sha256(qualification_path))
    write_json(root/'qualification.json', qualification)
    manifest.qualification_sha256 = sha256(root/'qualification.json')
    rules = [['M1.W.1', 'M1.S.1', 'V1.W.1'], ['M2.W.1', 'M1.A.1', 'V1.M2.EN.2']]
    rejections = []
    for level in (1, 2):
        for group in range(2):
            for slot, kind in enumerate(('repair', 'repair', 'repair', 'clean_control', 'no_edit')):
                case_id = f'l{level}_g{group}_c{slot}'
                try:
                    variants = []
                    anchors = []
                    for dirty in (False, kind != 'clean_control'):
                        layout = cell_source(library_path, level, group)
                        route, anchors = test_route(layout, 'SIGNAL_ROUTE', rules[group][slot % 3], dirty, level == 2)
                        # Place above the cell row, retaining real obstacles in the inspection halo.
                        trans = db.Trans(db.Trans.R90 if level == 2 and group else db.Trans.R0,
                                         300+slot*8000, 1452+group*40)
                        if level == 2:
                            parent = layout.create_cell('ROUTE_INSTANCE')
                            parent.insert(db.CellInstArray(route.cell_index(), db.Trans()))
                            layout.cell('BENCHMARK_TOP').insert(db.CellInstArray(parent.cell_index(), trans))
                        else:
                            layout.cell('BENCHMARK_TOP').insert(db.CellInstArray(route.cell_index(), trans))
                        variants.append(layout)
                    legal, dirty = variants
                    bounds = legal.cell('SIGNAL_ROUTE').bbox().transformed(trans)
                    scope = [v*legal.dbu for v in (bounds.left-12, bounds.bottom-12, bounds.right+12, bounds.top+12)]
                    window = [scope[0]-.16, scope[1]-.16, scope[2]+.16, scope[3]+.16]
                    local = legal.cell('SIGNAL_ROUTE').bbox().enlarged(64)
                    permissions = {} if kind == 'no_edit' else {'SIGNAL_ROUTE': {
                        'layers': [[19, 0], [20, 0], [21, 0], [30, 0]],
                        'box_dbu': [local.left, local.bottom, local.right, local.top], 'anchors': anchors}}
                    policy = EditPolicy(permissions, [window])
                    metrics = layout_metrics(legal)
                    if level == 2 and not 64 <= metrics['instance_count'] <= 256:
                        raise ValueError('L2 instance count outside the declared range')
                    source = {'kind': 'real_asap7_cells', 'library_sha256': sha256(library_path),
                              'families': ['INV', 'BUF', 'NAND', 'NOR', 'DFF'], 'units_verified': True}
                    case = qualify_case(root, case_id, level, kind, f'l{level}_source_{group}', legal, dirty, policy,
                                        scope, source, metrics, {'constructor': rules[group][slot % 3], 'slot': slot, 'coupled': level == 2})
                    manifest.cases.append(case)
                except Exception as exc:
                    rejections.append({'case_id': case_id, 'reason': str(exc)})
    write_json(root/'rejections.json', rejections)
    for level in (1, 2):
        if sum(c.level == level for c in manifest.cases) != 10:
            manifest.blocked.append({'level': level, 'reason': 'One or more cell cases failed qualification'})
    manifest.blocked += [{'level': level, 'reason': 'Routed sources not yet imported'} for level in (3, 4, 5)]
    write_json(root/'manifest.json', manifest.to_dict())
    return manifest
