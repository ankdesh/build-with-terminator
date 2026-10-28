# C1 visual guide

[Read the PDF](../../output/pdf/c1_visual_guide.pdf)

The PDF has ten examples. See the image manifest for verified hashes, exact source paths,
integer geometry measurements, checker counts, and the saved verdicts.

## 01 A wire that is too narrow

`m1_w1_iso_01` | isolated | `clean_success`

The M1 rectangle is 10 nm wide and 100 nm long. Look at the two long red edges.

M1.W.1 requires a width of at least 18 nm. One marker identifies the narrow wire.

The heuristic expands the rectangle to 32 nm in width. It passes the five scoped rules and preservation checks.

A repair can pass yet add more metal than needed. This is geometry success, not proof of a good circuit.

[reference: full image](c1_visual_guide/01_m1_w1_iso_01_reference.png)

![m1_w1_iso_01 reference](c1_visual_guide/01_m1_w1_iso_01_reference.png)

[input: full image](c1_visual_guide/01_m1_w1_iso_01_input.png)

![m1_w1_iso_01 input](c1_visual_guide/01_m1_w1_iso_01_input.png)

[output: full image](c1_visual_guide/01_m1_w1_iso_01_output.png)

![m1_w1_iso_01 output](c1_visual_guide/01_m1_w1_iso_01_output.png)

## 02 A narrow section inside a wider wire

`m1_w1_iso_08` | isolated | `clean_success`

The outside width is 24 nm. The middle section is only 12 nm wide. Look at the neck between y = 30 and 70 nm.

M1.W.1 requires at least 18 nm at the narrow section. The outside bounding box cannot show this fault.

The heuristic expands the polygon. The narrow section becomes 24 nm wide. The saved after-check has no scoped marker.

Check local shape width. A wide overall outline can still contain a narrow section.

[reference: full image](c1_visual_guide/02_m1_w1_iso_08_reference.png)

![m1_w1_iso_08 reference](c1_visual_guide/02_m1_w1_iso_08_reference.png)

[input: full image](c1_visual_guide/02_m1_w1_iso_08_input.png)

![m1_w1_iso_08 input](c1_visual_guide/02_m1_w1_iso_08_input.png)

[output: full image](c1_visual_guide/02_m1_w1_iso_08_output.png)

![m1_w1_iso_08 output](c1_visual_guide/02_m1_w1_iso_08_output.png)

## 03 One database step below the limit

`m1_w1_bnd_01` | boundary | `clean_success`

The wire is 17.75 nm wide. It is 71 database units wide. Look at the red side edges.

M1.W.1 requires 18 nm, or 72 database units. The 0.25 nm shortfall produces one marker.

The heuristic expands the wire to 39.75 nm in width. The saved output passes the scoped geometry checks.

A small difference can change a checker result. Exact integer coordinates matter.

[reference: full image](c1_visual_guide/03_m1_w1_bnd_01_reference.png)

![m1_w1_bnd_01 reference](c1_visual_guide/03_m1_w1_bnd_01_reference.png)

[input: full image](c1_visual_guide/03_m1_w1_bnd_01_input.png)

![m1_w1_bnd_01 input](c1_visual_guide/03_m1_w1_bnd_01_input.png)

[output: full image](c1_visual_guide/03_m1_w1_bnd_01_output.png)

![m1_w1_bnd_01 output](c1_visual_guide/03_m1_w1_bnd_01_output.png)

## 04 At the limit: a clean control

`m1_w1_bnd_04` | boundary | `unnecessary_edit`

The wire is exactly 18 nm wide. It is 72 database units wide. It has no input marker.

M1.W.1 accepts this width. The other four scoped checks also produce no marker.

The heuristic still expands the wire to 30 nm in width. It remains checker-clean, but the recorded outcome is unnecessary_edit.

A clean output alone does not prove useful repair. A clean input should stay unchanged.

[reference: full image](c1_visual_guide/04_m1_w1_bnd_04_reference.png)

![m1_w1_bnd_04 reference](c1_visual_guide/04_m1_w1_bnd_04_reference.png)

[input: full image](c1_visual_guide/04_m1_w1_bnd_04_input.png)

![m1_w1_bnd_04 input](c1_visual_guide/04_m1_w1_bnd_04_input.png)

[output: full image](c1_visual_guide/04_m1_w1_bnd_04_output.png)

![m1_w1_bnd_04 output](c1_visual_guide/04_m1_w1_bnd_04_output.png)

## 05 The same type of check on M2

`m2_w1_iso_06` | isolated | `clean_success`

The horizontal M2 wire is 100 nm long and 12 nm wide. M2 is the amber layer, 20/0.

M2.W.1 requires at least 18 nm. The pair of horizontal red edges marks the narrow width.

The heuristic expands the wire to 22 nm in width. The saved output has no scoped marker.

Layer numbers select which rule applies. Screen colour is only a viewer setting.

[reference: full image](c1_visual_guide/05_m2_w1_iso_06_reference.png)

![m2_w1_iso_06 reference](c1_visual_guide/05_m2_w1_iso_06_reference.png)

[input: full image](c1_visual_guide/05_m2_w1_iso_06_input.png)

![m2_w1_iso_06 input](c1_visual_guide/05_m2_w1_iso_06_input.png)

[output: full image](c1_visual_guide/05_m2_w1_iso_06_output.png)

![m2_w1_iso_06 output](c1_visual_guide/05_m2_w1_iso_06_output.png)

## 06 Width passes, but area fails

`m1_a1_iso_01` | isolated | `clean_success`

The M1 pad is 18 by 18 nm. Its area is 324 square nm. Look at the red polygon outline.

M1.A.1 requires at least 504 square nm. The width is legal, but the pad area is too small.

The heuristic makes a 30 by 30 nm pad. Its area is 900 square nm. The saved output has no scoped marker.

Width measures a distance. Area measures a surface. Passing one does not imply passing the other.

[reference: full image](c1_visual_guide/06_m1_a1_iso_01_reference.png)

![m1_a1_iso_01 reference](c1_visual_guide/06_m1_a1_iso_01_reference.png)

[input: full image](c1_visual_guide/06_m1_a1_iso_01_input.png)

![m1_a1_iso_01 input](c1_visual_guide/06_m1_a1_iso_01_input.png)

[output: full image](c1_visual_guide/06_m1_a1_iso_01_output.png)

![m1_a1_iso_01 output](c1_visual_guide/06_m1_a1_iso_01_output.png)

## 07 A small gap and an invalid shortcut

`m1_s1_iso_01` | isolated | `invalid_patch`

Two M1 wires are each 40 nm wide and 80 nm long. Their gap is 10 nm. Look between the wires.

M1.S.1 flags this gap. The facing edges are longer than 36 nm, and the scoped minimum spacing is 18 nm.

The heuristic expands the wires until they join. The component count changes from two to one. Validation rejects the patch before after-DRC.

Joining separate wires is not an acceptable repair. Preservation checks must pass before success can be scored.

[reference: full image](c1_visual_guide/07_m1_s1_iso_01_reference.png)

![m1_s1_iso_01 reference](c1_visual_guide/07_m1_s1_iso_01_reference.png)

[input: full image](c1_visual_guide/07_m1_s1_iso_01_input.png)

![m1_s1_iso_01 input](c1_visual_guide/07_m1_s1_iso_01_input.png)

[output: full image](c1_visual_guide/07_m1_s1_iso_01_output.png)

![m1_s1_iso_01 output](c1_visual_guide/07_m1_s1_iso_01_output.png)

## 08 A narrow gap with no scoped marker

`m1_s1_neg_03` | negative | `invalid_patch`

Two M1 stubs are 40 nm wide and only 30 nm long. Their gap is 12 nm. The input has no marker.

This deck filters spacing results using edges up to 36 nm long. These short stubs do not produce an M1.S.1 marker.

The heuristic expands the stubs and joins them. Validation rejects the two-to-one component change. After-DRC is not run.

No marker means no fault found by these checks. It does not prove compliance with every ASAP7 spacing rule.

[reference: full image](c1_visual_guide/08_m1_s1_neg_03_reference.png)

![m1_s1_neg_03 reference](c1_visual_guide/08_m1_s1_neg_03_reference.png)

[input: full image](c1_visual_guide/08_m1_s1_neg_03_input.png)

![m1_s1_neg_03 input](c1_visual_guide/08_m1_s1_neg_03_input.png)

[output: full image](c1_visual_guide/08_m1_s1_neg_03_output.png)

![m1_s1_neg_03 output](c1_visual_guide/08_m1_s1_neg_03_output.png)

## 09 One via shape, two width markers

`v1_w1_iso_01` | isolated | `clean_success`

The V1 square is 10 by 10 nm. The checker marks the horizontal and vertical width directions.

V1.W.1 requires at least 18 nm. One square produces two edge-pair markers. Marker count is not shape count.

The heuristic expands V1 to 20 by 20 nm and adds M1 metal. The saved output has no scoped marker.

This deck checks via width. It does not prove via enclosure, a square-cut rule, or electrical connection.

[reference: full image](c1_visual_guide/09_v1_w1_iso_01_reference.png)

![v1_w1_iso_01 reference](c1_visual_guide/09_v1_w1_iso_01_reference.png)

[input: full image](c1_visual_guide/09_v1_w1_iso_01_input.png)

![v1_w1_iso_01 input](c1_visual_guide/09_v1_w1_iso_01_input.png)

[output: full image](c1_visual_guide/09_v1_w1_iso_01_output.png)

![v1_w1_iso_01 output](c1_visual_guide/09_v1_w1_iso_01_output.png)

## 10 Two layers cross in a flat view

`m2_w1_int_02` | interaction | `clean_success`

A 12 nm M1 wire runs vertically. A 12 nm M2 wire crosses it horizontally. Both layers appear in this flat view.

M1.W.1 and M2.W.1 each produce one marker. Each wire fails its own width check.

The heuristic widens both wires. The saved output passes the five scoped checks and component checks.

An overlap in a two-dimensional drawing does not prove a connection between layers. A circuit needs more evidence.

[reference: full image](c1_visual_guide/10_m2_w1_int_02_reference.png)

![m2_w1_int_02 reference](c1_visual_guide/10_m2_w1_int_02_reference.png)

[input: full image](c1_visual_guide/10_m2_w1_int_02_input.png)

![m2_w1_int_02 input](c1_visual_guide/10_m2_w1_int_02_input.png)

[output: full image](c1_visual_guide/10_m2_w1_int_02_output.png)

![m2_w1_int_02 output](c1_visual_guide/10_m2_w1_int_02_output.png)
