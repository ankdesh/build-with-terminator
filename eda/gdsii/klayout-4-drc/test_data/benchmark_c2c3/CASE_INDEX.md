# C2+C3 case index

The corpus contains 50 qualified full GDS inputs: 30 repair cases, 10 clean controls, and 10 read-only cases. Inspection clips are additional files. They are never scored.

Primary checker: `asap7_c2c3_v1`. Full public audits use `asap7_public_full` for diagnosis. Connectivity and timing are unverified.

| Case / full GDS | Level | Kind | Inspection clip | Instances | Depth | Eligible route segments | Context shapes | Rule categories |
|---|---:|---|---|---:|---:|---:|---:|---:|
| [l1_g0_c0](cases/l1_g0_c0.gds) | 1 | repair | [clip](windows/l1_g0_c0.gds) | 11 | 2 | n/a | 5 | 1 |
| [l1_g0_c1](cases/l1_g0_c1.gds) | 1 | repair | [clip](windows/l1_g0_c1.gds) | 11 | 2 | n/a | 7 | 1 |
| [l1_g0_c2](cases/l1_g0_c2.gds) | 1 | repair | [clip](windows/l1_g0_c2.gds) | 11 | 2 | n/a | 6 | 1 |
| [l1_g0_c3](cases/l1_g0_c3.gds) | 1 | clean_control | [clip](windows/l1_g0_c3.gds) | 11 | 2 | n/a | 7 | 0 |
| [l1_g0_c4](cases/l1_g0_c4.gds) | 1 | no_edit | [clip](windows/l1_g0_c4.gds) | 11 | 2 | n/a | 10 | 1 |
| [l1_g1_c0](cases/l1_g1_c0.gds) | 1 | repair | [clip](windows/l1_g1_c0.gds) | 16 | 2 | n/a | 7 | 1 |
| [l1_g1_c1](cases/l1_g1_c1.gds) | 1 | repair | [clip](windows/l1_g1_c1.gds) | 16 | 2 | n/a | 5 | 1 |
| [l1_g1_c2](cases/l1_g1_c2.gds) | 1 | repair | [clip](windows/l1_g1_c2.gds) | 16 | 2 | n/a | 5 | 1 |
| [l1_g1_c3](cases/l1_g1_c3.gds) | 1 | clean_control | [clip](windows/l1_g1_c3.gds) | 16 | 2 | n/a | 8 | 0 |
| [l1_g1_c4](cases/l1_g1_c4.gds) | 1 | no_edit | [clip](windows/l1_g1_c4.gds) | 16 | 2 | n/a | 6 | 1 |
| [l2_g0_c0](cases/l2_g0_c0.gds) | 2 | repair | [clip](windows/l2_g0_c0.gds) | 103 | 4 | n/a | 6 | 2 |
| [l2_g0_c1](cases/l2_g0_c1.gds) | 2 | repair | [clip](windows/l2_g0_c1.gds) | 103 | 4 | n/a | 8 | 2 |
| [l2_g0_c2](cases/l2_g0_c2.gds) | 2 | repair | [clip](windows/l2_g0_c2.gds) | 103 | 4 | n/a | 8 | 2 |
| [l2_g0_c3](cases/l2_g0_c3.gds) | 2 | clean_control | [clip](windows/l2_g0_c3.gds) | 103 | 4 | n/a | 8 | 0 |
| [l2_g0_c4](cases/l2_g0_c4.gds) | 2 | no_edit | [clip](windows/l2_g0_c4.gds) | 103 | 4 | n/a | 13 | 2 |
| [l2_g1_c0](cases/l2_g1_c0.gds) | 2 | repair | [clip](windows/l2_g1_c0.gds) | 148 | 4 | n/a | 8 | 2 |
| [l2_g1_c1](cases/l2_g1_c1.gds) | 2 | repair | [clip](windows/l2_g1_c1.gds) | 148 | 4 | n/a | 10 | 3 |
| [l2_g1_c2](cases/l2_g1_c2.gds) | 2 | repair | [clip](windows/l2_g1_c2.gds) | 148 | 4 | n/a | 12 | 2 |
| [l2_g1_c3](cases/l2_g1_c3.gds) | 2 | clean_control | [clip](windows/l2_g1_c3.gds) | 148 | 4 | n/a | 11 | 0 |
| [l2_g1_c4](cases/l2_g1_c4.gds) | 2 | no_edit | [clip](windows/l2_g1_c4.gds) | 148 | 4 | n/a | 18 | 3 |
| [l3_g0_c0](cases/l3_g0_c0.gds) | 3 | repair | [clip](windows/l3_g0_c0.gds) | 721 | 2 | 2632 | 43 | 1 |
| [l3_g0_c1](cases/l3_g0_c1.gds) | 3 | repair | [clip](windows/l3_g0_c1.gds) | 721 | 2 | 2632 | 37 | 1 |
| [l3_g0_c2](cases/l3_g0_c2.gds) | 3 | repair | [clip](windows/l3_g0_c2.gds) | 721 | 2 | 2632 | 32 | 1 |
| [l3_g0_c3](cases/l3_g0_c3.gds) | 3 | clean_control | [clip](windows/l3_g0_c3.gds) | 721 | 2 | 2632 | 36 | 0 |
| [l3_g0_c4](cases/l3_g0_c4.gds) | 3 | no_edit | [clip](windows/l3_g0_c4.gds) | 721 | 2 | 2632 | 36 | 1 |
| [l3_g1_c0](cases/l3_g1_c0.gds) | 3 | repair | [clip](windows/l3_g1_c0.gds) | 976 | 2 | 2567 | 30 | 1 |
| [l3_g1_c1](cases/l3_g1_c1.gds) | 3 | repair | [clip](windows/l3_g1_c1.gds) | 976 | 2 | 2567 | 30 | 1 |
| [l3_g1_c2](cases/l3_g1_c2.gds) | 3 | repair | [clip](windows/l3_g1_c2.gds) | 976 | 2 | 2567 | 25 | 1 |
| [l3_g1_c3](cases/l3_g1_c3.gds) | 3 | clean_control | [clip](windows/l3_g1_c3.gds) | 976 | 2 | 2567 | 42 | 0 |
| [l3_g1_c4](cases/l3_g1_c4.gds) | 3 | no_edit | [clip](windows/l3_g1_c4.gds) | 976 | 2 | 2567 | 42 | 1 |
| [l4_g0_c0](cases/l4_g0_c0.gds) | 4 | repair | [clip](windows/l4_g0_c0.gds) | 1909 | 2 | 5077 | 50 | 1 |
| [l4_g0_c1](cases/l4_g0_c1.gds) | 4 | repair | [clip](windows/l4_g0_c1.gds) | 1909 | 2 | 5077 | 58 | 1 |
| [l4_g0_c2](cases/l4_g0_c2.gds) | 4 | repair | [clip](windows/l4_g0_c2.gds) | 1909 | 2 | 5077 | 54 | 1 |
| [l4_g0_c3](cases/l4_g0_c3.gds) | 4 | clean_control | [clip](windows/l4_g0_c3.gds) | 1909 | 2 | 5077 | 53 | 0 |
| [l4_g0_c4](cases/l4_g0_c4.gds) | 4 | no_edit | [clip](windows/l4_g0_c4.gds) | 1909 | 2 | 5077 | 55 | 1 |
| [l4_g1_c0](cases/l4_g1_c0.gds) | 4 | repair | [clip](windows/l4_g1_c0.gds) | 1978 | 2 | 5524 | 55 | 1 |
| [l4_g1_c1](cases/l4_g1_c1.gds) | 4 | repair | [clip](windows/l4_g1_c1.gds) | 1978 | 2 | 5524 | 56 | 1 |
| [l4_g1_c2](cases/l4_g1_c2.gds) | 4 | repair | [clip](windows/l4_g1_c2.gds) | 1978 | 2 | 5524 | 55 | 1 |
| [l4_g1_c3](cases/l4_g1_c3.gds) | 4 | clean_control | [clip](windows/l4_g1_c3.gds) | 1978 | 2 | 5524 | 51 | 0 |
| [l4_g1_c4](cases/l4_g1_c4.gds) | 4 | no_edit | [clip](windows/l4_g1_c4.gds) | 1978 | 2 | 5524 | 52 | 1 |
| [l5_g0_c0](cases/l5_g0_c0.gds) | 5 | repair | [clip](windows/l5_g0_c0.gds) | 1852 | 2 | 4962 | 38 | 2 |
| [l5_g0_c1](cases/l5_g0_c1.gds) | 5 | repair | [clip](windows/l5_g0_c1.gds) | 1852 | 2 | 4962 | 37 | 2 |
| [l5_g0_c2](cases/l5_g0_c2.gds) | 5 | repair | [clip](windows/l5_g0_c2.gds) | 1852 | 2 | 4962 | 29 | 2 |
| [l5_g0_c3](cases/l5_g0_c3.gds) | 5 | clean_control | [clip](windows/l5_g0_c3.gds) | 1852 | 2 | 4962 | 28 | 0 |
| [l5_g0_c4](cases/l5_g0_c4.gds) | 5 | no_edit | [clip](windows/l5_g0_c4.gds) | 1852 | 2 | 4962 | 29 | 2 |
| [l5_g1_c0](cases/l5_g1_c0.gds) | 5 | repair | [clip](windows/l5_g1_c0.gds) | 1782 | 2 | 5500 | 33 | 2 |
| [l5_g1_c1](cases/l5_g1_c1.gds) | 5 | repair | [clip](windows/l5_g1_c1.gds) | 1782 | 2 | 5500 | 30 | 2 |
| [l5_g1_c2](cases/l5_g1_c2.gds) | 5 | repair | [clip](windows/l5_g1_c2.gds) | 1782 | 2 | 5500 | 26 | 2 |
| [l5_g1_c3](cases/l5_g1_c3.gds) | 5 | clean_control | [clip](windows/l5_g1_c3.gds) | 1782 | 2 | 5500 | 24 | 0 |
| [l5_g1_c4](cases/l5_g1_c4.gds) | 5 | no_edit | [clip](windows/l5_g1_c4.gds) | 1782 | 2 | 5500 | 28 | 2 |

Instance counts include structural and editable route cells. Zero target categories identify clean controls. Read-only cases retain defects under an immutable policy. Native source markers are separate from injected target markers.
