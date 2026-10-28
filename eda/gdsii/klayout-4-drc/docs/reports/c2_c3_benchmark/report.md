# C2+C3 matched comparison

All results are geometry-only.
Primary scope: `asap7_c2c3_v1`. Full public audit: `asap7_public_full`, diagnostic only.

| Mode | Repairs / 30 | Clean controls / 10 | Read-only controls / 10 |
|---|---:|---:|---:|
| agent | 0 | 9 | 4 |
| heuristic | 0 | 4 | 4 |
| no_change | 0 | 10 | 10 |

Model request attempts: 50; responses: 49.

Blocked cases are completion accounting, not model-performance observations.

| Case | Level | Kind | Agent | Heuristic | No change |
|---|---:|---|---|---|---|
| l1_g0_c0 | 1 | repair | invalid_patch | unresolved | unresolved |
| l1_g0_c1 | 1 | repair | model_error | unresolved | unresolved |
| l1_g0_c2 | 1 | repair | unresolved | unresolved | unresolved |
| l1_g0_c3 | 1 | clean_control | unchanged_control | unchanged_control | unchanged_control |
| l1_g0_c4 | 1 | no_edit | unchanged_control | unchanged_control | unchanged_control |
| l1_g1_c0 | 1 | repair | unresolved | unresolved | unresolved |
| l1_g1_c1 | 1 | repair | invalid_patch | unresolved | unresolved |
| l1_g1_c2 | 1 | repair | unresolved | unresolved | unresolved |
| l1_g1_c3 | 1 | clean_control | unchanged_control | unchanged_control | unchanged_control |
| l1_g1_c4 | 1 | no_edit | invalid_patch | unchanged_control | unchanged_control |
| l2_g0_c0 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g0_c1 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g0_c2 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g0_c3 | 2 | clean_control | invalid_patch | unchanged_control | unchanged_control |
| l2_g0_c4 | 2 | no_edit | invalid_patch | unchanged_control | unchanged_control |
| l2_g1_c0 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g1_c1 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g1_c2 | 2 | repair | invalid_patch | unresolved | unresolved |
| l2_g1_c3 | 2 | clean_control | unchanged_control | unchanged_control | unchanged_control |
| l2_g1_c4 | 2 | no_edit | invalid_patch | unchanged_control | unchanged_control |
| l3_g0_c0 | 3 | repair | invalid_patch | invalid_patch | unresolved |
| l3_g0_c1 | 3 | repair | unresolved | invalid_patch | unresolved |
| l3_g0_c2 | 3 | repair | invalid_patch | invalid_patch | unresolved |
| l3_g0_c3 | 3 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l3_g0_c4 | 3 | no_edit | unchanged_control | invalid_patch | unchanged_control |
| l3_g1_c0 | 3 | repair | unresolved | invalid_patch | unresolved |
| l3_g1_c1 | 3 | repair | unresolved | invalid_patch | unresolved |
| l3_g1_c2 | 3 | repair | invalid_patch | invalid_patch | unresolved |
| l3_g1_c3 | 3 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l3_g1_c4 | 3 | no_edit | unchanged_control | invalid_patch | unchanged_control |
| l4_g0_c0 | 4 | repair | unresolved | invalid_patch | unresolved |
| l4_g0_c1 | 4 | repair | model_error | invalid_patch | unresolved |
| l4_g0_c2 | 4 | repair | unresolved | invalid_patch | unresolved |
| l4_g0_c3 | 4 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l4_g0_c4 | 4 | no_edit | invalid_patch | invalid_patch | unchanged_control |
| l4_g1_c0 | 4 | repair | model_error | invalid_patch | unresolved |
| l4_g1_c1 | 4 | repair | invalid_patch | invalid_patch | unresolved |
| l4_g1_c2 | 4 | repair | unresolved | invalid_patch | unresolved |
| l4_g1_c3 | 4 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l4_g1_c4 | 4 | no_edit | model_error | invalid_patch | unchanged_control |
| l5_g0_c0 | 5 | repair | unresolved | invalid_patch | unresolved |
| l5_g0_c1 | 5 | repair | model_error | invalid_patch | unresolved |
| l5_g0_c2 | 5 | repair | model_error | invalid_patch | unresolved |
| l5_g0_c3 | 5 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l5_g0_c4 | 5 | no_edit | model_error | invalid_patch | unchanged_control |
| l5_g1_c0 | 5 | repair | unresolved | invalid_patch | unresolved |
| l5_g1_c1 | 5 | repair | invalid_patch | invalid_patch | unresolved |
| l5_g1_c2 | 5 | repair | model_error | invalid_patch | unresolved |
| l5_g1_c3 | 5 | clean_control | unchanged_control | invalid_patch | unchanged_control |
| l5_g1_c4 | 5 | no_edit | unchanged_control | invalid_patch | unchanged_control |

One attempt per case.
Electrical connectivity and timing unverified.
Few designs and six repair cases per level; no consistency or broad generalization claim.
