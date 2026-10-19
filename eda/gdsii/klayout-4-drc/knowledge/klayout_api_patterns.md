# KLayout Python API Patterns (`klayout.db` / `pya`)

This document outlines standard KLayout Python API patterns for loading, inspecting, modifying, and saving GDSII layouts.

---

## 1. Initialization and Layout Management

```python
import klayout.db as db

# Create layout and set database units (DBU)
layout = db.Layout()
layout.read("input.gds")

# Retrieve top cell (or inspect available top cells)
top_cell = layout.top_cell()
dbu = layout.dbu  # e.g., 0.00025 for 0.25 nm in ASAP7
```

---

## 2. Layer and Region Operations

KLayout provides the `Region` class for planar boolean and polygon manipulation:

```python
# Resolve layer indices
m1_layer = layout.layer(18, 0)
v1_layer = layout.layer(19, 0)

# Load layer shapes into a Region
m1_region = db.Region(top_cell.shapes(m1_layer))
v1_region = db.Region(top_cell.shapes(v1_layer))

# Boolean Operations
overlap = m1_region & v1_region      # Intersection
merged = m1_region + v1_region       # Union
difference = m1_region - v1_region   # Subtraction

# Sizing / Buffering (values in database units, DBU)
# E.g. to expand by 9nm with dbu = 0.00025 um (0.25 nm):
# 9nm = 9 / 0.25 = 36 DBU
expanded_m1 = m1_region.sized(36)
```

---

## 3. In-Place Layer Replacement

To update the layout geometry:

```python
# Clear old shapes and write modified Region
top_cell.shapes(m1_layer).clear()
top_cell.shapes(m1_layer).insert(modified_m1_region)

# Save layout to target file
layout.write("output_fixed.gds")
```

---

## 4. Bounding Box & Polygon Extraction

```python
# Query shapes intersecting a bounding box window
window_box = db.DBox(x_min_um, y_min_um, x_max_um, y_max_um)
int_box = db.Box.from_dbox(window_box, dbu)

# Inspect shapes in window
for shape in top_cell.shapes(m1_layer).each_overlapping(int_box):
    if shape.is_polygon():
        poly = shape.polygon
        # Extract points in micrometers
        points_um = [(p.x * dbu, p.y * dbu) for p in poly.each_point_hull()]
```
