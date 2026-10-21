# Traceability to the Original ASAP7 Implementation Plan + Codex Handoff

**Purpose:** Preserve every original recommendation while reorganizing execution into Foundation → A → B → C and a separately designed Goal D. This is a sequencing change, not a withdrawal of the previous technical findings.

## 1. Original report is unchanged

The file `ORIGINAL_ASAP7_DRC_Agent_Codex_Implementation_Plan.md` is an exact copy of the previous complete report and remains the authoritative full issue inventory, detailed work-package specification, API examples and upstream references. It includes:

- All original findings **F01–F15** and dispositions.
- All original work packages **WP0–WP8** and their acceptance tests.
- All original recommended PRs **PR-00–PR-08**.
- Technology-profile, benchmark-manifest, and run-result schema examples.
- Research/validation claims and caveats (public KLayout is not foundry signoff; geometry-only is not electrically validated).

The new reports refine only implementation order, stage scope, and separate exit gates. Where the original says WP4 should be immediately integrated into the full pipeline, the staged approach deliberately defers WP4's *iterative* functions to Goal D while implementing WP3's one-shot execution and verification first.

## 2. Original work-package mapping

| Original WP | Original goal | New stage ownership | Notes |
|---|---|---|---|
| WP0 | Audit/pin baseline | 0 + A, plus B pinning | Run legacy baseline in A; pin real ASAP7 deck in B |
| WP1 | Technology/config/invocation repair | A (legacy isolation) + B (official mapping) | Do not silently overwrite mini profile |
| WP2 | Structured DRC/geometry context | B; hierarchy stress in C | Typed markers, XML-wrapped deck, rule catalog, recursion |
| WP3 | Safe execution + independent validation | **0 (mandatory first)**; electrical depth in C | Single attempt, apply, recheck, layout/connectivity gates |
| WP4 | Closed-loop DSH iteration | **D (separate goal)** | Retain all requirements, design later; do not block A/B/C |
| WP5 | Curated ASAP7 rule coverage | B | At least five independently validated categories |
| WP6 | Deterministic benchmark generation | C1/C2 | ~100 self-checking cases after validated generator |
| WP7 | OpenROAD RTL-to-GDS | C3 | Genuine routed designs, DEF/ODB/net ownership when available |
| WP8 | Scoring/reporting/CI | Basic per-run in 0; phased A/B; aggregate C4 | Reporting starts before A; deeper metrics grow incrementally |

## 3. Finding-by-finding disposition

| Finding | New stage | Maintained requirement |
|---|---|---|
| F01: wrong ASAP7 layer map | B | Official V0=18/0, M1=19/0, M2=20/0, V1=21/0, legacy separately labeled |
| F02: GDS DBU vs tech grid | 0/A/B | Read actual layout DBU, separate from manufacturing grid |
| F03: flow stops at save script | **0**; then D | Add one-shot patch execution/report now, iterative decision later |
| F04: silent model fallback | **0/A** | Explicit agent/heuristic provenance and model error |
| F05: global geometry edits can short nets | 0/A/C | Restrict edit domain; connectivity gate, never misstate full validation |
| F06: DRC deck variable mismatch | 0/B | Adapter `input/report` vs `in_gds/report_file` |
| F07: `.target.gds` fallback inconsistencies | **0** | Genuine `.lyrdb`, explicit alternate format only if tested |
| F08: one-line rule extraction inadequate | B | XML extraction, multi-constraint catalog |
| F09: top-cell-only geometry | B/C | Hierarchical instance-aware windows and typed markers |
| F10: three windows/rule and fixed halo | B/C | Context clustering, deterministic sampling, completeness flag |
| F11: parser complexity / identity | 0 baseline; B | Stable typed markers and cross-run comparison |
| F12: one mini test fixture | A then C | Preserve legacy; grow positive/negative suites |
| F13: mislabeled valid via example | A | Version fixture and confirm checker-observed truth |
| F14: duplicate model execution paths | 0; D architecture | Consistent single-shot contracts now, canonical loop decision later |
| F15: no realistic/large benchmark | C | Mutations, cells, OpenROAD, reproducible reports |

## 4. Stage-specific PR suggestion

The original PR numbering is retained in the unchanged reference but is **not a mandatory merge order** under the new staged structure. The following is a suggested implementation grouping:

| New PR | Contents | Merge gate |
|---|---|---|
| F-PR1 | Baseline, manifest, scripts/provenance modes, unique run directories | Pinned data and truthful baseline |
| F-PR2 | Sandbox apply, output integrity, before/after DRC, always-written report | End-to-end known-script and negative failures |
| F-PR3 | Single-shot DSH integration without retry, model-error behavior | One model run or explicitly blocked status |
| A-PR1 | Legacy suite/regressions and versioned honest small GDS cases | Old suite preserved, new mini-case fixtures pass |
| A-PR2 | Mini-deck agent/heuristic single-shot scoring/report examples | One full evidence bundle per mode |
| B-PR1 | Pinned public ASAP7 profile, correct mapping, CLI/deck adapter | Genuine parseable public `.lyrdb` |
| B-PR2 | Typed RDB/context/hierarchy + rule catalog | Source-to-marker traceability incl. edge-pairs |
| B-PR3 | Five verified BEOL rule categories and single-shot agent evaluation | Legal/illegal boundary fixtures and report |
| C-PR1 | Seeded mutation generator + manifest + self-validation | Reproducible ~100-case target |
| C-PR2 | Standard-cell/hierarchy fixtures and immutable masters | Correct transforms/edit enforcement |
| C-PR3 | OpenROAD build + baseline-dirty tracking + net context | One complete reproducible routed build |
| C-PR4 | Aggregate metrics/CI separation | Truthful per-rule results and blocked states |
| D-DESIGN | Independent closed-loop design ADR, not a code PR | Approved controller/state/feedback/budget semantics |
| D-PR* | Later implementation only after design review | Bounded reliable iteration on fixed A/B/C cases |

A PR may be split further, but it must not claim a later acceptance gate is complete by hiding unavailable dependencies. Keep default tests fast and hermetic.

## 5. Sequencing subtleties Codex must respect

1. **A runs before B:** The synthetic mini example uses nonstandard ASAP7 layer assignments; preserve it under `legacy_mini` to debug execution infrastructure. The correct real PDK mapping must be enforced under B's separate profile.
2. **0 runs before A:** A must not settle for `save_script.py`; a patch must actually run and a before/after DRC report must be generated, even if it fails.
3. **B before C:** The benchmark generator needs a verified rule oracle; do not generate scores for unreviewed categories.
4. **D is separate:** It can be designed once 0/A/B are reliable, but its automatic feedback/iteration is **not** required to declare A, B or C complete.
5. **Marker delta requires matching:** Aggregate category counts are useful, but spatially introduced/resolved markers need robust typed matching; report uncertainty until implemented.
6. **Connectivity matters:** For synthetic cases, explicit graph/net tags can check narrow invariants. For routed designs, use DEF/ODB/netlist-backed ownership or a trustworthy extractor. Do not promote geometry-only pass to full electrical validity.
7. **PDK provenance:** No unpinned upstream source. Record licenses and source hashes; do not uncritically patch upstream DRC semantics.

## 6. Codex kickoff prompts

### Foundation 0

> Read `00_README_Implementation_Roadmap.md`, `01_Foundation_Fix_Apply_Patch_Report.md` and the unchanged original plan. Inspect the current repository. Implement only a **single-attempt** Fix → Apply Patch → Report capability, with immutable input, sandboxed application, actual before/after DRC and truthful per-run artifacts. First propose file-level diffs and test contracts; do not add automatic retries.

### Phase A

> Read the Phase A document and Foundation 0. Keep the original synthetic mini test under an explicit legacy profile. Validate the agent and deterministic repair routes on the small GDS with positive and negative test cases and real before/after reports. Do not migrate this fixture to the full ASAP7 deck yet.

### Phase B

> Read Phase B and the original WP1/WP2/WP5. Pin upstream ASAP7 collateral, correct the authentic layer/DBU mapping, support KLayout `.lydrc` invocation, build a typed rule catalog/geometry context, and prove at least five public ASAP7 BEOL categories with boundary tests. Preserve Phase A compatibility.

### Phase C

> Read Phase C and original WP6/WP7/WP8. Implement deterministic rule-driven mutations and benchmark manifests; then hierarchy/standard-cell fixtures; then OpenROAD full routed ASAP7 designs. Reuse the unchanged single-shot executor/report, with explicit connectivity validation level and no closed-loop algorithm.

### Goal D

> Read `05_Separate_Goal_Closed_Loop_Repair.md` and original WP4. Produce an architecture decision record and detailed design (controller, state, rollback, budget, feedback, security and evaluation) before proposing any implementation. Do not merge D into A/B/C.

## 7. Definition of delivery for each stage

A human-reviewable report must include: exact files changed, exact commands run, actual results, missing dependencies and blocked items, a representative successful and failing run bundle where applicable, DRC deck/profile/model hashes, validation scope, and unresolved risks. No document in this package claims these experiments have been run.
