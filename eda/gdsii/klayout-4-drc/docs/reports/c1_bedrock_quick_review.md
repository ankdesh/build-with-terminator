# C1 Bedrock quick review

[Open the 20-case PDF](../../output/pdf/c1_bedrock_quick_review.pdf)

Ten successful repairs and ten unsuccessful attempts from the strict-API 100-case Bedrock campaign.
The selection shows different outcomes. It is not a statistical sample.

All geometry and red markers come from saved evidence. Five missing output panels are explicit placeholders.
The original heuristic review and all campaign evidence are unchanged.

## 01 m1_w1_iso_04 - FIXED

Recorded verdict: `clean_success`.

M1 width: 15 -> 18 nm. Minimum: 18 nm.

Markers: 1 -> 0. The output widens the wire to the required width.

[reference panel](c1_bedrock_quick_review/01_m1_w1_iso_04_reference.png)

[input panel](c1_bedrock_quick_review/01_m1_w1_iso_04_input.png)

[output panel](c1_bedrock_quick_review/01_m1_w1_iso_04_output.png)

## 02 m1_w1_bnd_01 - FIXED

Recorded verdict: `clean_success`.

M1 input: 17.75 nm, one DBU below the 18 nm limit.

Markers: 1 -> 0. A small sizing step clears the boundary violation.

[reference panel](c1_bedrock_quick_review/02_m1_w1_bnd_01_reference.png)

[input panel](c1_bedrock_quick_review/02_m1_w1_bnd_01_input.png)

[output panel](c1_bedrock_quick_review/02_m1_w1_bnd_01_output.png)

## 03 m2_w1_iso_01 - FIXED

Recorded verdict: `clean_success`.

M2 width: 10 -> 18 nm. Minimum: 18 nm.

Markers: 1 -> 0. The output changes M2 and keeps one component.

[reference panel](c1_bedrock_quick_review/03_m2_w1_iso_01_reference.png)

[input panel](c1_bedrock_quick_review/03_m2_w1_iso_01_input.png)

[output panel](c1_bedrock_quick_review/03_m2_w1_iso_01_output.png)

## 04 m2_w1_int_02 - FIXED

Recorded verdict: `clean_success`.

Crossing M1 and M2: both widths grow from 12 to 18 nm.

Markers: 2 -> 0. Both metal width checks pass after the repair.

[reference panel](c1_bedrock_quick_review/04_m2_w1_int_02_reference.png)

[input panel](c1_bedrock_quick_review/04_m2_w1_int_02_input.png)

[output panel](c1_bedrock_quick_review/04_m2_w1_int_02_output.png)

## 05 m1_a1_iso_02 - FIXED

Recorded verdict: `clean_success`.

M1 pad area: 360 -> 675 nm2. Minimum: 504 nm2.

Markers: 1 -> 0. Legal width alone did not give enough input area.

[reference panel](c1_bedrock_quick_review/05_m1_a1_iso_02_reference.png)

[input panel](c1_bedrock_quick_review/05_m1_a1_iso_02_input.png)

[output panel](c1_bedrock_quick_review/05_m1_a1_iso_02_output.png)

## 06 m1_a1_int_02 - FIXED

Recorded verdict: `clean_success`.

Two M1 pads: each area grows from 360 to 505.25 nm2.

Markers: 2 -> 0. The output keeps two separate components.

[reference panel](c1_bedrock_quick_review/06_m1_a1_int_02_reference.png)

[input panel](c1_bedrock_quick_review/06_m1_a1_int_02_input.png)

[output panel](c1_bedrock_quick_review/06_m1_a1_int_02_output.png)

## 07 m1_s1_iso_06 - FIXED

Recorded verdict: `clean_success`.

M1 horizontal-wire gap: 12 -> 18 nm. Minimum: 18 nm.

Markers: 1 -> 0. One wire moves; the two wires remain separate.

[reference panel](c1_bedrock_quick_review/07_m1_s1_iso_06_reference.png)

[input panel](c1_bedrock_quick_review/07_m1_s1_iso_06_input.png)

[output panel](c1_bedrock_quick_review/07_m1_s1_iso_06_output.png)

## 08 m1_s1_iso_07 - FIXED

Recorded verdict: `clean_success`.

M1 horizontal-wire gap: 14 -> 18 nm. Minimum: 18 nm.

Markers: 1 -> 0. The output increases spacing without adding metal.

[reference panel](c1_bedrock_quick_review/08_m1_s1_iso_07_reference.png)

[input panel](c1_bedrock_quick_review/08_m1_s1_iso_07_input.png)

[output panel](c1_bedrock_quick_review/08_m1_s1_iso_07_output.png)

## 09 v1_w1_iso_02 - FIXED

Recorded verdict: `clean_success`.

V1 square: 12 x 12 -> 18 x 18 nm. Minimum width: 18 nm.

Markers: 2 -> 0. Both width directions pass the scoped checker.

[reference panel](c1_bedrock_quick_review/09_v1_w1_iso_02_reference.png)

[input panel](c1_bedrock_quick_review/09_v1_w1_iso_02_input.png)

[output panel](c1_bedrock_quick_review/09_v1_w1_iso_02_output.png)

## 10 v1_w1_int_02 - FIXED

Recorded verdict: `clean_success`.

V1: 18 x 12 -> 36 x 30 nm. M2 width: 14 -> 32 nm.

Markers: 2 -> 0. Both layers grow; this repair adds extra material.

[reference panel](c1_bedrock_quick_review/10_v1_w1_int_02_reference.png)

[input panel](c1_bedrock_quick_review/10_v1_w1_int_02_input.png)

[output panel](c1_bedrock_quick_review/10_v1_w1_int_02_output.png)

## 11 m1_w1_iso_02 - NOT FIXED

Recorded verdict: `failed_unchanged`.

M1 width stays at 12 nm. Minimum: 18 nm.

Markers: 1 -> 1. The output geometry is unchanged.

[reference panel](c1_bedrock_quick_review/11_m1_w1_iso_02_reference.png)

[input panel](c1_bedrock_quick_review/11_m1_w1_iso_02_input.png)

[output panel](c1_bedrock_quick_review/11_m1_w1_iso_02_output.png)

## 12 m1_s1_iso_01 - NOT FIXED

Recorded verdict: `failed_unchanged`.

M1 wire gap stays at 10 nm. Minimum scoped spacing: 18 nm.

Markers: 1 -> 1. The script runs but does not repair the gap.

[reference panel](c1_bedrock_quick_review/12_m1_s1_iso_01_reference.png)

[input panel](c1_bedrock_quick_review/12_m1_s1_iso_01_input.png)

[output panel](c1_bedrock_quick_review/12_m1_s1_iso_01_output.png)

## 13 v1_w1_iso_03 - REGRESSION

Recorded verdict: `regression`.

V1 square: 14 x 14 -> 18 x 14 nm. One direction still fails.

Markers: 2 -> 1. Saved marker comparison flags one introduced marker.

[reference panel](c1_bedrock_quick_review/13_v1_w1_iso_03_reference.png)

[input panel](c1_bedrock_quick_review/13_v1_w1_iso_03_input.png)

[output panel](c1_bedrock_quick_review/13_v1_w1_iso_03_output.png)

## 14 m2_w1_int_01 - PARTIAL

Recorded verdict: `partial_success`.

M2 width: 14 -> 18 nm. V1 stays at 18 x 12 nm.

Markers: 2 -> 1. M2 is fixed; the V1 width fault remains.

[reference panel](c1_bedrock_quick_review/14_m2_w1_int_01_reference.png)

[input panel](c1_bedrock_quick_review/14_m2_w1_int_01_input.png)

[output panel](c1_bedrock_quick_review/14_m2_w1_int_01_output.png)

## 15 m1_s1_iso_05 - REJECTED

Recorded verdict: `invalid_patch`.

M1 gap: 16 nm. The attempted expansion joins both wires.

Components: 2 -> 1. Preservation rejects the output; no after-DRC.

[reference panel](c1_bedrock_quick_review/15_m1_s1_iso_05_reference.png)

[input panel](c1_bedrock_quick_review/15_m1_s1_iso_05_input.png)

[output panel](c1_bedrock_quick_review/15_m1_s1_iso_05_output.png)

## 16 m1_w1_iso_10 - API ERROR

Recorded verdict: `invalid_patch`.

The M1 branch is 12 nm thick. The script fails before output.

API failure: Box.left_bottom does not exist. No after-DRC result.

[reference panel](c1_bedrock_quick_review/16_m1_w1_iso_10_reference.png)

[input panel](c1_bedrock_quick_review/16_m1_w1_iso_10_input.png)

[output panel](c1_bedrock_quick_review/16_m1_w1_iso_10_output.png)

## 17 v1_w1_iso_01 - API ERROR

Recorded verdict: `invalid_patch`.

V1 input: 10 x 10 nm. It has two width markers.

API failure: Region.interacting receives EdgePairs. No output layout.

[reference panel](c1_bedrock_quick_review/17_v1_w1_iso_01_reference.png)

[input panel](c1_bedrock_quick_review/17_v1_w1_iso_01_input.png)

[output panel](c1_bedrock_quick_review/17_v1_w1_iso_01_output.png)

## 18 m1_w1_neg_01 - CLEAN / ERROR

Recorded verdict: `invalid_patch`.

The 18 nm M1 input already passes. The attempted script crashes.

API failure: PolygonWithProperties.polygon. This is a clean control.

[reference panel](c1_bedrock_quick_review/18_m1_w1_neg_01_reference.png)

[input panel](c1_bedrock_quick_review/18_m1_w1_neg_01_input.png)

[output panel](c1_bedrock_quick_review/18_m1_w1_neg_01_output.png)

## 19 m1_w1_iso_08 - SYNTAX ERROR

Recorded verdict: `invalid_patch`.

M1 has a 12 nm neck inside a 24 nm outside width.

IndentationError at line 60. The repair script cannot start.

[reference panel](c1_bedrock_quick_review/19_m1_w1_iso_08_reference.png)

[input panel](c1_bedrock_quick_review/19_m1_w1_iso_08_input.png)

[output panel](c1_bedrock_quick_review/19_m1_w1_iso_08_output.png)

## 20 m1_a1_iso_01 - JSON ERROR

Recorded verdict: `model_error`.

M1 pad: 18 x 18 nm; area 324 nm2. Minimum area: 504 nm2.

The response omits rationale. Validation stops before script execution.

[reference panel](c1_bedrock_quick_review/20_m1_a1_iso_01_reference.png)

[input panel](c1_bedrock_quick_review/20_m1_a1_iso_01_input.png)

[output panel](c1_bedrock_quick_review/20_m1_a1_iso_01_output.png)
