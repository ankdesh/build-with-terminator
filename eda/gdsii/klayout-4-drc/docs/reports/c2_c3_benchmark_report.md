# C2+C3 five-level ASAP7 benchmark results

The corpus contains **50 qualified full GDS cases**: **30 repair cases, 10 clean controls, and 10 no-edit controls**. Both independent generations pass the reproduction check. All 30 hidden reference repairs pass their edit policies and scored checks.

Primary scope: `asap7_c2c3_v1`. Full public audits use `asap7_public_full` for diagnosis and do not change the primary score. All results are geometry-only. Connectivity and timing are unverified.

| Method | Repairs / 30 | Clean restraint / 10 | No-edit restraint / 10 |
|---|---:|---:|---:|
| agent | 0 (0%) | 9 (90%) | 4 (40%) |
| heuristic | 0 (0%) | 4 (40%) | 4 (40%) |
| no_change | 0 (0%) | 10 (100%) | 10 (100%) |

The campaign made **50 Bedrock request attempts**. There were **49 parsed responses** and **zero retries**. One request timed out after 90 seconds. The initial dispatcher stopped after 40 attempts. A recorded continuation sent only the ten unrequested L5 cases. Every prior outcome, including the timeout, remains unchanged.

| Level | Model repairs / 6 | Model clean / 2 | Model no-edit / 2 |
|---|---:|---:|---:|
| L1 | 0 | 2 | 1 |
| L2 | 0 | 1 | 0 |
| L3 | 0 | 2 | 2 |
| L4 | 0 | 2 | 0 |
| L5 | 0 | 2 | 1 |

The model did not deliver an accepted repair. The failure counts below separate runtime failures, response-format failures, policy failures, and valid outputs that left defects unresolved. The existing heuristic copies or changes protected top-cell content in routed cases. Its twelve valid C2 repair outputs remain unchanged.

| Model outcome type | Cases |
|---|---:|
| API or transport timeout | 1 |
| Edit policy violation | 6 |
| Control restraint passed | 13 |
| Python script failed | 12 |
| Invalid response fields | 7 |
| Unchanged repair output | 11 |

Observed script errors include calls to `Box.sized`, `Layout.layout_io`, and `PolygonWithProperties.width_check`. The diagnostics file retains each error and policy rejection.

An inherited prompt requirement says to replace shapes in the top cell. The more specific case-policy section restricts edits to named route cells. That wording can create friction and may contribute to protected-cell failures. It was kept frozen throughout evaluation. These results assess the tested model, prompt, API guidance, and executor together; they do not isolate intrinsic geometric reasoning ability.

| Level | Instances including structure/fillers | Hierarchy depth | Eligible signal route segments | Coupled categories in repair cases |
|---|---|---|---|---|
| L1 | 11, 16 | 2 | not applicable | 1 |
| L2 | 103, 148 | 4 | not applicable | 2, 3 |
| L3 | 721, 976 | 2 | 2567, 2632 | 1 |
| L4 | 1909, 1978 | 2 | 5077, 5524 | 1 |
| L5 | 1782, 1852 | 2 | 4962, 5500 | 2 |

The median count of protected polygons that intersect repair inspection windows rises from **28.5 in L3 to 50.0 in L4**. L5 local M2/M3 metal occupancy is **1.275–2.716 times** the matching L4 window. All six L5 repairs couple M2 width and V2 enclosure by M2 on the same landing geometry.

The scored profile has eleven qualified checks. Nine families occur as injected repair targets. M2 spacing and V2 enclosure by M3 are qualified regression guards; this corpus has no injected repair target for those two checks. The 24 boundary fixtures pass, and all legal fixtures have zero scored markers. A separate seven-shape test checks the corrected V2/M2 orientation behavior.

The derived profile corrects the public V2/M2 expression. The public and C1 decks remain unchanged. The V1/M2 checker requires a 6 nm cap on the verified 1 nm grid despite its nominal 5 nm description. These are qualified research checks, not foundry signoff.

| Source group | Original public deck markers |
|---|---:|
| l3_source_0 | 43 |
| l3_source_1 | 36 |
| l4_source_0 | 58 |
| l4_source_1 | 78 |
| l5_source_0 | 68 |
| l5_source_1 | 74 |

All clean controls have zero native markers under the scored profile. The public deck reports unrelated source markers. A clean-control label therefore describes the scored scope; it does not claim a globally clean source. No-edit controls retain their injected defects. Their passing result means successful completion with unchanged geometry.

| Method | Public audits completed | Public audits failed | Not run on invalid candidates |
|---|---:|---:|---:|
| agent | 24 | 0 | 26 |
| heuristic | 20 | 0 | 30 |
| no_change | 50 | 0 | 0 |

Model: `qwen.qwen3-coder-next`, provider `bedrock`, region `ap-southeast-2`. Temperature and output-token limit were omitted, so provider defaults apply. Requests use JSON-object response format and a 90-second transport timeout. Known usage: **595,428 prompt tokens** and **61,537 completion tokens**, covering 49 responses. Usage for unreturned attempts and API cost are unknown.

ORFS is pinned to `64939f3717ad7c694199ba04cb98924b98022868`. The official container digest, submodule pins, collateral hashes, and actual binary hashes are retained. OpenROAD reports an unknown version string, so its image digest and binary hash identify it. The scored host checker is KLayout 0.28.16; the Python geometry library is 0.30.8. The public checker limit is 600 seconds and the scored limit is 120 seconds.

Source builds ran serially with two threads, an 8 GiB ceiling, available-RAM checks, and a 60-minute attempt limit. Evaluation modes shared one host concurrently. Runtime values are descriptive and do not support speed comparisons. Worker memory is sampled process-tree RSS, a lower bound. Corpus reproduction uses the same retained routed source artifacts; it does not repeat the OpenROAD builds.

Validation: the full regression run passed 233 tests with 2 skips. After the final C2+C3 refinements, all 33 focused tests passed. TypeScript checking and both Node test files passed. The checks cover transforms, arrays, protected masters, clock/power edits, route deletion, boundary edits, context limits, native-marker persistence, and missing dependencies.

There are six repair cases per level and one model attempt per case. This is a feasibility result for the tested configuration. It does not establish model consistency or broad generalization. Use C1 or separate development fixtures for any future prompt changes; do not retune this frozen campaign.

[Case index and full GDS files](../../test_data/benchmark_c2c3/CASE_INDEX.md) · [Source and verification receipts](../../test_data/benchmark_c2c3/provenance/README.md) · [Paired outcomes](c2_c3_benchmark/comparison.csv) · [Failure diagnostics](c2_c3_benchmark/failure_analysis.csv) · [Accounting JSON](c2_c3_benchmark/accounting.json)

Per-mode JSON, CSV, breakdown tables, Markdown, and frozen-source snapshots are in `docs/reports/c2_c3_benchmark/`. Full before/after GDS, marker reports, requests, responses, scripts, logs, and artifact hashes remain under `reports/runs/c2c3_v1_*`. A failed script or rejected policy can leave no scored after-report; that missing evidence earns no repair or restraint credit.
