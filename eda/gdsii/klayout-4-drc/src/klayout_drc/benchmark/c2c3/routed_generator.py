"""Qualify controlled changes to real DEF-owned, merged-GDS signal routes."""
import json
from dataclasses import replace
from pathlib import Path
import klayout.db as db
from .contracts import IMAGE, ORFS_COMMIT, Case, Manifest, safe_path, sha256, write_json
from .generator import load_layout, save_layout, qualify_case, layout_metrics, recipe_hashes, canonical_digest
from .routes import read_routes, local_occupancy
from ...edit_policy import EditPolicy
from ...profile import DRCProfileManager
from ..acceptance import run_checker


def verified_bundle(directory):
    directory = Path(directory).resolve()
    build = json.loads((directory/'build.json').read_text())
    if build.get('status') != 'complete' or build.get('orfs_commit') != ORFS_COMMIT or build.get('image') != IMAGE:
        raise ValueError('Source build is incomplete or uses a different ORFS revision')
    for relative, digest in build['artifacts'].items():
        if sha256(safe_path(directory, relative)) != digest:
            raise ValueError(f'Changed routed source artifact: {relative}')
    for suffix in ('gds', 'def', 'odb', 'v', 'sdc'):
        safe_path(directory, build['final'][suffix])
    nets = directory/'nets.json'
    if not nets.exists() or build.get('nets_sha256') != sha256(nets):
        raise ValueError('Missing or changed ODB net catalog')
    return build


def segments(region):
    """Return legal-width rectangle interiors in deterministic physical order."""
    candidates = []
    for pair in region.width_check(97).each():
        box = pair.bbox()
        if min(box.width(), box.height()) < 72 or max(box.width(), box.height()) < 240:
            continue
        if not (db.Region(box)-region).is_empty():
            continue
        candidates.append(box)
    return sorted(candidates, key=lambda b: (b.left, b.bottom, b.right, b.top))


def notch(box):
    if box.height() > box.width():
        mid = round((box.bottom+box.top)/8)*4
        return db.Box(box.left, mid-40, box.left+16, mid+40)
    mid = round((box.left+box.right)/8)*4
    return db.Box(mid-40, box.bottom, mid+40, box.bottom+16)


def cut_for(item, box):
    return item.get('cut_box', notch(box))


def neighborhood_shape_count(layout, cut):
    """Rank real obstacles in the same fixed physical window used by the prompt."""
    window = cut.enlarged(440)  # 120 DBU scope halo plus 80 nm inspection halo.
    total = 0
    mask = db.Region(window)
    for layer in ((19, 0), (20, 0), (21, 0), (25, 0), (30, 0)):
        index = layout.find_layer(*layer)
        if index is None: continue
        iterator = layout.top_cell().begin_shapes_rec_overlapping(index, window)
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_box() or shape.is_polygon() or shape.is_path():
                polygon = shape.polygon.transformed(iterator.itrans())
                if not (db.Region(polygon) & mask).is_empty(): total += 1
            iterator.next()
    return total


def generate_routed(root, bundle_specs, platform):
    root = Path(root); manifest = Manifest.load(root/'manifest.json')
    manifest.cases = [c for c in manifest.cases if c.level < 3]
    manifest.blocked = [b for b in manifest.blocked if b['level'] < 3]
    rejections = json.loads((root/'rejections.json').read_text())
    source_geometries = set()
    for spec in bundle_specs:
        level, group = spec['level'], spec['group']
        directory = Path(spec['build_dir']).resolve()
        try:
            build = verified_bundle(directory)
            if level not in (3, 4, 5) or group not in (0, 1):
                raise ValueError('Invalid routed source level/group')
            if build['design'] != ('gcd' if level == 3 else 'uart'):
                raise ValueError('Wrong design for the declared level')
            source, routes, catalog = read_routes(directory/build['final']['gds'], directory/build['final']['def'], directory/'nets.json', platform)
            fingerprint = (level, canonical_digest(source))
            if fingerprint in source_geometries:
                raise ValueError('Source groups have identical canonical geometry')
            source_geometries.add(fingerprint)
            public_profile = DRCProfileManager().get_profile('asap7_public_full')
            audit_relative = f'oracle/l{level}_g{group}.native_public.lyrdb'
            audit = run_checker(directory/build['final']['gds'], public_profile, root/audit_relative)
            native_audit = {'profile': public_profile.name, 'deck_sha256': sha256(public_profile.deck_path),
                            'counts': audit.rule_summary, 'report': audit_relative,
                            'report_sha256': sha256(root/audit_relative), 'acceptance_gate': False,
                            'frame': 'original routed hierarchy; diagnostic only'}
            prepared = root/f'oracle/l{level}_g{group}.prepared_source.gds'
            save_layout(source, prepared)
            by_net = {}
            for item in routes: by_net.setdefault(item['net'], []).append(item)
            candidates = []
            for net, items in sorted(by_net.items()):
                if level == 5:
                    # Both failures share the same M2 geometry: a thin bridge at
                    # a V2 landing breaks width and opposite-side enclosure.
                    lowers = [i for i in items if i['layer'] == [20, 0]]
                    for via in (i for i in items if i['layer'] == [25, 0]):
                        for polygon in via['region'].each():
                            if not polygon.is_box(): continue
                            b = polygon.bbox()
                            cuts = [db.Box(b.left+4, b.top+4, b.right, b.top+20),
                                    db.Box(b.right+4, b.bottom+4, b.right+20, b.top),
                                    db.Box(b.left+4, b.bottom-20, b.right, b.bottom-4),
                                    db.Box(b.left-20, b.bottom+4, b.left-4, b.top)]
                            for lower in lowers:
                                for cut in cuts:
                                    if (db.Region(cut) & lower['region']).is_empty(): continue
                                    item = {**lower, 'cut_box': cut, 'target_rules': ['M2.W.1', 'V2.M2.EN.1']}
                                    candidates.append((net, items, [(item, b)]))
                    continue
                choices = [(item, box) for item in items for box in segments(item['region'])]
                for item, box in choices:
                    selected = [(item, box)]
                    candidates.append((net, items, selected))
                for via in (i for i in items if i['layer'] == [25, 0]):
                    for polygon in via['region'].each():
                        if not polygon.is_box(): continue
                        b = polygon.bbox()
                        if b.width() < 72 or b.height() < 72: continue
                        item = {**via, 'cut_box': db.Box(b.right-16, b.bottom, b.right, b.top), 'target_rules': ['V2.W.1']}
                        candidates.append((net, items, [(item, b)]))
            if level == 4:
                ranked = [(neighborhood_shape_count(source, cut_for(selected[0][0], selected[0][1])), index, value)
                          for index, value in enumerate(candidates) for net, items, selected in [value]]
                candidates = [value for _, _, value in sorted(ranked, key=lambda row: (-row[0], row[1]))]
            used = set(); accepted = 0
            for slot, kind in enumerate(('repair', 'repair', 'repair', 'clean_control', 'no_edit')):
                case_id = f'l{level}_g{group}_c{slot}'
                checkpoint = root/f'oracle/{case_id}.case.json'
                if checkpoint.exists():
                    cached = Case(**json.loads(checkpoint.read_text()))
                    if (cached.evidence.get('recipe_hashes') == recipe_hashes() and
                            cached.evidence.get('deck_sha256') == manifest.deck_sha256 and
                            cached.source.get('build_sha256') == sha256(directory/'build.json') and
                            sha256(root/cached.gds) == cached.gds_sha256):
                        cached = replace(cached, source={**cached.source, 'native_public_audit': native_audit})
                        write_json(checkpoint, cached.to_dict())
                        manifest.cases.append(cached)
                        used.add(cached.evidence['mutation']['candidate_index'])
                        continue
                case_accepted = False
                for number, (net, items, selected) in enumerate(candidates):
                    if number in used: continue
                    if number > 400: break
                    if level in (3, 4) and kind == 'repair' and selected[0][0]['layer'][0] != (20, 30, 25)[slot]:
                        continue
                    try:
                        # Re-read the complete source. Reparent only proven top-level signal geometry.
                        legal = load_layout(prepared)
                        top = legal.top_cell(); route = legal.create_cell(f'EDIT_ROUTE_{slot}')
                        for item in items:
                            idx = legal.layer(*item['layer'])
                            background = db.Region(top.shapes(idx))-item['region']
                            top.shapes(idx).clear(); top.shapes(idx).insert(background)
                            route.shapes(idx).insert(item['region'])
                        top.insert(db.CellInstArray(route.cell_index(), db.Trans()))
                        for info in source.layer_infos():
                            old_idx = source.find_layer(info.layer, info.datatype)
                            new_idx = legal.find_layer(info.layer, info.datatype)
                            old_region = db.Region(source.top_cell().begin_shapes_rec(old_idx)).merged()
                            new_region = db.Region(top.begin_shapes_rec(new_idx)).merged()
                            if not (old_region ^ new_region).is_empty():
                                raise ValueError('Route partition changed merged source geometry')
                        bounds = db.Box()
                        for item, box in selected: bounds += cut_for(item, box).enlarged(120)
                        scope = [v*legal.dbu for v in (bounds.left, bounds.bottom, bounds.right, bounds.top)]
                        window = [scope[0]-.08, scope[1]-.08, scope[2]+.08, scope[3]+.08]
                        anchors = []
                        for item, box in selected:
                            if box.height() > box.width():
                                anchor = db.Box(box.left, box.bottom, box.right, box.bottom+8)
                            else: anchor = db.Box(box.left, box.bottom, box.left+8, box.top)
                            anchors.append({'layer': item['layer'], 'box_dbu': [anchor.left, anchor.bottom, anchor.right, anchor.top]})
                        permissions = {} if kind == 'no_edit' else {route.name: {'layers': [i['layer'] for i in items],
                            'box_dbu': [bounds.left, bounds.bottom, bounds.right, bounds.top], 'anchors': anchors, 'net_owner': net}}
                        policy = EditPolicy(permissions, [window])
                        temp = root/'oracle/route_work.gds'; save_layout(legal, temp); dirty = load_layout(temp)
                        if kind != 'clean_control':
                            for item, box in selected:
                                idx = dirty.layer(*item['layer']); cell = dirty.cell(route.name)
                                changed = db.Region(cell.shapes(idx))-db.Region(cut_for(item, box))
                                cell.shapes(idx).clear(); cell.shapes(idx).insert(changed)
                        metrics = {**layout_metrics(legal), **local_occupancy(legal, window),
                                   'route_segment_count': sum(i['route_segments'] for i in routes),
                                   'decoded_route_primitive_count': sum(i['decoded_route_primitives'] for i in routes),
                                   'via_count': catalog['decoded_regular_net_via_instances']}
                        if level == 5:
                            baseline_directory = Path(spec['matched_baseline_dir'])
                            original = verified_bundle(baseline_directory)
                            baseline_layout = load_layout(baseline_directory/original['final']['gds'])
                            occupancy = local_occupancy(baseline_layout, window)['local_routing_occupancy']
                            if occupancy <= 0 or metrics['local_routing_occupancy'] < 1.25*occupancy:
                                raise ValueError('L5 local occupancy is not 25% above the matched L4 source')
                            metrics['matched_l4_occupancy'] = occupancy
                        source_meta = {'kind': 'routed_asap7', 'design': build['design'], 'orfs_commit': ORFS_COMMIT,
                                       'image': build['image'], 'build_sha256': sha256(directory/'build.json'),
                                       'net_catalog_sha256': sha256(directory/'nets.json'),
                                       'source_gds_sha256': sha256(directory/build['final']['gds']),
                                       'clock_protection_verified': catalog['clock_protection_verified'],
                                       'native_public_audit': native_audit,
                                       'units_verified': True, 'net_owner_source': 'DEF properties checked against ODB catalog'}
                        intended = sorted({rule for item, _ in selected for rule in item.get('target_rules',
                                           ['M2.W.1' if item['layer'][0] == 20 else 'M3.W.1'])})
                        case = qualify_case(root, case_id, level, kind, f'l{level}_source_{group}', legal, dirty, policy,
                                            scope, source_meta, metrics, {'net': net, 'candidate_index': number,
                                            'target_rules': intended, 'cuts_dbu': [cut_for(i, b).to_s() for i, b in selected]})
                        manifest.cases.append(case); used.add(number); accepted += 1; case_accepted = True
                        write_json(root/'generation_progress.json', {'accepted': [c.case_id for c in manifest.cases], 'complete': False})
                        break
                    except Exception as exc:
                        rejections.append({'case_id': case_id, 'candidate': number, 'reason': str(exc)})
                        write_json(root/'rejections.json', rejections)
                if not case_accepted:
                    rejections.append({'case_id': case_id, 'reason': 'No eligible route candidate passed qualification'})
        except Exception as exc:
            manifest.blocked.append({'level': level, 'group': group, 'reason': str(exc)})
    for level in (3, 4, 5):
        if sum(c.level == level for c in manifest.cases) != 10:
            manifest.blocked.append({'level': level, 'reason': 'Fewer than ten qualified routed cases'})
    level3 = [c.metrics for c in manifest.cases if c.level == 3]
    for case in manifest.cases:
        if case.level == 4 and level3 and not (case.metrics['instance_count'] > max(m['instance_count'] for m in level3)
                and case.metrics['route_segment_count'] > max(m['route_segment_count'] for m in level3)):
            manifest.blocked.append({'level': 4, 'reason': 'UART is not more complex than GCD in the measured metrics'})
            break
    from statistics import median
    low = [c.metrics['protected_obstacle_count'] for c in manifest.cases if c.level == 3 and c.kind == 'repair']
    high = [c.metrics['protected_obstacle_count'] for c in manifest.cases if c.level == 4 and c.kind == 'repair']
    if low and high and median(high) <= median(low):
        manifest.blocked.append({'level': 4, 'reason': 'Median protected-neighbor count does not exceed L3'})
    write_json(root/'rejections.json', rejections); write_json(root/'manifest.json', manifest.to_dict())
    return manifest


def congestion_score(gds_path, bin_um=1.):
    """Maximum M2/M3 metal occupancy on a fixed physical bin size."""
    import math
    layout = load_layout(gds_path); top = layout.top_cell(); bounds = top.bbox()
    step = round(bin_um/layout.dbu)
    regions = []
    for layer in ((20, 0), (30, 0)):
        index = layout.find_layer(*layer)
        regions.append(db.Region(top.begin_shapes_rec(index)).merged() if index is not None else db.Region())
    best = {'maximum_bin_occupancy': 0., 'bin_um': bin_um, 'layers': [[20, 0], [30, 0]]}
    for x in range(bounds.left, bounds.right, step):
        for y in range(bounds.bottom, bounds.top, step):
            box = db.Box(x, y, x+step, y+step); mask = db.Region(box)
            occupancy = sum((r & mask).area() for r in regions)/(2*box.area())
            if occupancy > best['maximum_bin_occupancy']:
                best.update(maximum_bin_occupancy=occupancy, bin_dbu=[box.left, box.bottom, box.right, box.top])
    return best


def select_sources(root, output):
    """Select from all planned builds using fresh geometry measurements."""
    root = Path(root).resolve(); specs, selection = [], []
    bases = {}
    for level, design in ((3, 'gcd'), (4, 'uart')):
        for group in (0, 1):
            choices = []
            for directory in (root/'builds').glob(f'{design}_g{group}*'):
                if '_stress_' in directory.name: continue
                try:
                    build = verified_bundle(directory)
                    attempt = int(directory.name.rsplit('_attempt', 1)[1]) if '_attempt' in directory.name else 1
                    choices.append((attempt, directory, build))
                except (ValueError, OSError, KeyError):
                    continue
            if not choices:
                raise ValueError(f'Missing complete {design} source group {group}')
            _, directory, build = max(choices, key=lambda item: item[0])
            bases[(level, group)] = directory
            specs.append({'level': level, 'group': group, 'build_dir': str(directory)})
    for group in (0, 1):
        candidates, rows = [], []
        for factor in (1., .9, .8):
            try:
                directories = sorted((root/'builds').glob(f'uart_g{group}_stress_{factor:.2f}*'),
                                     key=lambda p: int(p.name.rsplit('_attempt', 1)[1]) if '_attempt' in p.name else 1, reverse=True)
                eligible = []
                for path in directories:
                    try:
                        candidate_build = verified_bundle(path)
                        if group == 1 and candidate_build.get('source_parameters', {}).get('data_width') != 12:
                            continue
                        eligible.append((path, candidate_build))
                    except (ValueError, OSError, KeyError):
                        continue
                if not eligible:
                    raise ValueError(f'No complete matching stress build for factor {factor}')
                directory, build = eligible[0]
                if build.get('factor') != factor or build.get('density') != .75:
                    raise ValueError('Wrong stress configuration')
                score = congestion_score(directory/build['final']['gds'])
                candidates.append((score['maximum_bin_occupancy'], -factor, directory))
                rows.append({'factor': factor, 'status': 'complete', **score, 'build_sha256': sha256(directory/'build.json')})
            except (ValueError, OSError, KeyError) as exc:
                rows.append({'factor': factor, 'status': 'blocked', 'reason': str(exc)})
        if candidates:
            _, _, directory = max(candidates, key=lambda row: (row[0], row[1]))
            specs.append({'level': 5, 'group': group, 'build_dir': str(directory),
                          'matched_baseline_dir': str(bases[(4, group)])})
        selection.append({'group': group, 'trials': rows, 'selected': str(directory) if candidates else None})
    write_json(output, specs)
    write_json(Path(output).with_name('stress_selection.json'), selection)
    return specs
