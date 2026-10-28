"""Case-specific geometry permissions. These checks do not prove connectivity."""
from dataclasses import asdict, dataclass, field
import json
import klayout.db as db


class ContextIncomplete(ValueError):
    """Required local geometry does not fit the declared context budget."""


@dataclass(frozen=True)
class EditPolicy:
    editable_cells: dict = field(default_factory=dict)
    windows_um: list = field(default_factory=list)
    context_layers: list = field(default_factory=lambda: [[19, 0], [20, 0], [21, 0], [25, 0], [30, 0]])
    max_context_shapes: int = 1024
    schema_version: int = 1
    grid_dbu: int = 4

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        result = cls(**value)
        if result.schema_version != 1 or not 1 <= result.max_context_shapes <= 10000 or result.grid_dbu < 1:
            raise ValueError('Unsupported edit policy or context budget')
        if not result.windows_um or any(len(w) != 4 or w[0] >= w[2] or w[1] >= w[3] for w in result.windows_um):
            raise ValueError('Policy requires nonempty inspection windows')
        for name, rule in result.editable_cells.items():
            if not name or not rule.get('layers') or len(rule.get('box_dbu', [])) != 4:
                raise ValueError('Editable cell requires layers and a local DBU region')
            box = rule['box_dbu']
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError('Empty edit region')
        return result


def direct_region(layout, cell, layer):
    index = layout.find_layer(*layer)
    return db.Region(cell.shapes(index)).merged() if index is not None else db.Region()


def _instances(layout, cell):
    return sorted((layout.cell(i.cell_index).name, str(i.cplx_trans), str(i.a), str(i.b), i.na, i.nb,
                   str(i.properties())) for i in cell.each_inst())


def _obstacles(layout, layer, excluded):
    result = db.Region()
    index = layout.find_layer(*layer)
    if index is None:
        return result
    iterator = layout.top_cell().begin_shapes_rec(index)
    while not iterator.at_end():
        if iterator.cell().name not in excluded:
            shape = iterator.shape()
            if shape.is_box() or shape.is_polygon() or shape.is_path():
                result.insert(shape.polygon.transformed(iterator.itrans()))
        iterator.next()
    return result.merged()


def validate_edit_policy(before, after, policy):
    """Compare all definitions, placements, local masks, anchors and obstacles."""
    from .validator import _cell_content
    policy = EditPolicy.from_dict(policy) if isinstance(policy, dict) else policy
    errors = []
    if before.dbu != after.dbu:
        return ['Edit policy: database units changed']
    names = {c.name for c in before.each_cell()}
    if names != {c.name for c in after.each_cell()}:
        return ['Edit policy: cell definitions added or removed']
    if before.top_cell().name != after.top_cell().name:
        return ['Edit policy: top cell changed']
    layers = {(i.layer, i.datatype) for layout in (before, after) for i in layout.layer_infos()}
    placements = {}
    def walk(cell, multiplicity=1):
        for inst in cell.each_inst():
            child = before.cell(inst.cell_index)
            count = multiplicity * max(1, inst.na) * max(1, inst.nb)
            placements[child.name] = placements.get(child.name, 0) + count
            walk(child, count)
    walk(before.top_cell())
    for name in policy.editable_cells:
        if placements.get(name) != 1:
            errors.append(f'Edit policy: editable route is not instance-specific: {name}')
    for name in sorted(names):
        a, b = before.cell(name), after.cell(name)
        if _instances(before, a) != _instances(after, b):
            errors.append(f'Edit policy: instance definitions changed in {name}')
        if a.properties() != b.properties():
            errors.append(f'Edit policy: cell properties changed in {name}')
        rule = policy.editable_cells.get(name)
        if rule is None:
            if _cell_content(before, a) != _cell_content(after, b):
                errors.append(f'Edit policy: protected cell changed: {name}')
            continue
        mask = db.Region(db.Box(*rule['box_dbu']))
        for layer in sorted(layers):
            left, right = direct_region(before, a, layer), direct_region(after, b, layer)
            delta = left ^ right
            if delta.is_empty():
                continue
            for polygon in delta.each():
                points = list(polygon.each_point_hull())
                points += [p for h in range(polygon.holes()) for p in polygon.each_point_hole(h)]
                if any(p.x % policy.grid_dbu or p.y % policy.grid_dbu for p in points):
                    errors.append(f'Edit policy: changed geometry is off the manufacturing grid: {name} {layer}')
                    break
            if list(layer) not in rule['layers'] or not (delta - mask).is_empty():
                errors.append(f'Edit policy: change outside allowed layer/region: {name} {layer}')
            if left.count() != right.count() or (not left.is_empty() and right.is_empty()):
                errors.append(f'Edit policy: route component removed or joined: {name} {layer}')
            for anchor in rule.get('anchors', []):
                if anchor['layer'] == list(layer) and not (delta & db.Region(db.Box(*anchor['box_dbu']))).is_empty():
                    errors.append(f'Edit policy: fixed route anchor changed: {name} {layer}')
            # Exactly one placement is required for each editable route cell.
            transforms = []
            idx = before.find_layer(*layer)
            if idx is not None:
                iterator = before.top_cell().begin_shapes_rec(idx)
                while not iterator.at_end():
                    if iterator.cell().name == name:
                        trans = iterator.itrans()
                        if str(trans) not in [str(t) for t in transforms]:
                            transforms.append(trans)
                    iterator.next()
            if len(transforms) != 1:
                errors.append(f'Edit policy: editable route is not instance-specific: {name}')
                continue
            obstacles = _obstacles(before, layer, {name})
            old_overlap = left.transformed(transforms[0]) & obstacles
            new_overlap = right.transformed(transforms[0]) & obstacles
            if not (new_overlap - old_overlap).is_empty():
                errors.append(f'Edit policy: new overlap with protected geometry: {name} {layer}')
        # Texts and properties are immutable even in editable route cells.
        for info in layers:
            def metadata(layout, cell):
                idx = layout.find_layer(*info)
                return sorted((s.to_s(), str(s.properties())) for s in cell.shapes(idx).each()
                              if s.is_text() or s.properties()) if idx is not None else []
            if metadata(before, a) != metadata(after, b):
                errors.append(f'Edit policy: route metadata changed: {name}')
    for name in policy.editable_cells:
        if name not in names:
            errors.append(f'Edit policy: missing editable route cell: {name}')
    return errors


def policy_context(gds_path, policy):
    """Return complete relevant geometry, with paths and top-level transforms."""
    policy = EditPolicy.from_dict(policy) if isinstance(policy, dict) else policy
    layout = db.Layout()
    layout.read(str(gds_path))
    shapes, seen = [], set()
    for window in policy.windows_um:
        box = db.Box(*(round(v / layout.dbu) for v in window))
        for layer in sorted(policy.context_layers):
            idx = layout.find_layer(*layer)
            if idx is None:
                continue
            iterator = layout.top_cell().begin_shapes_rec_overlapping(idx, box)
            while not iterator.at_end():
                shape = iterator.shape()
                if shape.is_box() or shape.is_polygon() or shape.is_path():
                    polygon = shape.polygon.transformed(iterator.itrans())
                    path = [(layout.cell(e.cell_inst().cell_index).name, e.ia(), e.ib(),
                             str(e.specific_cplx_trans())) for e in iterator.path()]
                    item = {'cell': iterator.cell().name, 'instance_path': path,
                            'transform': str(iterator.itrans()), 'layer': layer,
                            'polygon_dbu': polygon.to_s(), 'polygon_local_dbu': shape.polygon.to_s(),
                            'editable': iterator.cell().name in policy.editable_cells}
                    key = json.dumps(item, sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        shapes.append(item)
                        if len(shapes) > policy.max_context_shapes:
                            raise ContextIncomplete(f'Required geometry exceeds {policy.max_context_shapes} shapes; no context was sent')
                iterator.next()
    shapes.sort(key=lambda x: (not x['editable'], x['layer'], x['cell'], str(x['instance_path']), x['polygon_dbu']))
    result = {'schema_version': 1, 'dbu_um': layout.dbu, 'top_cell': layout.top_cell().name,
            'coordinate_frame': 'polygon_dbu uses top-cell DBU; polygon_local_dbu and edit masks use named-cell DBU',
            'edit_policy': policy.to_dict(), 'shapes': shapes, 'shape_count': len(shapes),
            'omitted_required_shapes': 0, 'omitted_layers': [list((i.layer, i.datatype)) for i in layout.layer_infos()
                                                          if [i.layer, i.datatype] not in policy.context_layers]}
    if len(json.dumps(result)) > 120000:
        raise ContextIncomplete('Required geometry exceeds the 120000-character context budget')
    return result


def policy_report(report, policy_path):
    """Restrict flat C2+C3 observations to the public inspection windows."""
    from dataclasses import replace
    from pathlib import Path
    policy = EditPolicy.from_dict(json.loads(Path(policy_path).read_text()))
    def visible(item):
        boxes = [g.bbox_um for g in item.geometries if g.bbox_um is not None]
        if not boxes:
            raise ContextIncomplete('Cannot locate an untyped checker marker')
        return any(b[0] <= w[2] and b[2] >= w[0] and b[1] <= w[3] and b[3] >= w[1]
                   for b in boxes for w in policy.windows_um)
    categories = [replace(c, violations=[v for v in c.violations if visible(v)]) for c in report.categories]
    return replace(report, categories=[c for c in categories if c.violations])
