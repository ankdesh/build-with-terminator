# Geometric Fix Techniques for KLayout DRC Errors

This document provides recommended geometric strategies and Python algorithms for resolving common DRC violations in GDS layouts.

---

## 1. Fixing Minimum Width Violations (`M1_W`)

### Root Cause
Polygons or tracks whose transverse width is narrower than the DRC minimum threshold (e.g. $10\text{ nm} < 18\text{ nm}$).

### Recommended Repair Algorithm
1. Identify the violating polygon or edge pair.
2. If the violation occurs on a narrow isolated polygon, dilate the polygon outward using:
   ```python
   # Dilation by half the missing width on both sides:
   # Target = 18nm (72 DBU), Current = 10nm (40 DBU) -> expand by 16 DBU
   healed_region = violating_region.sized(16)
   ```
3. Alternatively, replace the narrow segment with an expanded bounding box that respects design grid and enclosure.

---

## 2. Fixing Minimum Spacing Violations (`M1_S`)

### Root Cause
Adjacent polygons or parallel edges separated by less than the required DRC spacing (e.g. $10\text{ nm} < 18\text{ nm}$).

### Recommended Repair Algorithm
1. Identify which edge can be trimmed or pushed back without breaking connectivity:
   ```python
   # Example: subtract a spacing keep-out buffer
   keepout = poly_a_region.sized(spacing_dbu)
   poly_b_region = poly_b_region - keepout
   ```
2. Or merge the two traces if they belong to the same electrical net:
   ```python
   unified_region = poly_a_region + poly_b_region
   ```

---

## 3. Fixing Enclosure Violations (`V1_M1_ENC`)

### Root Cause
Metal 1 boundary does not extend far enough beyond the boundary of a Via 1 cut (e.g. $0\text{ nm} < 9\text{ nm}$).

### Recommended Repair Algorithm
1. Calculate the required enclosure buffer around V1:
   ```python
   # Required enclosure = 9nm (36 DBU)
   v1_enclosure_target = v1_region.sized(36)
   ```
2. Union this enclosure patch with the M1 region:
   ```python
   repaired_m1 = m1_region + v1_enclosure_target
   ```
3. Verify that the newly added enclosure does not violate M1 spacing (`M1_S`) to adjacent shapes.

---

## 4. Standard Python Script Template for Automated Layout Healing

Any generated fix script should be a self-contained executable Python script:

```python
import sys
import klayout.db as db

def fix_layout(input_gds: str, output_gds: str):
    layout = db.Layout()
    layout.read(input_gds)
    top_cell = layout.top_cell()
    
    m1_layer = layout.layer(18, 0)
    v1_layer = layout.layer(19, 0)
    
    m1_reg = db.Region(top_cell.shapes(m1_layer))
    v1_reg = db.Region(top_cell.shapes(v1_layer))
    
    # Apply repairs...
    # (e.g. pad V1 enclosure)
    repaired_m1 = m1_reg + v1_reg.sized(36)
    
    # Commit changes
    top_cell.shapes(m1_layer).clear()
    top_cell.shapes(m1_layer).insert(repaired_m1)
    layout.write(output_gds)

if __name__ == "__main__":
    in_file = sys.argv[1] if len(sys.argv) > 1 else "input.gds"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "fixed.gds"
    fix_layout(in_file, out_file)
```
