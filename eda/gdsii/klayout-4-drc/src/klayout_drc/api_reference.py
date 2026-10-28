"""Trusted, executable KLayout examples shared by prompts and runtime checks.

Only this package's fixed examples are executed. Markdown and candidate code
are never executed by reference validation.
"""
from dataclasses import asdict, dataclass
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import textwrap

import klayout.db as db

from .config import DRCConfigurationError


class APIReferenceError(DRCConfigurationError):
    """The installed runtime cannot execute the trusted API examples."""


@dataclass(frozen=True)
class APIExample:
    name: str
    notes: str
    code: str
    checks: str
    source: str


EXAMPLES = (
    APIExample('layout_io',
        'Layout.read/write change the layout/file. find_layer returns an existing layer index or None; '
        'layer(number, datatype) creates a layer if missing. shapes.clear/insert change that cell only. '
        'This replacement helper is for an explicitly editable FLAT cell, not protected masters or recursive geometry.',
        '''
def read_layout(input_gds):
    layout = db.Layout()
    layout.read(str(input_gds))
    tops = list(layout.top_cells())
    if len(tops) != 1:
        raise ValueError("Require one top cell")
    return layout, tops[0]

def replace_flat_layer(layout, top, layer_index, repaired_region, output_gds):
    top.shapes(layer_index).clear()
    top.shapes(layer_index).insert(repaired_region)
    layout.write(str(output_gds))
''', '''
original = db.Layout(); original.dbu = 0.00025
cell = original.create_cell('TOP'); index = original.layer(7, 3)
cell.shapes(index).insert(db.Box(0, 0, 40, 400))
input_path = work_dir/'input.gds'; output_path = work_dir/'output.gds'
original.write(str(input_path))
layout, top = read_layout(input_path)
index = layout.find_layer(7, 3)
assert index is not None and layout.find_layer(999, 0) is None
assert db.Region(top.shapes(index)).area() == 16000
assert layout.dbu == original.dbu
replace_flat_layer(layout, top, index, db.Region(db.Box(0, 0, 72, 400)), output_path)
saved, saved_top = read_layout(output_path)
assert db.Region(saved_top.shapes(saved.find_layer(7, 3))).area() == 28800
assert db.Region(original.top_cell().shapes(original.find_layer(7, 3))).area() == 16000
''', 'https://www.klayout.de/doc/code/class_Layout.html'),
    APIExample('units_and_grid',
        'layout.dbu is micrometers per integer DBU. 1 nm = 0.001 um; 1 nm2 = 0.000001 um2. '
        'Length / dbu gives DBU; area / dbu**2 gives DBU2. Round required lengths UP to the manufacturing grid. '
        'Do not use meters (1e-9) with layout.dbu. These helpers return numbers and do not change geometry.',
        '''
from decimal import Decimal, ROUND_CEILING

def length_on_grid(length_um, dbu_um, grid_um):
    length, dbu, grid = map(lambda x: Decimal(str(x)), (length_um, dbu_um, grid_um))
    if length < 0 or dbu <= 0 or grid <= 0:
        raise ValueError("Require nonnegative length and positive DBU/grid")
    grid_dbu = grid / dbu
    if grid_dbu != grid_dbu.to_integral_value():
        raise ValueError("Manufacturing grid must be an integer number of DBU")
    return int((length / grid).to_integral_value(rounding=ROUND_CEILING) * grid_dbu)

def area_in_um2(polygon, dbu_um):
    return polygon.area() * dbu_um**2
''', '''
assert length_on_grid(0.018, 0.00025, 0.00025) == 72
assert length_on_grid(0.0181, 0.00025, 0.0005) == 74
assert length_on_grid(0.018, 0.001, 0.001) == 18
assert length_on_grid(0, 0.001, 0.001) == 0
assert abs(area_in_um2(db.Polygon(db.Box(0, 0, 72, 112)), 0.00025) - 0.000504) < 1e-15
assert abs(area_in_um2(db.Polygon(db.Box(0, 0, 18, 28)), 0.001) - 0.000504) < 1e-15
''', 'https://www.klayout.de/doc/programming/database_api.html'),
    APIExample('polygon_iteration_and_area',
        'Region.each() yields raw PolygonWithProperties objects in 0.30.8; each_merged() yields connected '
        'merged polygons. Both are iterators, not lists. Polygon.area() returns DBU2 and accounts for holes. '
        'Evaluate a minimum-area rule per component, not by total layer area. These reads do not change the region. '
        'Region.each_polygon() does not exist. Polygon.inside(point) returns True for a point inside or '
        'on its boundary; a point in a hole is outside. Polygon.contains(point) does not exist.',
        '''
def component_areas(region):
    return [polygon.area() for polygon in region.each_merged()]

def raw_polygon_count(region):
    return sum(1 for polygon in region.each())

def polygon_contains_or_touches(polygon, point):
    return polygon.inside(point)
''', '''
with_hole = db.Region(db.Box(0, 0, 100, 100)) - db.Region(db.Box(25, 25, 75, 75))
separate = with_hole + db.Region(db.Box(200, 0, 210, 10))
assert sorted(component_areas(separate)) == [100, 7500]
assert raw_polygon_count(separate) == 2
polygon = next(with_hole.each())
assert polygon.holes() == 1 and polygon.area() == 7500
assert polygon_contains_or_touches(polygon, db.Point(0, 50))
assert polygon_contains_or_touches(polygon, db.Point(10, 10))
assert not polygon_contains_or_touches(polygon, db.Point(50, 50))
assert not polygon_contains_or_touches(polygon, db.Point(150, 50))
touching = db.Region(db.Box(0, 0, 10, 10)) + db.Region(db.Box(10, 0, 20, 10))
assert raw_polygon_count(touching) == 2 and component_areas(touching) == [200]
''', 'https://www.klayout.de/doc/code/class_Region.html'),
    APIExample('rectangle_measurement',
        'Polygon.is_box() is a bool. bbox() returns Box; width()/height() return integer DBU. '
        'min(bbox.width(), bbox.height()) measures transverse width ONLY for an axis-aligned rectangle. '
        'It is not a general polygon minimum-width algorithm. No geometry is changed.',
        '''
def rectangle_width(polygon):
    if not polygon.is_box():
        raise ValueError("Bounding-box width is valid only for a rectangle")
    box = polygon.bbox()
    return min(box.width(), box.height())
''', '''
assert rectangle_width(db.Polygon(db.Box(0, 0, 40, 400))) == 40
assert rectangle_width(db.Polygon(db.Box(0, 0, 400, 40))) == 40
nonrectangle = db.Polygon([db.Point(0, 0), db.Point(20, 0), db.Point(20, 10),
                          db.Point(10, 10), db.Point(10, 20), db.Point(0, 20)])
try:
    rectangle_width(nonrectangle)
except ValueError:
    pass
else:
    raise AssertionError("Nonrectangular width must be rejected")
''', 'https://www.klayout.de/doc/code/class_Polygon.html'),
    APIExample('width_check_and_sizing',
        'Region.width_check(integer_threshold_dbu) returns EdgePairs: violation markers, not width measurements. '
        'Region.min_width() does not exist. Region.sized(integer_delta_dbu) returns a NEW Region; '
        'positive values expand, negative values shrink. It expands all sides and can create spacing errors '
        'or join components. Region.moved(dx, dy) returns a NEW translated Region using integer DBU. '
        'Apply only to selected editable geometry and recheck preservation and DRC.',
        '''
def width_markers(region, threshold_dbu):
    return region.width_check(threshold_dbu)

def expand_region(region, delta_dbu):
    return region.sized(delta_dbu)

def translate_region(region, dx_dbu, dy_dbu):
    return region.moved(dx_dbu, dy_dbu)
''', '''
narrow = db.Region(db.Box(0, 0, 40, 400))
markers = width_markers(narrow, 72)
assert isinstance(markers, db.EdgePairs) and markers.count() == 1
assert width_markers(narrow, 40).is_empty()
expanded = expand_region(narrow, 16)
assert expanded.bbox() == db.Box(-16, -16, 56, 416)
assert width_markers(expanded, 72).is_empty()
assert narrow.bbox() == db.Box(0, 0, 40, 400)
translated = translate_region(narrow, 80, -20)
assert translated.bbox() == db.Box(80, -20, 120, 380)
assert narrow.bbox() == db.Box(0, 0, 40, 400)
''', 'https://www.klayout.de/doc/code/class_Region.html'),
    APIExample('edge_length_filter',
        'Region.edges() returns Edges. Edges.with_length(minimum, maximum, False) returns NEW Edges '
        'with minimum <= length < maximum. None means no bound. Always pass the third argument: '
        'the two-argument form may select a different overload. Edges.MaxLength does not exist. '
        'edges.each() yields Edge objects; edge.length() gives DBU length. These operations do not mutate edges. '
        'Python range endpoints differ from Ruby inclusive ranges; use the complete decoded deck expression, '
        'not an assumed equivalent spacing rule. Edges uses merged semantics by default: overlapping '
        'collinear edges can be combined before filtering.',
        '''
def edges_in_range(edges, minimum_dbu, maximum_dbu):
    return edges.with_length(minimum_dbu, maximum_dbu, False)
''', '''
edges = db.Edges([db.Edge(0, row * 10, length, row * 10)
                  for row, length in enumerate((143, 144, 145, 146))])
def lengths(selected):
    return sorted(edge.length() for edge in selected.each())
assert lengths(edges_in_range(edges, 144, 146)) == [144, 145]
assert lengths(edges_in_range(edges, 145, None)) == [145, 146]
assert lengths(edges_in_range(edges, None, 144)) == [143]
assert edges.count() == 4
''', 'https://www.klayout.de/doc/code/class_Edges.html'),
    APIExample('edge_pair_inspection',
        'EdgePairs.is_empty() returns bool; count() returns an integer; each() returns an iterator of '
        'EdgePair objects. EdgePairs.empty() does not exist. EdgePair.first and .second are Edge '
        'PROPERTIES, not methods: use pair.first, never pair.first(). Edge.p1 and .p2 are Point '
        'properties; Point.x and .y are integer DBU properties. Edge.length() is a method. '
        'These reads do not change the markers. Marker edges can lie on polygon boundaries; '
        'use polygon.inside(point) to include those boundary points.',
        '''
def has_markers(markers):
    return not markers.is_empty()

def marker_edges(markers):
    return [(pair.first, pair.second) for pair in markers.each()]

def edge_endpoints(edge):
    return ((edge.p1.x, edge.p1.y), (edge.p2.x, edge.p2.y))
''', '''
markers = db.Region(db.Box(0, 0, 40, 400)).width_check(72)
assert has_markers(markers) and markers.count() == 1
pairs = marker_edges(markers)
assert len(pairs) == 1 and all(isinstance(edge, db.Edge) for edge in pairs[0])
assert {edge.length() for edge in pairs[0]} == {400}
assert {x for edge in pairs[0] for x, y in edge_endpoints(edge)} == {0, 40}
assert {y for edge in pairs[0] for x, y in edge_endpoints(edge)} == {0, 400}
assert not has_markers(db.EdgePairs()) and marker_edges(db.EdgePairs()) == []
''', 'https://www.klayout.de/doc/code/class_EdgePair.html'),
    APIExample('region_construction_and_insertion',
        'Region(cell.shapes(layer_index)) builds a Region from a Shapes collection (boxes, polygons, '
        'and paths). An individual Shape is a handle, not a Polygon: do not call Region.insert(shape). '
        'For selected shapes use shape.box, shape.polygon, or shape.path after checking the shape type. '
        'Region.insert(source_region) and insert(polygon) are supported and MUTATE the destination. '
        'each_merged() returns a Python iterator: do not pass it directly to insert(). '
        'Insert the source Region itself or insert its polygons one at a time. These insertion '
        'operations keep other destination geometry and do not change the source.',
        '''
def region_from_shapes(shapes):
    return db.Region(shapes)

def append_region(destination, source):
    destination.insert(source)

def append_merged_polygons(destination, source):
    for polygon in source.each_merged():
        destination.insert(polygon)
''', '''
layout = db.Layout(); cell = layout.create_cell('INSERT_TEST'); layer = layout.layer(7, 3)
cell.shapes(layer).insert(db.Box(0, 0, 10, 10))
cell.shapes(layer).insert(db.Polygon(db.Box(20, 0, 30, 10)))
cell.shapes(layer).insert(db.Path([db.Point(40, 0), db.Point(40, 10)], 4))
source = region_from_shapes(cell.shapes(layer))
assert source.area() == 240 and len(list(source.each_merged())) == 3
for shape in cell.shapes(layer).each():
    selected = db.Region()
    if shape.is_box():
        selected.insert(shape.box)
    elif shape.is_polygon():
        selected.insert(shape.polygon)
    elif shape.is_path():
        selected.insert(shape.path)
    assert not selected.is_empty()
first = db.Region(db.Box(-20, 0, -10, 10))
second = first.dup()
append_region(first, source)
append_merged_polygons(second, source)
assert (first ^ second).is_empty() and first.area() == 340
assert len(list(first.each_merged())) == 4 and source.area() == 240
''', 'https://www.klayout.de/doc/code/class_Region.html'),
    APIExample('physical_box_conversion',
        'DBox coordinates are in micrometers. DBox.to_itype(dbu) returns an integer Box without '
        'changing the DBox. Do not call Box.from_dbox(box, dbu): that argument form is invalid. '
        'Coordinate conversion rounds coordinates; it does not enforce an outward repair margin or grid.',
        '''
def physical_box(x1_um, y1_um, x2_um, y2_um, dbu_um):
    return db.DBox(x1_um, y1_um, x2_um, y2_um).to_itype(dbu_um)
''', '''
assert physical_box(0, 0, 0.01, 0.1, 0.00025) == db.Box(0, 0, 40, 400)
assert physical_box(0, 0, 0.01, 0.1, 0.001) == db.Box(0, 0, 10, 100)
''', 'https://www.klayout.de/doc/code/class_DBox.html'),
)


EXAMPLES += (
    APIExample('geometry_values', 'Geometry values and safe component replacement.', '''
def shape_polygon(shape):
    if shape.is_box():
        return db.Polygon(shape.box)
    if shape.is_polygon():
        return shape.polygon
    if shape.is_path():
        return shape.path.polygon()
    raise ValueError("Unsupported shape type; preserve it separately")

def replace_component(region, target, replacement):
    result = db.Region()
    found = False
    for polygon in region.each_merged():
        if polygon == target:
            result.insert(replacement)
            found = True
        else:
            result.insert(polygon)
    if not found:
        raise ValueError("Target component not found")
    return result
''', '''
box = db.Box(0, 0, 10, 20); point = db.Point(2, 3)
path = db.Path([db.Point(0, 0), db.Point(0, 10)], 4)
polygon = db.Polygon(box)
ring = db.Region(db.Box(0, 0, 100, 100)) - db.Region(db.Box(20, 20, 80, 80))
hole_polygon = next(ring.each())
layout = db.Layout(); cell = layout.create_cell('VALUES'); layer = layout.layer(7, 3)
shapes = cell.shapes(layer)
box_shape = shapes.insert(box)
polygon_shape = shapes.insert(db.Polygon(db.Box(30, 0, 40, 20)))
path_shape = shapes.insert(path)
assert shape_polygon(box_shape).area() == 200
assert shape_polygon(polygon_shape).area() == 200
assert shape_polygon(path_shape).area() == 40
source = db.Region(box) + db.Region(db.Box(100, 0, 110, 20))
target = next(p for p in source.each_merged() if p.bbox().left == 0)
repaired = replace_component(source, target, db.Region(db.Box(0, 0, 20, 20)))
assert repaired.area() == 600 and source.area() == 400
assert len(list(repaired.each_merged())) == 2
assert (db.Region(db.Box(100, 0, 110, 20)) - repaired).is_empty()
assert list(hole_polygon.each_point_hole(0)) and len(list(hole_polygon.each_point_hull())) == 4
''', 'https://www.klayout.de/doc/code/class_Shape.html'),
    APIExample('geometry_operations', 'Boolean operations, selection and mutation.', '''
def spacing_markers(region, threshold_dbu):
    return region.space_check(threshold_dbu)
''', '''
a = db.Region(db.Box(0, 0, 10, 10)); b = db.Region(db.Box(5, 0, 15, 10))
assert (a | b).area() == 150 and (a & b).area() == 50
assert (a - b).area() == 50 and (a ^ b).area() == 100
assert a.area() == b.area() == 100
components = a + db.Region(db.Box(20, 0, 40, 10))
window = db.Region(db.Box(-1, -1, 11, 11))
assert components.inside(window).area() == 100
assert components.interacting(db.Region(db.Box(10, 0, 11, 10))).area() == 100
assert components.with_area(100, 200, False).area() == 100
spaced = db.Region(db.Box(0, 0, 10, 100)) + db.Region(db.Box(15, 0, 25, 100))
assert spacing_markers(spaced, 8).count() == 1
assert spacing_markers(spaced, 5).is_empty()
touching = a + db.Region(db.Box(10, 0, 20, 10))
assert touching.count() == 2 and len(list(touching.each_merged())) == 1
assert touching.merge() is touching and touching.count() == 1
''', 'https://www.klayout.de/doc/code/class_Region.html'),
    APIExample('hierarchy_read', 'Read geometry in the starting cell coordinate frame.', '''
def recursive_polygons(cell, layer_index):
    result = []
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_box():
            polygon = db.Polygon(shape.box)
        elif shape.is_polygon():
            polygon = shape.polygon
        elif shape.is_path():
            polygon = shape.path.polygon()
        else:
            iterator.next()
            continue
        result.append(polygon.transformed(iterator.itrans()))
        iterator.next()
    return result
''', '''
layout = db.Layout(); layer = layout.layer(7, 3)
top = layout.create_cell('TOP'); block = layout.create_cell('BLOCK'); leaf = layout.create_cell('LEAF')
leaf.shapes(layer).insert(db.Box(0, 0, 10, 20))
block.insert(db.CellInstArray(leaf.cell_index(), db.Trans(1, False, 100, 200)))
top.insert(db.CellInstArray(block.cell_index(), db.Trans(0, False, 1000, 2000)))
top.insert(db.CellInstArray(leaf.cell_index(), db.Trans(0, False, 100, 200)))
top.insert(db.CellInstArray(leaf.cell_index(), db.Trans(0, True, 300, 400)))
top.insert(db.CellInstArray(leaf.cell_index(), db.Trans(0, False, 500, 600),
                           db.Vector(50, 0), db.Vector(0, 60), 2, 2))
top.insert(db.CellInstArray(leaf.cell_index(), db.ICplxTrans(2.0, 90.0, False, 800, 900)))
master_before = db.Region(leaf.shapes(layer))
definitions_before = [(instance.cell_index, str(instance.cplx_trans)) for instance in top.each_inst()]
polygons = recursive_polygons(top, layer)
expected_boxes = [db.Box(1080, 2200, 1100, 2210), db.Box(100, 200, 110, 220),
                  db.Box(300, 380, 310, 400), db.Box(500, 600, 510, 620),
                  db.Box(550, 600, 560, 620), db.Box(500, 660, 510, 680),
                  db.Box(550, 660, 560, 680), db.Box(760, 900, 800, 920)]
assert sorted(str(p.bbox()) for p in polygons) == sorted(str(box) for box in expected_boxes)
flat = db.Region(top.begin_shapes_rec(layer))
assert (flat ^ db.Region(polygons)).is_empty() and flat.count() == 8
assert db.Region(top.shapes(layer)).is_empty()
assert (db.Region(leaf.shapes(layer)) ^ master_before).is_empty()
assert definitions_before == [(instance.cell_index, str(instance.cplx_trans)) for instance in top.each_inst()]
transform = db.Trans(1, False, 100, 200)
complex_transform = db.ICplxTrans(2.0, 90.0, False, 100, 200)
assert transform * db.Point(10, 20) == db.Point(80, 210)
assert complex_transform * db.Point(10, 20) == db.Point(60, 220)
assert transform.inverted() * (transform * db.Point(10, 20)) == db.Point(10, 20)
iterator = top.begin_shapes_rec(layer)
''', 'https://www.klayout.de/doc/code/class_RecursiveShapeIterator.html'),
)


@dataclass(frozen=True)
class APIContract:
    section: str
    call: str
    result: str
    units: str
    effect: str
    example: str
    check: str


# Every published call has a behavior check, executed with its example fixture.
CONTRACTS = (
    APIContract('Layout and shapes', 'db.Layout()', 'Layout', '-', 'new', 'layout_io', 'assert isinstance(db.Layout(), db.Layout)'),
    APIContract('Layout and shapes', 'L.read(path: str)', 'LayerMap; use L afterward', '-', 'layout', 'layout_io', "fresh = db.Layout(); assert isinstance(fresh.read(str(input_path)), db.LayerMap); assert fresh.top_cell().name == 'TOP'"),
    APIContract('Layout and shapes', 'L.write(path: str)', 'same Layout', '-', 'file', 'layout_io', "assert saved.write(str(work_dir/'verify.gds')) is saved; assert (work_dir/'verify.gds').is_file()"),
    APIContract('Layout and shapes', 'L.dbu', 'float (property)', 'um/DBU', 'read', 'layout_io', 'assert layout.dbu == 0.00025'),
    APIContract('Layout and shapes', 'L.top_cells()', 'list[Cell]', '-', 'read', 'layout_io', "assert isinstance(layout.top_cells(), list) and [c.name for c in layout.top_cells()] == ['TOP']"),
    APIContract('Layout and shapes', 'L.top_cell()', 'Cell/None; reject multiple tops', '-', 'read', 'layout_io', "assert layout.top_cell().name == 'TOP' and db.Layout().top_cell() is None"),
    APIContract('Layout and shapes', 'L.cell(name: str)', 'Cell/None', '-', 'read', 'layout_io', "assert layout.cell('TOP').name == 'TOP' and layout.cell('missing') is None"),
    APIContract('Layout and shapes', 'L.find_layer(number: int, datatype: int)', 'index: int/None', '-', 'read', 'layout_io', 'assert layout.find_layer(7, 3) == index and layout.find_layer(999, 0) is None'),
    APIContract('Layout and shapes', 'L.layer(number: int, datatype: int)', 'index: int; creates if absent', '-', 'layout', 'layout_io', 'new_index = layout.layer(99, 4); assert isinstance(new_index, int) and layout.find_layer(99, 4) == new_index'),
    APIContract('Layout and shapes', 'C.shapes(index: int)', 'Shapes; direct cell only', 'DBU', 'read', 'geometry_values', 'assert isinstance(cell.shapes(layer), db.Shapes) and db.Region(cell.shapes(layer)).area() == 420'),
    APIContract('Layout and shapes', 'S.each()', 'iterator[Shape handles]', '-', 'read', 'geometry_values', 'assert len(list(shapes.each())) == 3'),
    APIContract('Layout and shapes', 'S.insert(value: Box/Polygon/Path/Region)', 'Shape for primitives; Shapes for Region', 'DBU', 'cell', 'geometry_values', 'assert isinstance(shapes.insert(box), db.Shape); assert isinstance(shapes.insert(polygon), db.Shape); assert isinstance(shapes.insert(path), db.Shape); assert shapes.insert(db.Region(db.Box(200, 0, 210, 10))) is shapes'),
    APIContract('Layout and shapes', 'S.clear()', 'same Shapes', '-', 'cell', 'geometry_values', 'assert shapes.clear() is shapes and db.Region(shapes).is_empty()'),
    APIContract('Layout and shapes', 's.is_box()/s.is_polygon()/s.is_path()', 'bool (methods)', '-', 'read', 'geometry_values', 'assert box_shape.is_box() and polygon_shape.is_polygon() and path_shape.is_path()'),
    APIContract('Layout and shapes', 's.box / s.polygon / s.path', 'Box/Polygon/Path (properties)', 'DBU', 'read', 'geometry_values', 'assert box_shape.box == box and polygon_shape.polygon.area() == 200 and path_shape.path.polygon().area() == 40'),
    APIContract('Geometry values', 'db.Point(x: int, y: int); p.x / p.y', 'Point; int properties', 'DBU', 'new/read', 'geometry_values', 'assert point == db.Point(2, 3) and (point.x, point.y) == (2, 3)'),
    APIContract('Geometry values', 'db.Box(x1, y1, x2, y2: int)', 'Box', 'DBU', 'new', 'geometry_values', 'assert db.Box(0, 0, 10, 20) == box'),
    APIContract('Geometry values', 'B.left / B.bottom / B.right / B.top', 'int properties', 'DBU', 'read', 'geometry_values', 'assert (box.left, box.bottom, box.right, box.top) == (0, 0, 10, 20)'),
    APIContract('Geometry values', 'B.width()/B.height()', 'int', 'DBU', 'read', 'geometry_values', 'assert (box.width(), box.height()) == (10, 20)'),
    APIContract('Geometry values', 'db.DBox(x1, y1, x2, y2: float).to_itype(dbu)', 'Box; nearest integer coordinates', 'um -> DBU', 'new', 'physical_box_conversion', 'assert db.DBox(0, 0, 0.01, 0.1).to_itype(0.00025) == db.Box(0, 0, 40, 400)'),
    APIContract('Geometry values', 'db.Polygon(box: Box) / db.Polygon(points: list[Point])', 'Polygon', 'DBU', 'new', 'geometry_values', 'assert db.Polygon(box).area() == 200; assert db.Polygon([db.Point(0, 0), db.Point(10, 0), db.Point(0, 10)]).area() == 50'),
    APIContract('Geometry values', 'P.bbox()', 'Box', 'DBU', 'read', 'geometry_values', 'assert polygon.bbox() == box'),
    APIContract('Geometry values', 'P.is_box()', 'bool; guards rectangle width', '-', 'read', 'geometry_values', 'assert polygon.is_box() and not hole_polygon.is_box()'),
    APIContract('Geometry values', 'P.area()', 'int; subtracts holes', 'DBU2', 'read', 'geometry_values', 'assert polygon.area() == 200 and hole_polygon.area() == 6400'),
    APIContract('Geometry values', 'P.inside(point: Point)', 'bool; includes boundary', 'DBU', 'read', 'geometry_values', 'assert polygon.inside(db.Point(0, 10)) and not hole_polygon.inside(db.Point(50, 50))'),
    APIContract('Geometry values', 'P.each_point_hull()', 'iterator[Point]', 'DBU', 'read', 'geometry_values', 'assert len(list(polygon.each_point_hull())) == 4'),
    APIContract('Geometry values', 'P.holes(); P.each_point_hole(h: int)', 'int; iterator[Point]', 'DBU', 'read', 'geometry_values', 'assert hole_polygon.holes() == 1 and len(list(hole_polygon.each_point_hole(0))) == 4'),
    APIContract('Geometry values', 'P.dup()', 'independent Polygon', 'DBU', 'new', 'geometry_values', 'copy = polygon.dup(); assert copy is not polygon and copy == polygon'),
    APIContract('Geometry values', 'db.Path(points: list[Point], width: int).polygon()', 'Polygon of stroked path', 'DBU', 'new', 'geometry_values', 'assert db.Path([db.Point(0, 0), db.Point(0, 10)], 4).polygon().area() == 40'),
    APIContract('Regions', 'db.Region() / db.Region(value: Box/Polygon/Path/Shapes)', 'Region', 'DBU', 'new', 'geometry_values', 'assert db.Region().is_empty(); assert db.Region(box).area() == 200; assert db.Region(polygon).area() == 200; assert db.Region(path).area() == 40; assert db.Region(shapes).area() == 420'),
    APIContract('Regions', 'R.is_empty()', 'bool', '-', 'read', 'geometry_operations', 'assert db.Region().is_empty() and not a.is_empty()'),
    APIContract('Regions', 'R.count()', 'int; stored polygons, not nets', '-', 'read', 'geometry_operations', 'assert components.count() == 2'),
    APIContract('Regions', 'R.bbox()/R.area()', 'Box/int', 'DBU/DBU2', 'read', 'geometry_operations', 'assert a.bbox() == db.Box(0, 0, 10, 10) and a.area() == 100'),
    APIContract('Regions', 'R.each()/R.each_merged()', 'iterator[PolygonWithProperties]', 'DBU', 'read', 'polygon_iteration_and_area', 'assert raw_polygon_count(separate) == 2 and sorted(p.area() for p in separate.each_merged()) == [100, 7500]'),
    APIContract('Regions', 'R.insert(value: Box/Polygon/Path/Region)', 'same Region', 'DBU', 'self', 'geometry_values', 'out = db.Region(); assert out.insert(box) is out; assert out.insert(polygon) is out; assert out.insert(path) is out; assert out.insert(db.Region(db.Box(100, 0, 110, 10))) is out; assert out.area() == 320'),
    APIContract('Regions', 'R.clear()', 'same Region; removes all polygons', '-', 'self', 'geometry_operations', 'copy = a.dup(); assert copy.clear() is copy and copy.is_empty() and a.area() == 100'),
    APIContract('Regions', 'R.dup()', 'independent Region', 'DBU', 'new', 'geometry_operations', 'copy = a.dup(); copy.clear(); assert a.area() == 100 and copy.is_empty()'),
    APIContract('Regions', 'a | b; a & b; a - b; a ^ b', 'Region: union/intersection/difference/XOR', 'DBU', 'new', 'geometry_operations', 'assert [(a | b).area(), (a & b).area(), (a - b).area(), (a ^ b).area()] == [150, 50, 50, 100]'),
    APIContract('Regions', 'a + b', 'Region; concatenates raw polygons', 'DBU', 'new', 'geometry_operations', 'assert (a + b).count() == 2 and (a + b).area() == 150'),
    APIContract('Regions', 'R.merge()', 'same Region; resolves overlaps/touches', 'DBU', 'self', 'geometry_operations', 'copy = a + b; assert copy.merge() is copy and copy.count() == 1'),
    APIContract('Regions', 'R.sized(d: int)/R.moved(dx: int, dy: int)', 'independent Region', 'DBU', 'new', 'width_check_and_sizing', 'assert narrow.sized(1).bbox() == db.Box(-1, -1, 41, 401); assert narrow.moved(10, 20).bbox() == db.Box(10, 20, 50, 420); assert narrow.bbox() == db.Box(0, 0, 40, 400)'),
    APIContract('Regions', 'R.size(d: int)/R.move(dx: int, dy: int)', 'same Region', 'DBU', 'self', 'geometry_operations', 'copy = a.dup(); assert copy.size(1) is copy and copy.bbox() == db.Box(-1, -1, 11, 11); assert copy.move(10, 20) is copy and copy.bbox() == db.Box(9, 19, 21, 31); assert a.area() == 100'),
    APIContract('Regions', 'R.interacting(other: Region)', 'Region; selects whole touching/overlapping components', 'DBU', 'new', 'geometry_operations', 'assert components.interacting(db.Region(db.Box(10, 0, 11, 10))).area() == 100'),
    APIContract('Regions', 'R.inside(other: Region)', 'Region; selects contained components', 'DBU', 'new', 'geometry_operations', 'assert components.inside(window).area() == 100'),
    APIContract('Regions', 'R.with_area(lo, hi: int/None, False)', 'Region; lo <= area < hi', 'DBU2', 'new', 'geometry_operations', 'assert components.with_area(100, 200, False).area() == 100 and components.with_area(200, None, False).area() == 200'),
    APIContract('Markers and edges', 'R.width_check(d: int)/R.space_check(d: int)', 'EdgePairs; error markers, not scalar distance', 'DBU', 'new', 'geometry_operations', 'assert a.width_check(11).count() > 0 and spacing_markers(spaced, 8).count() == 1 and spaced.space_check(5).is_empty()'),
    APIContract('Markers and edges', 'R.edges()', 'Edges', 'DBU', 'new', 'geometry_operations', 'assert isinstance(a.edges(), db.Edges) and a.edges().count() == 4'),
    APIContract('Markers and edges', 'E.with_length(lo, hi: int/None, False)', 'Edges; lo <= length < hi', 'DBU', 'new', 'edge_length_filter', 'assert lengths(edges.with_length(144, 146, False)) == [144, 145] and lengths(edges.with_length(145, None, False)) == [145, 146] and lengths(edges.with_length(None, 144, False)) == [143]'),
    APIContract('Markers and edges', 'E.each(); E.count()', 'iterator[Edge]; int', 'DBU', 'read', 'edge_length_filter', 'assert len(list(edges.each())) == edges.count() == 4'),
    APIContract('Markers and edges', 'M.is_empty(); M.count(); M.each()', 'bool; int; iterator[EdgePair]', '-', 'read', 'edge_pair_inspection', 'assert not markers.is_empty() and markers.count() == 1 and len(list(markers.each())) == 1'),
    APIContract('Markers and edges', 'ep.first / ep.second', 'Edge properties; no parentheses', 'DBU', 'read', 'edge_pair_inspection', 'pair = next(markers.each()); assert isinstance(pair.first, db.Edge) and isinstance(pair.second, db.Edge)'),
    APIContract('Markers and edges', 'edge.p1 / edge.p2; edge.length()', 'Point properties; rounded int length', 'DBU', 'read', 'edge_pair_inspection', 'edge = next(markers.each()).first; assert isinstance(edge.p1, db.Point) and isinstance(edge.p2, db.Point) and isinstance(edge.length(), int) and edge.length() == 400; assert db.Edge(0, 0, 10, 10).length() == 14'),
    APIContract('Hierarchy and transforms', 'C.begin_shapes_rec(index: int)', 'RecursiveShapeIterator; all placements', 'DBU', 'read', 'hierarchy_read', 'assert db.Region(top.begin_shapes_rec(layer)).count() == 8'),
    APIContract('Hierarchy and transforms', 'C.begin_shapes_rec_overlapping(index: int, window: Box)', 'RecursiveShapeIterator; bbox filter, not clip', 'DBU', 'read', 'hierarchy_read', 'selected = db.Region(top.begin_shapes_rec_overlapping(layer, db.Box(101, 201, 105, 205))); assert selected.bbox() == db.Box(100, 200, 110, 220)'),
    APIContract('Hierarchy and transforms', 'db.Region(iterator: RecursiveShapeIterator)', 'Region in starting cell frame', 'DBU', 'new', 'hierarchy_read', 'assert (db.Region(top.begin_shapes_rec(layer)) ^ db.Region(polygons)).is_empty()'),
    APIContract('Hierarchy and transforms', 'it.at_end(); it.next()', 'bool; same iterator', '-', 'read/advance', 'hierarchy_read', 'seen = 0\nwhile not iterator.at_end():\n    seen += 1\n    assert iterator.next() is iterator\nassert seen == 8'),
    APIContract('Hierarchy and transforms', 'it.shape(); it.cell(); it.itrans()', 'Shape; source Cell; ICplxTrans', 'DBU', 'read', 'hierarchy_read', "assert isinstance(iterator.shape(), db.Shape) and iterator.cell().name == 'LEAF' and isinstance(iterator.itrans(), db.ICplxTrans)"),
    APIContract('Hierarchy and transforms', 'C.each_inst(); inst.cell_index / inst.trans / inst.cplx_trans', 'iterator[Instance]; int/Trans/ICplxTrans properties', 'DBU', 'read', 'hierarchy_read', 'instances = list(top.each_inst()); assert len(instances) == 5; assert all(isinstance(i.cell_index, int) and isinstance(i.trans, db.Trans) and isinstance(i.cplx_trans, db.ICplxTrans) for i in instances)'),
    APIContract('Hierarchy and transforms', 'db.Trans(rot: int, mirror: bool, dx: int, dy: int)', 'Trans; rot=0,1,2,3 quarter-turns', 'DBU', 'new', 'hierarchy_read', 'assert db.Trans(1, False, 100, 200) * db.Point(10, 20) == db.Point(80, 210); assert db.Trans(0, True, 0, 0) * db.Point(10, 20) == db.Point(10, -20)'),
    APIContract('Hierarchy and transforms', 'db.ICplxTrans(mag: float, angle: float, mirror: bool, dx: int, dy: int)', 'ICplxTrans; angle in degrees', 'DBU', 'new', 'hierarchy_read', 'assert db.ICplxTrans(2.0, 90.0, False, 100, 200) * db.Point(10, 20) == db.Point(60, 220)'),
    APIContract('Hierarchy and transforms', 'T * point; parent * child; T.inverted()', 'Point; composed/inverse transform', 'DBU', 'new', 'hierarchy_read', 'p = db.Point(10, 20); parent = db.Trans(0, False, 1000, 2000); assert (parent * transform) * p == parent * (transform * p); assert transform.inverted() * (transform * p) == p; assert complex_transform.inverted() * (complex_transform * p) == p'),
    APIContract('Hierarchy and transforms', 'P.transformed(T); R.transformed(T)', 'independent Polygon/Region', 'DBU', 'new', 'hierarchy_read', 'p = db.Polygon(db.Box(0, 0, 10, 20)); r = db.Region(p); assert p.transformed(transform).bbox() == db.Box(80, 200, 100, 210); assert r.transformed(transform).bbox() == db.Box(80, 200, 100, 210); assert p.bbox() == r.bbox() == db.Box(0, 0, 10, 20); assert r.transformed(complex_transform).area() == 800'),
    APIContract('Hierarchy and transforms', 'R.transform(T)', 'same Region', 'DBU', 'self', 'hierarchy_read', 'r = db.Region(db.Box(0, 0, 10, 20)); assert r.transform(transform) is r and r.bbox() == db.Box(80, 200, 100, 210)'),
)


MAX_REFERENCE_CHARACTERS = 18000
RUNTIME_RULES = '''
## 1. Runtime and binding rules

Use `import klayout.db as db`. This is the Python database API, not Ruby DRC,
Qt/GUI, PCell, routing, or electrical-verification APIs. Use the call forms below.
If an operation is not covered, preserve affected geometry and state the limit;
do not guess a name, overload, keyword, constant, or return type.

Properties have no parentheses: `layout.dbu`, `pair.first`, `edge.p1`, `point.x`.
Methods need them: `region.is_empty()`, `polygon.area()`. A returned object may
be the modified input: KLayout has fluent mutators. A Shape is a layout handle;
a Polygon is a geometry value. Iterators are not lists or accepted bulk inputs.

Integer geometry uses DBU; `layout.dbu` is micrometers per DBU. Length in um /
dbu = DBU; area in um2 / dbu**2 = DBU2. 1 nm = 0.001 um; 1 nm2 = 0.000001 um2.
Floating `D*` geometry uses physical coordinates here; convert DBox with the
actual DBU. Do not mix integer and floating geometry or meter-valued thresholds.
Coordinate rounding is not margin enforcement. Round required enlargements UP
to the active manufacturing grid; the grid must be an integer number of DBU.
Layer indices are layout handles, not physical layer numbers. Use the active
profile's layer/datatype pair and decoded deck; example dimensions are not rules.
'''.strip()

TABLE_LEGEND = '''
## 2. Object and call tables

Names: L=Layout, C=Cell, S=Shapes, s=Shape, R/a/b=Region, P=Polygon, B=Box,
p=Point, E=Edges, M=EdgePairs, ep=EdgePair, T=Trans/ICplxTrans,
it=RecursiveShapeIterator, inst=Instance. Coordinates, widths, offsets, and
windows are integer DBU unless stated otherwise; None means missing/unbounded
only where listed. PolygonWithProperties/EdgePairWithProperties support the
listed base geometry reads. `path` in file calls is a string file name.

Effects: read=no change; new=independent result; self=changes receiver and
returns it; cell/layout=changes that owner; file=writes the requested path.
Read handles remain tied to their Layout. Do not edit their owner while an
iterator is active. Keep the Layout alive until traversal is complete.
'''.strip()

GEOMETRY_RULES = '''
## 3. Geometry semantics

Regions and Edges use merged semantics by default. Overlapping/touching polygons
may form one connected component; overlapping collinear edges may combine before
filtering. `each()` reads stored polygons; `each_merged()` reads merged components
under the default semantics. Do not disable merged semantics in these recipes.
Counts are not electrical net counts. `+` concatenates stored polygons; `|` is
geometric union. Neither invents a bridge across a gap. Never merge unknown nets
to fix spacing. Sizing affects every boundary, can close holes or join components,
and can create other violations; limit it to selected editable geometry.

Area is per connected polygon and subtracts holes. A layer total can hide a small
island. A bounding-box side measures width only after `is_box()` succeeds; it is
not the neck width of an arbitrary polygon. Integer area and edge length can
lose sub-DBU precision on diagonal geometry; do not infer exact distances from
rounded values. Width/space checks return EdgePairs,
not a scalar minimum. Inspect both marker edges; their order is not net ownership.
`inside(point)` includes the polygon boundary but excludes hole interiors.
Region selection returns whole components; intersection clips geometry.

Range forms include the lower bound and exclude the upper bound. Pass the
explicit inverse=False argument. None opens a bound. Ruby inclusive ranges and
filtered DRC expressions are not direct Python equivalents. The pinned deck is
authoritative for threshold equality, edge filters, projections, and final DRC.
'''.strip()

HIERARCHY_RULES = '''
## 4. Hierarchy and safe editing

`cell.shapes(index)` sees only that cell's direct shapes. Recursive reads expand
all instance placements, including arrays. A Shape from `it.shape()` is in its
source cell frame; `it.itrans()` accumulates the transform into the starting
cell frame. Apply it exactly once. `Region(cell.begin_shapes_rec(index))` already
applies transforms: do not transform its output again. Window traversal filters
shape bounding boxes; it does not clip the returned shapes to the window.

Trans uses integer quarter-turns 0..3; ICplxTrans uses degrees and magnification.
Mirroring is about the x axis before rotation; translation follows. `parent *
child` applies child first. Complex integer transforms can round; inverse mapping
is not necessarily exact. Test grid alignment after rotation/scaling.

`each_inst()` returns instance definitions; an array is one item, not all its
placements. A master edit affects every instance. Treat masters and instance
definitions as read-only unless the edit policy explicitly permits changes.
Do not insert flattened recursive geometry into a cell as a repair strategy.
Build replacement geometry separately, retain unaffected components/holes, finish
iteration, then commit once to the explicitly editable flat cell/layer. Rewriting
physical geometry with clear/insert does not preserve text/properties or other
nonphysical metadata automatically; do not use it where those must be retained.
Write a separate output file. Preserve clean inputs and protected content.
Geometry validity and DRC cleanliness do not establish electrical correctness.
'''.strip()

KNOWN_ERRORS = (
    ('Region.each_polygon()', 'Region.each() or each_merged()'),
    ('Region.min_width()', 'width_check(dbu) returns markers; rectangle width needs is_box()'),
    ('Edges.MaxLength / guessed two-argument filter', 'with_length(lo, None, False) for an open upper bound'),
    ('markers.empty()', 'markers.is_empty()'),
    ('pair.first() / pair.second()', 'pair.first / pair.second (properties)'),
    ('polygon.contains(point)', 'polygon.inside(point), including boundary'),
    ('Region.insert(shape_handle)', 'Region(Shapes), or insert shape.box/polygon/path after type check'),
    ('Region.insert(region.each_merged())', 'insert(region), or loop and insert each polygon'),
    ('Box.from_dbox(box, dbu)', 'DBox.to_itype(dbu)'),
    ('clear/insert during iteration', 'build a new Region, then commit after iteration'),
)

DISPLAY_EXAMPLES = ('layout_io', 'units_and_grid', 'edge_pair_inspection',
                    'geometry_values', 'hierarchy_read')
EXAMPLE_EXPECTATIONS = {
    'layout_io': 'Read one top cell; replace only an authorized flat physical layer; write a separate file.',
    'units_and_grid': 'At DBU=0.00025 um and grid=0.0005 um, 0.0181 um rounds UP to 74 DBU.',
    'edge_pair_inspection': 'A 40-by-400 DBU rectangle checked at 72 DBU yields one marker; edge properties are readable without calls.',
    'geometry_values': 'Replacing a 200 DBU2 component by 400 DBU2 retains its separate 200 DBU2 neighbor: total 600; source stays 400.',
    'hierarchy_read': 'A 10-by-20 DBU leaf at Trans(1, False, 100, 200) reads as box (80,200;100,210). Repeated placements stay separate.',
}
ADDITIONAL_SOURCES = tuple(f'https://www.klayout.de/doc/code/class_{name}.html'
                           for name in ('EdgePairs', 'Trans', 'ICplxTrans', 'Point', 'Box',
                                        'Path', 'Shapes', 'Cell'))


def reference_digest():
    content = {'examples': [asdict(example) for example in EXAMPLES],
               'contracts': [asdict(contract) for contract in CONTRACTS],
               'text': [RUNTIME_RULES, TABLE_LEGEND, GEOMETRY_RULES, HIERARCHY_RULES],
               'known_errors': KNOWN_ERRORS, 'display_examples': DISPLAY_EXAMPLES,
               'expectations': EXAMPLE_EXPECTATIONS, 'additional_sources': ADDITIONAL_SOURCES,
               'size_limit': MAX_REFERENCE_CHARACTERS}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def validate_example(example, work_dir):
    """Execute a fixed package example and its value/geometry checks."""
    namespace = {'db': db, 'work_dir': Path(work_dir)}
    for label, source in [('code', example.code), ('checks', example.checks)]:
        exec(compile(textwrap.dedent(source), f'<api-reference:{example.name}:{label}>',
                     'exec', optimize=0), namespace)
    return namespace


def validate_contract(contract, work_dir):
    example = next(example for example in EXAMPLES if example.name == contract.example)
    namespace = validate_example(example, work_dir)
    exec(compile(contract.check, f'<api-contract:{contract.call}>', 'exec', optimize=0), namespace)


@lru_cache(maxsize=1)
def verify_api_reference():
    """Fail before dispatch if any bundled example is incompatible with the runtime."""
    example_name = 'runtime setup'
    try:
        with TemporaryDirectory(prefix='klayout-api-reference-') as directory:
            for example in EXAMPLES:
                example_name = example.name
                validate_example(example, directory)
            for contract in CONTRACTS:
                example_name = contract.call
                if not contract.check.strip():
                    raise ValueError('A published call has no behavior check')
                validate_contract(contract, directory)
    except Exception as exc:
        raise APIReferenceError(f'KLayout API reference check failed for {example_name}: {exc}') from exc
    return {'runtime_version': db.__version__, 'reference_sha256': reference_digest(),
            'examples_checked': len(EXAMPLES), 'contracts_checked': len(CONTRACTS)}


def render_api_reference():
    metadata = verify_api_reference()
    lines = ['=== Verified KLayout Python API Reference ===',
             '# KLayout Python API: layout repair and hierarchy',
             f"Runtime: klayout.db {metadata['runtime_version']}",
             f"Reference SHA-256: {metadata['reference_sha256']}",
             f"Verified: {metadata['contracts_checked']} call contracts and {metadata['examples_checked']} example groups.",
             '', RUNTIME_RULES, '', TABLE_LEGEND]
    section = None
    for contract in CONTRACTS:
        if contract.section != section:
            section = contract.section
            lines.extend(['', f'### {section}', '', '| Exact call and accepted arguments | Returns | Units | Effect |',
                          '|---|---|---|---|'])
        values = [f'`{contract.call}`', contract.result, contract.units, contract.effect]
        lines.append('| ' + ' | '.join(value.replace('|', r'\|') for value in values) + ' |')
    lines.extend(['', GEOMETRY_RULES, '', HIERARCHY_RULES,
                  '', '## 5. Known errors and usage examples', '',
                  '| Unsupported or unsafe form | Verified replacement |', '|---|---|'])
    for bad, good in KNOWN_ERRORS:
        lines.append(f'| {bad} | {good} |')
    lines.extend(['', 'Copy needed helpers into a self-contained script with `import klayout.db as db`.',
                  'The sandbox cannot import this project. These are API idioms, not repair decisions.',
                  'Each function below was executed on synthetic geometry; expected results are shown.'])
    for name in DISPLAY_EXAMPLES:
        example = next(example for example in EXAMPLES if example.name == name)
        lines.extend(['', f'### {name}', '', EXAMPLE_EXPECTATIONS[name], '',
                      '```python', textwrap.dedent(example.code).strip(), '```'])
    lines.extend(['', '### Official sources', '',
                  'Installed-binding behavior checks are authoritative for this version; web manuals may describe newer versions.'])
    sources = dict.fromkeys(example.source for example in EXAMPLES)
    sources.update(dict.fromkeys(ADDITIONAL_SOURCES))
    for url in sources:
        label = url.rsplit('/', 1)[-1].removeprefix('class_').removesuffix('.html')
        lines.append(f'- [{label}]({url})')
    lines.append('=== End Verified KLayout Python API Reference ===')
    result = '\n'.join(lines) + '\n'
    if len(result) > MAX_REFERENCE_CHARACTERS:
        raise APIReferenceError(f'API reference exceeds {MAX_REFERENCE_CHARACTERS} characters: {len(result)}')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    try:
        rendered = render_api_reference()
        if args.format == 'markdown':
            print(rendered, end='')
        else:
            print(json.dumps({'status': 'success', **verify_api_reference(),
                              'reference_text': rendered}))
    except APIReferenceError as error:
        print(json.dumps({'status': 'error', 'stage': 'api_reference', 'message': str(error)}))
        raise SystemExit(1)
