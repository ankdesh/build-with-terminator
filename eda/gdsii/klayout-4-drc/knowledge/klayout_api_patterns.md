=== Verified KLayout Python API Reference ===
# KLayout Python API: layout repair and hierarchy
Runtime: klayout.db 0.30.8
Reference SHA-256: ad5b7aab61cfeb241a0bbf8188485f49a2629056f325a56e4a2f6593ea8dbac5
Verified: 63 call contracts and 12 example groups.

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

### Layout and shapes

| Exact call and accepted arguments | Returns | Units | Effect |
|---|---|---|---|
| `db.Layout()` | Layout | - | new |
| `L.read(path: str)` | LayerMap; use L afterward | - | layout |
| `L.write(path: str)` | same Layout | - | file |
| `L.dbu` | float (property) | um/DBU | read |
| `L.top_cells()` | list[Cell] | - | read |
| `L.top_cell()` | Cell/None; reject multiple tops | - | read |
| `L.cell(name: str)` | Cell/None | - | read |
| `L.find_layer(number: int, datatype: int)` | index: int/None | - | read |
| `L.layer(number: int, datatype: int)` | index: int; creates if absent | - | layout |
| `C.shapes(index: int)` | Shapes; direct cell only | DBU | read |
| `S.each()` | iterator[Shape handles] | - | read |
| `S.insert(value: Box/Polygon/Path/Region)` | Shape for primitives; Shapes for Region | DBU | cell |
| `S.clear()` | same Shapes | - | cell |
| `s.is_box()/s.is_polygon()/s.is_path()` | bool (methods) | - | read |
| `s.box / s.polygon / s.path` | Box/Polygon/Path (properties) | DBU | read |

### Geometry values

| Exact call and accepted arguments | Returns | Units | Effect |
|---|---|---|---|
| `db.Point(x: int, y: int); p.x / p.y` | Point; int properties | DBU | new/read |
| `db.Box(x1, y1, x2, y2: int)` | Box | DBU | new |
| `B.left / B.bottom / B.right / B.top` | int properties | DBU | read |
| `B.width()/B.height()` | int | DBU | read |
| `db.DBox(x1, y1, x2, y2: float).to_itype(dbu)` | Box; nearest integer coordinates | um -> DBU | new |
| `db.Polygon(box: Box) / db.Polygon(points: list[Point])` | Polygon | DBU | new |
| `P.bbox()` | Box | DBU | read |
| `P.is_box()` | bool; guards rectangle width | - | read |
| `P.area()` | int; subtracts holes | DBU2 | read |
| `P.inside(point: Point)` | bool; includes boundary | DBU | read |
| `P.each_point_hull()` | iterator[Point] | DBU | read |
| `P.holes(); P.each_point_hole(h: int)` | int; iterator[Point] | DBU | read |
| `P.dup()` | independent Polygon | DBU | new |
| `db.Path(points: list[Point], width: int).polygon()` | Polygon of stroked path | DBU | new |

### Regions

| Exact call and accepted arguments | Returns | Units | Effect |
|---|---|---|---|
| `db.Region() / db.Region(value: Box/Polygon/Path/Shapes)` | Region | DBU | new |
| `R.is_empty()` | bool | - | read |
| `R.count()` | int; stored polygons, not nets | - | read |
| `R.bbox()/R.area()` | Box/int | DBU/DBU2 | read |
| `R.each()/R.each_merged()` | iterator[PolygonWithProperties] | DBU | read |
| `R.insert(value: Box/Polygon/Path/Region)` | same Region | DBU | self |
| `R.clear()` | same Region; removes all polygons | - | self |
| `R.dup()` | independent Region | DBU | new |
| `a \| b; a & b; a - b; a ^ b` | Region: union/intersection/difference/XOR | DBU | new |
| `a + b` | Region; concatenates raw polygons | DBU | new |
| `R.merge()` | same Region; resolves overlaps/touches | DBU | self |
| `R.sized(d: int)/R.moved(dx: int, dy: int)` | independent Region | DBU | new |
| `R.size(d: int)/R.move(dx: int, dy: int)` | same Region | DBU | self |
| `R.interacting(other: Region)` | Region; selects whole touching/overlapping components | DBU | new |
| `R.inside(other: Region)` | Region; selects contained components | DBU | new |
| `R.with_area(lo, hi: int/None, False)` | Region; lo <= area < hi | DBU2 | new |

### Markers and edges

| Exact call and accepted arguments | Returns | Units | Effect |
|---|---|---|---|
| `R.width_check(d: int)/R.space_check(d: int)` | EdgePairs; error markers, not scalar distance | DBU | new |
| `R.edges()` | Edges | DBU | new |
| `E.with_length(lo, hi: int/None, False)` | Edges; lo <= length < hi | DBU | new |
| `E.each(); E.count()` | iterator[Edge]; int | DBU | read |
| `M.is_empty(); M.count(); M.each()` | bool; int; iterator[EdgePair] | - | read |
| `ep.first / ep.second` | Edge properties; no parentheses | DBU | read |
| `edge.p1 / edge.p2; edge.length()` | Point properties; rounded int length | DBU | read |

### Hierarchy and transforms

| Exact call and accepted arguments | Returns | Units | Effect |
|---|---|---|---|
| `C.begin_shapes_rec(index: int)` | RecursiveShapeIterator; all placements | DBU | read |
| `C.begin_shapes_rec_overlapping(index: int, window: Box)` | RecursiveShapeIterator; bbox filter, not clip | DBU | read |
| `db.Region(iterator: RecursiveShapeIterator)` | Region in starting cell frame | DBU | new |
| `it.at_end(); it.next()` | bool; same iterator | - | read/advance |
| `it.shape(); it.cell(); it.itrans()` | Shape; source Cell; ICplxTrans | DBU | read |
| `C.each_inst(); inst.cell_index / inst.trans / inst.cplx_trans` | iterator[Instance]; int/Trans/ICplxTrans properties | DBU | read |
| `db.Trans(rot: int, mirror: bool, dx: int, dy: int)` | Trans; rot=0,1,2,3 quarter-turns | DBU | new |
| `db.ICplxTrans(mag: float, angle: float, mirror: bool, dx: int, dy: int)` | ICplxTrans; angle in degrees | DBU | new |
| `T * point; parent * child; T.inverted()` | Point; composed/inverse transform | DBU | new |
| `P.transformed(T); R.transformed(T)` | independent Polygon/Region | DBU | new |
| `R.transform(T)` | same Region | DBU | self |

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

## 5. Known errors and usage examples

| Unsupported or unsafe form | Verified replacement |
|---|---|
| Region.each_polygon() | Region.each() or each_merged() |
| Region.min_width() | width_check(dbu) returns markers; rectangle width needs is_box() |
| Edges.MaxLength / guessed two-argument filter | with_length(lo, None, False) for an open upper bound |
| markers.empty() | markers.is_empty() |
| pair.first() / pair.second() | pair.first / pair.second (properties) |
| polygon.contains(point) | polygon.inside(point), including boundary |
| Region.insert(shape_handle) | Region(Shapes), or insert shape.box/polygon/path after type check |
| Region.insert(region.each_merged()) | insert(region), or loop and insert each polygon |
| Box.from_dbox(box, dbu) | DBox.to_itype(dbu) |
| clear/insert during iteration | build a new Region, then commit after iteration |

Copy needed helpers into a self-contained script with `import klayout.db as db`.
The sandbox cannot import this project. These are API idioms, not repair decisions.
Each function below was executed on synthetic geometry; expected results are shown.

### layout_io

Read one top cell; replace only an authorized flat physical layer; write a separate file.

```python
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
```

### units_and_grid

At DBU=0.00025 um and grid=0.0005 um, 0.0181 um rounds UP to 74 DBU.

```python
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
```

### edge_pair_inspection

A 40-by-400 DBU rectangle checked at 72 DBU yields one marker; edge properties are readable without calls.

```python
def has_markers(markers):
    return not markers.is_empty()

def marker_edges(markers):
    return [(pair.first, pair.second) for pair in markers.each()]

def edge_endpoints(edge):
    return ((edge.p1.x, edge.p1.y), (edge.p2.x, edge.p2.y))
```

### geometry_values

Replacing a 200 DBU2 component by 400 DBU2 retains its separate 200 DBU2 neighbor: total 600; source stays 400.

```python
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
```

### hierarchy_read

A 10-by-20 DBU leaf at Trans(1, False, 100, 200) reads as box (80,200;100,210). Repeated placements stay separate.

```python
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
```

### Official sources

Installed-binding behavior checks are authoritative for this version; web manuals may describe newer versions.
- [Layout](https://www.klayout.de/doc/code/class_Layout.html)
- [database_api](https://www.klayout.de/doc/programming/database_api.html)
- [Region](https://www.klayout.de/doc/code/class_Region.html)
- [Polygon](https://www.klayout.de/doc/code/class_Polygon.html)
- [Edges](https://www.klayout.de/doc/code/class_Edges.html)
- [EdgePair](https://www.klayout.de/doc/code/class_EdgePair.html)
- [DBox](https://www.klayout.de/doc/code/class_DBox.html)
- [Shape](https://www.klayout.de/doc/code/class_Shape.html)
- [RecursiveShapeIterator](https://www.klayout.de/doc/code/class_RecursiveShapeIterator.html)
- [EdgePairs](https://www.klayout.de/doc/code/class_EdgePairs.html)
- [Trans](https://www.klayout.de/doc/code/class_Trans.html)
- [ICplxTrans](https://www.klayout.de/doc/code/class_ICplxTrans.html)
- [Point](https://www.klayout.de/doc/code/class_Point.html)
- [Box](https://www.klayout.de/doc/code/class_Box.html)
- [Path](https://www.klayout.de/doc/code/class_Path.html)
- [Shapes](https://www.klayout.de/doc/code/class_Shapes.html)
- [Cell](https://www.klayout.de/doc/code/class_Cell.html)
=== End Verified KLayout Python API Reference ===
