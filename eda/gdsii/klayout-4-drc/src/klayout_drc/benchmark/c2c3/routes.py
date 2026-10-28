"""Read route ownership from DEF properties, checked against an ODB net catalog."""
import json
from pathlib import Path
import re
import klayout.db as db
from .generator import load_layout


def explicit_def_vias(text, net_names, via_names):
    """Decode only supported explicit via statements in regular NETS."""
    section = re.search(r'^NETS\s+\d+\s*;(.*?)^END NETS', text, re.M | re.S)
    if section is None:
        return []
    result = []
    pattern = r'(?:\+\s+ROUTED|\bNEW)\s+\S+\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)'
    for statement in section.group(1).split(';'):
        header = re.match(r'\s*-\s+(\S+)', statement)
        if not header or header.group(1) not in net_names:
            continue
        for match in re.finditer(pattern, statement):
            cell_name = 'VIA_'+match.group(3)
            if cell_name not in via_names:
                continue
            tail = statement[match.end():].lstrip()
            if tail and tail.split()[0] not in ('NEW', '+', 'N'):
                continue
            result.append((header.group(1), cell_name, int(match.group(1)), int(match.group(2))))
    return result


def read_routes(gds_path, def_path, nets_path, platform):
    platform = Path(platform)
    catalog = json.loads(Path(nets_path).read_text())
    if catalog.get('schema_version') != 1 or catalog.get('dbu_per_um', 0) <= 0:
        raise ValueError('Missing trusted ODB unit/net catalog')
    source = load_layout(gds_path)
    if source.dbu != .00025:
        raise ValueError('Unverified merged GDS units')
    technology = db.Technology()
    technology.load(str(platform/'KLayout/asap7.lyt'))
    options = technology.load_layout_options
    config = options.lefdef_config
    config.lef_files = [str((platform/'lef/asap7_tech_1x_201209.lef').resolve()),
                        str((platform/'lef/asap7sc7p5t_28_R_1x_220121a.lef').resolve())]
    config.dbu = source.dbu
    config.net_property_name = 1
    config.instance_property_name = 2
    config.pin_property_name = 3
    options.lefdef_config = config
    routed = db.Layout(); routed.read(str(def_path), options)
    if routed.dbu != source.dbu:
        raise ValueError('DEF/GDS grid conversion mismatch')
    net_names = {n['name']: n for n in catalog['nets']}
    for net in catalog['nets']:
        touches_cts = any('clkbuf' in term[0].lower() for term in net['iterms'])
        protected = (net['signal_type'].upper() != 'SIGNAL' or net.get('clock_terminal') or
                     re.search(r'clk|clock|cts|vdd|vss', net['name'], re.I))
        if touches_cts and not protected:
            raise ValueError('Clock classification is incomplete for a CTS-connected net')
    catalog['clock_protection_verified'] = True
    # KLayout's DEF reader creates VIA_ cells. Expand only these route primitives;
    # all standard-cell definitions and placements remain hierarchical and intact.
    via_names = {cell.name for cell in routed.each_cell() if cell.name.startswith('VIA_')}
    original_regions = {str(info): db.Region(source.top_cell().begin_shapes_rec(source.find_layer(info.layer, info.datatype))).merged()
                        for info in source.layer_infos()}
    original_top = source.top_cell()
    via_indices = {cell.cell_index() for cell in source.each_cell() if cell.name in via_names}
    for inst in list(original_top.each_inst()):
        if inst.cell_index in via_indices:
            inst.flatten()
    for idx in sorted(via_indices, reverse=True):
        cell = source.cell(idx)
        if cell is not None and cell.parent_cells() == 0:
            source.delete_cell(idx)
    for info in source.layer_infos():
        after = db.Region(original_top.begin_shapes_rec(source.find_layer(info.layer, info.datatype))).merged()
        if not (after ^ original_regions[str(info)]).is_empty():
            raise ValueError('Via expansion changed the real source geometry')
    owned = {}
    primitive_counts = {}
    for layer in ((20, 0), (30, 0), (21, 0), (25, 0)):
        idx = routed.find_layer(*layer)
        if idx is None: continue
        iterator = routed.top_cell().begin_shapes_rec(idx)
        while not iterator.at_end():
            shape = iterator.shape()
            name = shape.property(1)
            if name not in net_names:
                for element in reversed(list(iterator.path())):
                    candidate = element.inst().property(1)
                    if candidate in net_names:
                        name = candidate; break
            if name in net_names and (shape.is_box() or shape.is_polygon() or shape.is_path()):
                owned.setdefault((name, layer), db.Region()).insert(shape.polygon.transformed(iterator.itrans()))
                count = max(1, len(list(shape.path.each_point()))-1) if shape.is_path() else 1
                primitive_counts[(name, layer)] = primitive_counts.get((name, layer), 0) + count
            iterator.next()
    wire_counts = dict(primitive_counts)
    # KLayout attaches net properties to wires, but not to via instances.
    # Recover only explicitly named, unrotated vias from regular DEF NETS.
    # No ownership is assigned by proximity or GDS layer number.
    def_text = Path(def_path).read_text()
    via_count = 0
    for name, cell_name, x, y in explicit_def_vias(def_text, net_names, via_names):
        cell = routed.cell(cell_name)
        scale = 1/(catalog['dbu_per_um']*source.dbu)
        coordinates = [x*scale, y*scale]
        if any(abs(v-round(v)) > 1e-8 for v in coordinates):
            raise ValueError('DEF via coordinate is off the GDS grid')
        transform = db.Trans(*(round(v) for v in coordinates))
        via_count += 1
        for layer in ((20, 0), (30, 0), (21, 0), (25, 0)):
            index = routed.find_layer(*layer)
            if index is None: continue
            region = db.Region(cell.begin_shapes_rec(index)).transformed(transform)
            if region.is_empty(): continue
            owned.setdefault((name, layer), db.Region()).insert(region)
            primitive_counts[(name, layer)] = primitive_counts.get((name, layer), 0)+region.count()
    catalog['decoded_regular_net_via_instances'] = via_count
    accepted = []
    owned = {key: region.merged() for key, region in owned.items()}
    boxes = {key: region.bbox() for key, region in owned.items()}
    direct_by_layer = {}
    for layer in {key[1] for key in owned}:
        index = source.find_layer(*layer)
        direct_by_layer[layer] = db.Region(source.top_cell().shapes(index)).merged() if index is not None else db.Region()
    for (name, layer), region in sorted(owned.items()):
        record = net_names[name]
        # Clock/power catalog entries and conservatively named CTS routes are immutable.
        if record['signal_type'].upper() != 'SIGNAL' or record.get('clock_terminal') or re.search(r'clk|clock|cts|vdd|vss', name, re.I):
            continue
        direct = direct_by_layer[layer]
        if not (region-direct).is_empty():
            continue
        bounds = boxes[(name, layer)]
        ambiguous = any(other_name != name and other_layer == layer and bounds.overlaps(boxes[(other_name, other_layer)])
                        and not (region & other_region).is_empty()
                        for (other_name, other_layer), other_region in owned.items())
        if ambiguous: continue
        accepted.append({'net': name, 'layer': list(layer), 'region': region, 'net_record': record,
                         'decoded_route_primitives': primitive_counts[(name, layer)],
                         'route_segments': wire_counts.get((name, layer), 0)})
    if not accepted:
        raise ValueError('No unambiguous DEF-owned signal geometry matches merged GDS top-level routes')
    # LEF/DEF source units must agree with the ODB export, not with a guessed scale.
    units = re.search(r'UNITS\s+DISTANCE\s+MICRONS\s+(\d+)', Path(def_path).read_text())
    if units is None or int(units.group(1)) != catalog['dbu_per_um']:
        raise ValueError('DEF/ODB units disagree')
    return source, accepted, catalog


def local_occupancy(layout, box_um, layers=((20, 0), (30, 0))):
    box = db.Box(*(round(v/layout.dbu) for v in box_um))
    mask = db.Region(box)
    if box.area() <= 0: raise ValueError('Empty occupancy window')
    area = 0; polygons = 0
    for layer in layers:
        idx = layout.find_layer(*layer)
        if idx is not None:
            region = db.Region(layout.top_cell().begin_shapes_rec(idx)).merged() & mask
            area += region.area(); polygons += region.count()
    return {'local_routing_occupancy': area/(box.area()*len(layers)), 'local_route_polygons': polygons,
            'occupancy_layers': [list(layer) for layer in layers], 'occupancy_box_um': box_um}
