# ASAP7 Process Design Kit (PDK) Rules Guide

This document defines physical dimensions, layer numbers, and design rules for the ASAP7 predictive 7nm finFET technology PDK.

---

## 1. Technology Grid and Units

- **Database Units (DBU)**: $1\text{ DBU} = 0.25\text{ nm} = 0.00025\ \mu\text{m}$.
- **Grid Snapping**: All coordinates and dimensions must be integer multiples of the manufacturing grid ($0.25\text{ nm}$).
- **Conversion**:
  - Distance in DBU = $\text{Distance in nm} / 0.25$.
  - Example: $18\text{ nm} \rightarrow 72\text{ DBU}$; $9\text{ nm} \rightarrow 36\text{ DBU}$.

---

## 2. ASAP7 Layer Table

| Layer Name | Layer Number | Datatype | Description |
|---|---|---|---|
| `M1` | 18 | 0 | Metal 1 (Interconnect) |
| `V1` | 19 | 0 | Via 1 (Connects M1 to M2) |
| `M2` | 20 | 0 | Metal 2 (Interconnect) |

---

## 3. Geometric Design Rules

### 3.1 M1_W: Metal 1 Minimum Width
- **Rule Specification**: Minimum width of any M1 polygon is $18\text{ nm}$ ($0.018\ \mu\text{m}$ / $72\text{ DBU}$).
- **Common Violations**: Thin routing tracks or necks below $18\text{ nm}$ (e.g. $10\text{ nm}$).

### 3.2 M1_S: Metal 1 Minimum Spacing
- **Rule Specification**: Minimum spacing between distinct M1 polygons or edges is $18\text{ nm}$ ($0.018\ \mu\text{m}$ / $72\text{ DBU}$).
- **Common Violations**: Parallel traces placed too close (e.g. $10\text{ nm}$ spacing between $0.12\ \mu\text{m}$ and $0.13\ \mu\text{m}$).

### 3.3 V1_M1_ENC: Via 1 Enclosure by Metal 1
- **Rule Specification**: Metal 1 must enclose Via 1 on all sides by at least $9\text{ nm}$ ($0.009\ \mu\text{m}$ / $36\text{ DBU}$).
- **Common Violations**: Via placed flush with M1 edge ($0\text{ nm}$ enclosure) or partial overhangs.
