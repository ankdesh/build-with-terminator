# SkyWater 130nm HD Standard Cell Library (`sky130_fd_sc_hd`) GDS Statistics

Comprehensive layout and file size statistics for all GDSII layout files in the **SkyWater SKY130 High-Density Standard Cell Library** (`sky130_fd_sc_hd`).

## 1. Source & Repository Context

- **PDK Repository**: [`google/skywater-pdk`](https://github.com/google/skywater-pdk/tree/main/libraries/sky130_fd_sc_hd)
- **Target Submodule**: `libraries/sky130_fd_sc_hd` ([`google/skywater-pdk-libs-sky130_fd_sc_hd`](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd))
- **Target Commit**: `ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1` (`latest`)
- **Technology**: SkyWater 130nm CMOS (`sky130`)
- **Cell Library**: High Density (`fd_sc_hd`), 7-track standard cell architecture.

---

## 2. Overall GDS Metrics Summary

- **Total GDS Layout Files**: **437**
- **Total Uncompressed Size**: **4,220,820 Bytes** (4.03 MB)
- **Minimum File Size**: **1,370 Bytes** (1.34 KB)
- **Maximum File Size**: **23,996 Bytes** (23.43 KB)
- **Mean File Size**: **9658.6 ± 4801.0 Bytes** (9.43 KB)
- **Median File Size**: **8254.0 Bytes** (8.06 KB)

---

## 3. Breakdown by Functional Cell Category

| Category | Cell Count | Total Size | Min Size | Max Size | Mean Size | Median Size |
|---|---|---|---|---|---|---|
| **Combinational Logic Gates** | 225 | 1827.1 KB | 3,748 B | 16,316 B | 8315 B | 7532 B |
| **Sequential (Flip-Flops / Latches)** | 82 | 1186.4 KB | 5,556 B | 23,996 B | 14816 B | 15104 B |
| **Buffers & Inverters** | 66 | 590.0 KB | 3,632 B | 23,774 B | 9153 B | 7904 B |
| **Physical & Decap Cells** | 20 | 56.1 KB | 1,370 B | 5,286 B | 2872 B | 2812 B |
| **Other Specialized Cells** | 18 | 190.8 KB | 6,266 B | 21,080 B | 10853 B | 9664 B |
| **Multiplexers** | 10 | 106.3 KB | 6,970 B | 15,750 B | 10881 B | 10380 B |
| **Adders & Arithmetic** | 9 | 130.4 KB | 9,018 B | 19,578 B | 14832 B | 14156 B |
| **Power Management & Special** | 7 | 35.0 KB | 3,154 B | 9,106 B | 5117 B | 5028 B |

---

## 4. Size Percentile Distribution

| Percentile | Size (Bytes) | Size (KB) |
|---|---|---|
| **p10** | 4,622.0 B | 4.51 KB |
| **p25** | 6,278.0 B | 6.13 KB |
| **p50 (median)** | 8,254.0 B | 8.06 KB |
| **p75** | 12,648.0 B | 12.35 KB |
| **p90** | 16,278.8 B | 15.90 KB |
| **p95** | 19,504.4 B | 19.05 KB |
| **p99** | 22,957.9 B | 22.42 KB |

---

## 5. Size Bin Histogram

| Size Range | Cell Count | Percentage |
|---|---|---|
| `< 2 KB` | 7 | 1.60% |
| `2 KB – 5 KB` | 52 | 11.90% |
| `5 KB – 8 KB` | 158 | 36.16% |
| `8 KB – 12 KB` | 99 | 22.65% |
| `12 KB – 16 KB` | 78 | 17.85% |
| `16 KB – 20 KB` | 25 | 5.72% |
| `>= 20 KB` | 18 | 4.12% |

---

## 6. Extremes: Top 5 Smallest & Largest Cells

### Top 5 Smallest Cells

| Rank | File Size | Cell Name | Path | Functional Description |
|---|---|---|---|---|
| 1 | 1,370 B (1.34 KB) | `fill_1` | `cells/fill/sky130_fd_sc_hd__fill_1.gds` | Physical fill/tap cell |
| 2 | 1,498 B (1.46 KB) | `fill_2` | `cells/fill/sky130_fd_sc_hd__fill_2.gds` | Physical fill/tap cell |
| 3 | 1,754 B (1.71 KB) | `fill_4` | `cells/fill/sky130_fd_sc_hd__fill_4.gds` | Physical fill/tap cell |
| 4 | 1,774 B (1.73 KB) | `tapvpwrvgnd_1` | `cells/tapvpwrvgnd/sky130_fd_sc_hd__tapvpwrvgnd_1.gds` | Physical fill/tap cell |
| 5 | 1,942 B (1.90 KB) | `tap_1` | `cells/tap/sky130_fd_sc_hd__tap_1.gds` | Physical fill/tap cell |

### Top 5 Largest Cells

| Rank | File Size | Cell Name | Path | Functional Description |
|---|---|---|---|---|
| 1 | 23,996 B (23.43 KB) | `sedfxbp_2` | `cells/sedfxbp/sky130_fd_sc_hd__sedfxbp_2.gds` | Complex sequential / isolation macro |
| 2 | 23,774 B (23.22 KB) | `lpflow_isobufsrc_16` | `cells/lpflow_isobufsrc/sky130_fd_sc_hd__lpflow_isobufsrc_16.gds` | Complex sequential / isolation macro |
| 3 | 23,520 B (22.97 KB) | `sdfbbn_2` | `cells/sdfbbn/sky130_fd_sc_hd__sdfbbn_2.gds` | Complex sequential / isolation macro |
| 4 | 23,088 B (22.55 KB) | `sdfbbn_1` | `cells/sdfbbn/sky130_fd_sc_hd__sdfbbn_1.gds` | Complex sequential / isolation macro |
| 5 | 23,022 B (22.48 KB) | `sedfxtp_4` | `cells/sedfxtp/sky130_fd_sc_hd__sedfxtp_4.gds` | Complex sequential / isolation macro |

---

## 7. Comparison: Rule2DRC Testcases vs. Sky130 HD Standard Cells

| Metric | Rule2DRC Testcase GDS (`testcases.parquet`) | Sky130 HD Standard Cell GDS (`sky130_fd_sc_hd`) |
|---|---|---|
| **Total Files** | 13,921 synthetic rule snippets | 437 production library cells |
| **Total Size** | 4.68 MB | 4.03 MB |
| **Mean Size** | 352.6 Bytes | 9659 Bytes (~9.4 KB) |
| **Median Size** | 362.0 Bytes | 8254 Bytes (~8.1 KB) |
| **Size Range** | 106 B – 1,930 B (0.10 KB – 1.88 KB) | 1,370 B – 23,996 B (1.3 KB – 23.4 KB) |
| **Layout Content** | Minimal test polygons targeting single DRC rules (e.g. 2 shapes with specific spacing) | Full production standard cell layouts (wells, diffusions, poly gates, contacts, pins, local interconnect, power rails) |
