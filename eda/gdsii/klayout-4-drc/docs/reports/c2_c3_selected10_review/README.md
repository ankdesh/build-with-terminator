# Ten selected C2+C3 repair cases

[Open the 10-page A3 PDF](../../../output/pdf/c2_c3_selected10_repair_review.pdf)

One case per page. Each page shows the full layout, input defect, verified reference fix, actual agent attempt and actual heuristic attempt.
Reference fixes are evaluator evidence. They are not agent or heuristic successes. Both methods scored 0/30 accepted repairs in the full campaign.
Two repair cases are selected per level, one from each source group. This is an explanatory selection, not a performance sample.

| Case | Level | Scored input markers | Agent | Heuristic | Reference |
|---|---|---|---|---|---|
| l1_g0_c0 | L1 | {'M1.W.1': 1} | invalid_patch | unresolved | 0 markers; policy pass |
| l1_g1_c2 | L1 | {'V1.M2.EN.2': 1} | unresolved | unresolved | 0 markers; policy pass |
| l2_g0_c1 | L2 | {'M1.S.1': 1, 'M3.W.1': 1} | invalid_patch | unresolved | 0 markers; policy pass |
| l2_g1_c1 | L2 | {'M1.W.1': 1, 'M1.A.1': 1, 'M3.W.1': 1} | invalid_patch | unresolved | 0 markers; policy pass |
| l3_g0_c1 | L3 | {'M3.W.1': 1} | unresolved | invalid_patch | 0 markers; policy pass |
| l3_g1_c2 | L3 | {'V2.W.1': 1} | invalid_patch | invalid_patch | 0 markers; policy pass |
| l4_g0_c0 | L4 | {'M2.W.1': 1} | unresolved | invalid_patch | 0 markers; policy pass |
| l4_g1_c2 | L4 | {'V2.W.1': 1} | unresolved | invalid_patch | 0 markers; policy pass |
| l5_g0_c0 | L5 | {'M2.W.1': 1, 'V2.M2.EN.1': 1} | unresolved | invalid_patch | 0 markers; policy pass |
| l5_g1_c1 | L5 | {'M2.W.1': 1, 'V2.M2.EN.1': 1} | invalid_patch | invalid_patch | 0 markers; policy pass |

Red marks are saved scored checker markers. Teal outlines show spatial edit bounds; cell and layer restrictions also apply.
Cyan outlines on reference views show the actual geometry delta, including additions and removals.
Input, reference and candidate details use the same physical camera and scale.
A rejected output has no after-DRC result; missing red lines do not mean that it passes.
The full public deck is a separate audit. Electrical connectivity and timing are not verified.
No input, reference, campaign artifact, prompt or result was changed. No new checker, model or repair was run.
