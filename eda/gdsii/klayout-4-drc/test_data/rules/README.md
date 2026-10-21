# DRC Rule Decks Provenance & Specifications

This directory contains verified Design Rule Check (DRC) runsets for KLayout headless batch execution.

---

## 1. `asap7.lydrc` (Pinned Public Full Deck)
* **Description**: Authentic public ASAP7 7nm FinFET KLayout DRC deck from OpenROAD-flow-scripts.
* **Format**: KLayout XML Macro (`<klayout-macro>`) wrapping Ruby DRC DSL.
* **Upstream Source**: [The-OpenROAD-Project/OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts)
* **Upstream Path**: `flow/platforms/asap7/drc/asap7.lydrc`
* **Pinned Commit**: `d3c27c104e9c4c492a853cb75ae2c03ecd151e45`
* **SHA256**: `dc78ccd8b2b30498f25ef885c2c28a9c2a565c38cb30a87460282c8a36c7765d`
* **License**: BSD 2-Clause License (Copyright (c) 2021, laurentc2)
* **Runner Variables**:
  - `in_gds`: Input GDS layout file path (`-rd in_gds=<path>`)
  - `report_file`: Output ReportDatabase file path (`-rd report_file=<path>`)
* **Physical Layers**:
  - `V0`: 18/0
  - `M1`: 19/0
  - `M2`: 20/0
  - `V1`: 21/0
  - `V2`: 25/0
  - `M3`: 30/0
  - ... up to `Pad`: 96/0
* **Known Upstream Deck Anomalies**:
  - `M1.S.2`: Emits category `"  "` (blank whitespace).
  - `V1.M1.EN.1`: Reused category across two distinct enclosure checks.

---

## 2. `asap7_mini.drc` (Legacy Mini Deck)
* **Description**: Synthetic 3-rule mini DRC deck strictly preserved for Phase A backward compatibility and regression tests.
* **Format**: Plain Ruby DRC DSL.
* **Runner Variables**:
  - `input`: Input GDS layout file path (`-rd input=<path>`)
  - `report`: Output ReportDatabase file path (`-rd report=<path>`)
* **Layers**:
  - `M1`: 18/0 (synthetic convention)
  - `V1`: 19/0 (synthetic convention)
* **Rules Checked**:
  - `M1_W`: Minimum width 18 nm
  - `M1_S`: Minimum spacing 18 nm
  - `V1_M1_ENC`: Minimum enclosure 9 nm

---

## 3. `asap7_curated.lydrc` (Audited BEOL Subset)
* **Description**: Scoped KLayout DRC deck covering 5 independently audited BEOL rule families with normalized category identifiers and zero blank/ambiguous output tags.
* **Format**: KLayout XML Macro (`<klayout-macro>`) wrapping Ruby DRC DSL.
* **Runner Variables**:
  - `in_gds`: Input GDS layout file path (`-rd in_gds=<path>`)
  - `report_file`: Output ReportDatabase file path (`-rd report_file=<path>`)
* **Layers**:
  - `V0`: 18/0
  - `M1`: 19/0
  - `M2`: 20/0
  - `V1`: 21/0
* **Rule Families**:
  - `M1.W.1`: Minimum M1 width (18 nm)
  - `M2.W.1`: Minimum M2 width (18 nm)
  - `M1.A.1`: Minimum M1 area (504 nm²)
  - `M1.S.1`: Minimum M1 spacing for parallel edges > 36 nm (18 nm)
  - `V1.W.1`: Minimum V1 width (18 nm)
