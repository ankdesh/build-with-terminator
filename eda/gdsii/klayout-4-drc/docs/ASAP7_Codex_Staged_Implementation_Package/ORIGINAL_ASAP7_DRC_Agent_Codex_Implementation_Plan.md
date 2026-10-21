# ASAP7 Agentic DRC Repair: Correctness Fixes and Benchmark Expansion

**Date:** 2026-10-21  
**Audience:** Codex (planning and incremental implementation)  
**Primary repository:** https://github.com/ankdesh/build-with-terminator/tree/main/eda/gdsii/klayout-4-drc  
**Scope:** ASAP7 only; KLayout + Python + existing DeepSeek Harness (DSH) architecture. No GT2N, no new agent framework.  
**Status:** Engineering plan; code changes and end-to-end experiments have **not** been executed as part of this report.

## 0. Goal and non-goals

Build an independently testable system that takes a versioned ASAP7 GDS and DRC deck, identifies violations, produces an agent-authored patch, **executes** it in isolation, rechecks the geometry and relevant circuit invariants, and reports a reproducible benchmark result. Once reliable, expand from a small three-rule synthetic example to a growing suite of rules, controlled mutations, standard-cell layouts and OpenROAD-generated routed blocks.

**Success is not simply reducing DRC marker count.** A patch is fully successful only when the selected DRC scope passes, there are no unapproved new markers, the intended electrical connectivity is preserved *when that can be independently verified*, and changes remain within the allowed edit scope. When connectivity is not verifiable, report `geometry_only` rather than `fully_validated`.

**Non-goals for initial ASAP7 milestone:** foundry signoff; complete LVS from scratch; automatic repair of arbitrary front-end transistor layouts; guaranteed repair of all ASAP7 design rules; generalized multi-PDK support beyond an extensible interface; replacement of DSH with LangGraph/AutoGen; rewriting the upstream KLayout deck without qualification.

## 1. Current implementation and specific defects

The following observations are based on inspected repository source, **not** on a successful local execution.

| ID | Priority | Source | Finding | Required disposition |
|---|---|---|---|---|
| F01 | P0 | `config.py`, `asap7_mini.drc`, `knowledge/asap7_rules_guide.md`, `generate_fix.md`, `run-flow.mjs`, `fixer.py` | Mini test calls 18/0 M1 and 19/0 V1. The public ASAP7 KLayout deck maps 18/0=V0, 19/0=M1, 21/0=V1, 20/0=M2. | Introduce authoritative ASAP7 profile; migrate tests while retaining a clearly labeled legacy fixture if useful. |
| F02 | P0 | `create_sample_layout.py`, KB, agent prompt | Synthetic GDS sets `layout.dbu=0.001` um while instructions claim 0.00025 um per DBU. | Read actual GDS DBU and obtain manufacturing grid from technology profile; unit tests for both representations. |
| F03 | P0 | `harness/profile/catalog/flows/run_drc.yaml`, `harness/scripts/run-flow.mjs` | Seven-node flow ends with `save_script`: no run-patch -> DRC -> validate cycle. | Add explicit execution/validation/orchestration steps with bounded retry. |
| F04 | P0 | `harness/scripts/run-flow.mjs` | On missing/failed model API call, a fixed geometric recipe silently substitutes for an LLM result. | Explicit mode and provenance (`agent`, `heuristic_baseline`, `error`); no silent success. |
| F05 | P0 | `fixer.py`, generated fallback | Layer-wide growth/closing/union can merge separate nets. No net awareness. | Make heuristic a separate baseline; reject unverified electrical repairs from `fully_validated` score. Avoid unconstrained global writes. |
| F06 | P0 | `runner.py` | Assumes runset CLI parameters `input` and `report`. OpenROAD ASAP7 `.lydrc` expects `in_gds` and `report_file`. Reports can be misrouted. | Deck-specific invocation adapter and report-file integrity checks. |
| F07 | P0 | `runner.py`, `parser.py` | Runner allows a `.target.gds` fallback while returning the missing `.lyrdb` path; parser cannot fulfill that contract consistently. | Require genuine, readable `.lyrdb` for benchmark jobs; make alternative format explicit and tested if later needed. |
| F08 | P1 | `drc_context.py` | Extractor searches one line containing rule name and assumes one threshold. Large ASAP7 deck is XML-wrapped, has expressions/multiple distances/derived layers. | Parse `.lydrc` embedded source and maintain a versioned, explicit rule catalog; don't misreport one scalar threshold. |
| F09 | P1 | `gds_context.py` | Reads only `top_cell.shapes(...)`; hierarchical standard-cell instances are missed. Uses regex on textual marker representations. | Use KLayout typed report geometries and recursive hierarchy-aware shape traversal/transforms. |
| F10 | P1 | `gds_context.py` | Default 3 windows per rule and 100nm halo may omit interacting violations and relevant shapes. | Adaptive clustering, caps with deterministic selection, per-cluster context provenance. |
| F11 | P1 | `parser.py` | Scans every report item for every category; item IDs are only per-category ordinal; no stable cross-run marker identity. | Single-pass indexed parse, explicit marker geometry and canonical comparison model. |
| F12 | P1 | `tests/test_drc_pipeline.py` | Assertions of 8 violations and 0 after deterministic fixer cover one legacy mini dataset, not model repairs or electrical safety. | Preserve legacy regression then add isolated rule, negative, round-trip, and sandbox failure tests. |
| F13 | P1 | `test_data/layouts/create_sample_layout.py` | A polygon labeled a valid enclosure example around x≈300nm has only ≈1nm lateral enclosure of its via. | Correct or rename this fixture; validation must derive labels from actual checks, not comments. |
| F14 | P1 | `run-flow.mjs`, `drc-operations.ts` | Standalone flow manually calls model HTTP endpoint, while catalog defines `kind:model`; result provenance may differ by execution path. | Make both run paths share contracts, or explicitly designate one canonical production path. |
| F15 | P2 | Entire project | No fixtures from real ASAP7 cells or post-route blocks; no reproducible benchmark manifest, metrics, run hashes or isolated output directories. | Implement expanding test suite after correctness gates. |

**Upstream deck caution:** the OpenROAD KLayout ASAP7 runset contains rules with multiple output statements for the same category and at least one suspicious `M1.S.2` line emitted with a blank category string. Audit actual category IDs/behavior before making metrics depend on them. Do **not** quietly 'fix' upstream semantics in benchmark copies; capture patch provenance or define a separately reviewed curated subset.

## 2. PDK and DRC policy decisions (must be agreed in code)

1. **Authoritative technology:** `flow/platforms/asap7` from a pinned OpenROAD Flow Scripts commit, recording SHA256 checksums of the `.lydrc`, technology layer mapping and included cell GDS. The ASAP7 design rule manual is the semantic reference; the public KLayout deck is a research verifier, not signoff.
2. **Physical ASAP7 layers:** confirm and configure **V0 18/0, M1 19/0, M2 20/0, V1 21/0** and additional layers from pinned technology file. Do not infer a layer merely from an old example.
3. **Coordinate representation:** store GDS geometry in native integer DBU with explicit `layout.dbu` (micrometers per DBU); convert user-facing values to nm/um only at defined boundaries. Record manufacturing-grid assumptions separately and verify integer-grid snapping.
4. **Two rule scopes:** `legacy_mini` for migration/compatibility testing only; `asap7_curated` for individually validated rule classes; `asap7_public_full` as a wider regression signal, with known limitations documented.
5. **Connectivity contract:** for small synthetic geometry with no netlist or connectivity annotation, outcome may be `geometry_only_pass`. For routed designs, source netlist/DEF/ODB or equivalent reliable reference is required for electrical acceptance. Never infer electrical correctness from DRC alone.
6. **Edit domain v1:** initially focus BEOL routing geometry and vias; treat standard-cell internals, FEOL and protected cells/instances as immutable unless an explicit test authorizes edits.
7. **Execution mode:** no generated Python script runs unsandboxed. Run in a disposable isolated environment with no secrets/network and constrained filesystem, time, memory and CPU; input/reference read-only; output temporary. Failed execution is a test failure, not a heuristic success.
8. **Unclean baselines:** OpenROAD final GDS may have pre-existing public-deck markers. Snapshot/check them rather than assuming all generated GDS is DRC-clean. Track **introduced, resolved, persisted** violations and classify known deck limitations/waivers explicitly.

## 3. Work packages in implementation order

### WP0 — Audit, pin, and establish repeatable baseline (P0; no production behavior change)

**Deliverables**
- `docs/asap7_drc_baseline.md` with exact tools, revisions, deck invocation, known issues and results.
- A versioned `assets/asap7/manifest.yaml` (or profile) with upstream URLs, commit hashes, file checksums, license provenance, layer information, deck variable names, runner mode, expected output format.
- A reproducible `make`/`uv` command to run existing tests; test categories tagged by `legacy` vs `asap7`.
- Inspection of `flow/platforms/asap7/drc/asap7.lydrc` output categories, threshold expressions, flags `OFFGRID/DEBUG`, and limitations.

**Actions**
1. Pin the **current** repository under test plus KLayout version; capture execution environment (`uv.lock`, Python, Node, DSH version).
2. Run and save existing pytest results without altering goldens; check actual sample `.gds` DBU/layers and category counts.
3. Verify upstream deck's parameter names `in_gds`/`report_file`; check actual `.lyrdb` loads in `klayout.rdb.ReportDatabase`.
4. Inventory rule IDs (not merely rule-name string search). Identify target BEOL rule families and duplicate/blank category labels.
5. Produce a baseline compatibility matrix: `legacy_mini`, `asap7_curated`, `asap7_public_full` × sample GDS, ASAP7 std-cell GDS, OpenROAD final GDS.

**Acceptance:** deterministic baseline command and machine-readable environment manifest; unknown/missing tools fail with explicit diagnostics; *no* claim of zero DRC unless check was actually run.

### WP1 — Repair technology/configuration and invocation contracts (P0)

**Files:** `src/klayout_drc/config.py`, `runner.py`, `cli.py`; new `technology.py`/`profiles/asap7.yaml`; existing KB and prompt; test fixture generator.

**Actions**
1. Replace hardcoded `LAYER_M1`, `LAYER_V1`, fixed DBU constants and assumed thresholds with a validated technology-profile interface (preserve old defaults only under `legacy_mini`).
2. Provide runset adapter mapping `legacy_mini` → `input/report` and `asap7_public_full` → `in_gds/report_file`; select top cell explicitly if needed. **Never** rewrite the upstream deck just to rename a variable.
3. Separate DBU from manufacturing grid. On read, verify cell/top selection, units, permitted layers and integer coordinate conversion. Do not silently rescale genuine ASAP7 GDS.
4. Mark/correct the old generator's invalid “valid” via example; version the seed. Keep a migration test proving original legacy semantics still work if retained.
5. Prevent false success on absent, stale, text-placeholder, corrupt or non-loadable `.lyrdb`. Alternative `.target.gds` output, if kept, must be its own typed output path with its own parser tests.

**Acceptance tests**
- Correct ASAP7 layer map is asserted in code and test.
- 0.001 um and 0.00025 um GDS DBU cases convert same physical 18nm distance consistently; avoid assuming the input layout's DBU always equals the tech grid.
- A deck parameter mismatch fails clearly instead of reporting zero violations.
- Missing/placeholder/corrupt `.lyrdb` fails before the model node.
- KLayout's actual `.lydrc` file generates a parseable report on a chosen fixture.

### WP2 — Normalize structured DRC/geometry/rule context (P1; prerequisite for larger decks)

**Files:** `parser.py`, `drc_context.py`, `gds_context.py`, `reporter.py`; new `rule_catalog.py`, optionally `geometry.py`.

**Actions**
1. Preserve native marker types (`edge`, `edge_pair`, `polygon`, `box`) and their numeric coordinates; do not recover them with an untyped regular expression on `to_s()`.
2. Normalize every marker to `{category, description, source_cell, hierarchy_path, geometry_type, bbox_um, geometry, provenance}`. Stable cross-run comparison should use canonical category + quantized geometry (with tolerance) and, where available, instance identity. Record when matching is ambiguous.
3. Walk transformed child instances recursively when extracting layout windows. Include GDS hierarchy path, layer name, geometry and coordinate transforms; impose deterministic caps, memory limits, pagination/sampling for large designs.
4. Parse XML `.lydrc` macro text (`<text>`) and HTML/XML entities correctly; build a rule catalog linking category names to full source spans, derived layers and all relevant constraints. Because general Ruby DSL static analysis is difficult, use a curated, reviewable catalog for semantic metadata and fall back to exact source snippets, not guessed scalar thresholds.
5. Ensure list of violated categories from checker is accurately mapped even when an upstream category is blank, reused, or truncated. Report `unresolved_rule_mapping` explicitly.
6. Cluster spatially related markers and attach a context completeness flag; add format suitable for agent inputs without enormous text dumps.

**Acceptance tests**
- RDB fixtures with edge pairs, polygons, text and empty categories parse without incorrect coordinates.
- Multi-instance hierarchical synthetic GDS returns correctly transformed polygons in the reported local window.
- Varying DBU yields numerically identical physical marker extents.
- Multiple constraints for one ASAP7 category are represented without losing information.
- Full deck's `M1.W.1`, multiple M1 spacing categories, `M1.A.1` and via-related categories can be traced to known source spans or flagged as unresolved.

### WP3 — Safe candidate execution and independent validation (P0)

**Files:** new `repair_executor.py`, `validator.py`, `layout_diff.py`, `run_artifacts.py`; modify `cli.py` and DSH operations.

**Actions**
1. Accept candidate code only as a staged artifact; validate script syntax/entry point and instantiate a unique read-only input + writable output workspace. Run in OS/container sandbox; do not rely on Python import allowlists for security.
2. Execute `fix_layout(input_gds, output_gds)` with bounded resources and capture exit status, logs, runtime, script hash and output hash.
3. Validate output as a readable GDS, expected top cell/units/layers, no unexplained cell removals/additions, and edit region restrictions. Use GDS shape diff and hierarchy-aware metrics.
4. Rerun the exact same pinned DRC deck on input and output; compare category count **and** spatial markers, classifying `resolved`, `persisted`, `introduced`, `shifted/ambiguous`. Do not accept lower aggregate count if new severe violations appear.
5. Implement a separate connectivity gate. In v1, synthetic fixtures may use explicit net tags or graph constraints; routed cases should consume DEF/ODB/netlist connectivity. If no trustworthy check exists, status is `unverified_connectivity` and cannot count as `fully_validated`.
6. Validate untouched, deliberately untouched, and intentionally unsolvable cases. Preserve full audit trail.

**Acceptance tests**
- A script that deletes all shapes never scores a successful repair.
- A script that merges two differently tagged nets fails connectivity.
- A script with syntax error, infinite loop, wrong output path, or no produced GDS fails explicitly and reproducibly.
- An unchanged GDS passes integrity checks but **does not** claim repair success when original violations remain.
- Real exception and zero-marker states remain distinguishable.

### WP4 — Closed-loop DSH agent execution (P0)

**Files:** `harness/profile/catalog/flows/run_drc.yaml`, `generate_fix.md`, `harness/src/drc-operations.ts`, `harness/src/types.ts`, `harness/scripts/run-flow.mjs`.

**Actions**
1. Extend flow beyond script saving: `execute_patch` → `validate_gds` → decision. Use bounded iteration (default 3 attempts as a **configurable starting point**, not an asserted optimum).
2. On failure, supply targeted feedback: surviving/new markers, violated constraints, edit-scope violations, connectivity failure, script stderr. Keep original inputs immutable and track each candidate separately.
3. Introduce explicit modes: `agent`, `heuristic_baseline`, `analyze_only`. A failed model call must remain a failed agent run, never be auto-scored as successful heuristic repair.
4. Make the model-input contract use `technology_profile`, `rule_context`, `violation_clusters`, `local_geometry`, `protected_shapes`, `connectivity_context`, `allowed_operations` and `feedback` rather than a single unbounded text dump.
5. Preserve DSH model-node flow as intended. If `run-flow.mjs` retains its manual API call, clearly identify it as a different runner and make it consume the same validated stages/results; otherwise choose one canonical flow. Do not modify the core DSH repository.
6. Add final typed statuses: `success_full`, `success_geometry_only`, `partial`, `invalid_patch`, `model_error`, `drc_error`, `timeout`, `no_change`, `unsupported`.

**Acceptance tests**
- One generated repair runs through full before/after DRC with validated file outputs and recorded provenance.
- All model errors and fallbacks are reflected in reported status.
- Attempt count, limits, and tool/model costs are traceable.
- A failed attempt never overwrites the previous/original GDS.
- Repeated patches that do not improve the violation set terminate correctly.

### WP5 — Expand ASAP7 rule coverage using curated checker tests (P1)

**Rule inventory first; implementation second.** Build an inventory from the pinned public deck and record coverage status: `supported`, `unsupported`, `known_problem`, `not_applicable`, `under_review`.

**Proposed initial order** (verify precise rule semantics against pinned deck; not every item is independent):
1. M1 minimum width (`M1.W.1`), M2 minimum width (`M2.W.1`), M1 minimum area (`M1.A.1`).
2. M1 spacing family (`M1.S.1` etc.): length-conditioned parallel edges, end of line, corner conditions; do **not** implement as one generic 18 nm spacing test.
3. M2 spacing and area rules.
4. Via rules associated with V0/M1 and V1/M1/M2, including enclosure and alignment, once valid surrounding geometry exists.
5. M3 and higher BEOL rules, then more complex categories, keeping FEOL edit operations out of scope initially.

**Actions**
- Produce for each selected rule a *legal* geometry test, a barely *illegal* geometry test (one manufacturing-grid increment across boundary), a clearly illegal test, and an interaction test where possible.
- For a full-deck fixture, valid supporting layers and neighboring shapes must be present; else use a **clearly labeled scoped deck** for rule semantics. Never call a bare two-box layout full-ASAP7 DRC clean.
- Audit category IDs from KLayout output against rule catalog; capture intentional duplicate category semantics and upstream anomalies.
- Snapshot expected DRC markers by rule/geometry with tolerance; prefer semantic assertions to brittle total-count goldens.

**Acceptance:** at least 5 independently verified ASAP7 rule categories, all with positive/negative boundary tests and self-checking datasets, before broad generation.

### WP6 — Controlled GDS mutation generator and benchmark manifest (P1)

**Files:** new `benchmark/generate.py`, `benchmark/mutations.py`, `benchmark/manifest.py`, `benchmark/evaluate.py`, `tests/test_benchmark_generation.py`; separate immutable fixtures.

**Core algorithm**
1. Select legal canonical seed / verified baseline layout and technology profile.
2. Pick rule, target polygon/edge, mutation family, integer-grid delta and RNG seed.
3. Clone the target cell or instance context so changes remain local; preserve parent hierarchy and original reference.
4. Apply one mutation: shrink width, move track, reduce spacing, shorten line, shift via, reduce enclosure, trim area. Use `klayout.db` integer-DBU operations and snap to verified legal grid.
5. Run DRC; accept case only when it produces the intended violation and meets its declared maximum for unintended additional markers. Store observed categories and actual marker geometries.
6. Save `reference.gds`, `mutated.gds`, a manifest, baseline/mutated `.lyrdb`, checksums and expected invariants.
7. Split by underlying design/seed/cell family, not randomly among almost identical mutations.

**Benchmark modes**
- `isolated`: a single intended violation, no confounding markers in scoped rules.
- `interaction`: deliberate overlapping or coupled rule failures; manifest lists **all** expected affected categories.
- `negative`: no violation or illegal-to-modify region; agent must abstain/no-op.
- `hierarchy`: violation occurs in a repeated or transformed instance.
- `baseline_dirty`: pre-existing unrelated markers explicitly tracked.

**Suggested target:** bootstrap approximately **100 validated cases** across at least 5 rule categories and multiple randomized geometries. Increase only after the generator demonstrates reproducible checks.

### WP7 — Real ASAP7 designs from OpenROAD Flow Scripts (P2)

**Primary source:** `https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts` with `flow/platforms/asap7/config.mk` and its KLayout deck.

**Actions**
1. Bring up small ASAP7 RTL-to-GDS designs, starting with `gcd`; record exact `DESIGN_CONFIG`, constraints, seed, tool versions and output manifest.
2. Preserve final GDS, DEF, final netlist and routing database/ODB as available to support net-aware validation.
3. Execute `make DESIGN_CONFIG=./designs/asap7/gcd/config.mk` and `make DESIGN_CONFIG=./designs/asap7/gcd/config.mk drc` after environment setup. Do not hardcode expected violation totals.
4. Classify existing public-deck violations; determine which are actionable routing defects versus deck/library caveats. For benchmark creation, mutate routing shapes in an allowed region while holding standard-cell masters immutable.
5. Increase difficulty through distinct RTL blocks, feasible placement densities, route congestion, layers and seeds; do not rely on changing seed alone as a proxy for independent data.
6. For first routed repairs, allow changes only to known route net shapes, with DEF/netlist-based checks. If a robust map from GDS polygons to nets cannot be constructed, benchmark detection/geometry-only separately and defer electrically validated repairs.

**Acceptance:** at least one complete ASAP7 RTL-to-GDS build is reproducible, produces a genuine parsed `.lyrdb`, and supplies enough net ownership/reference context to state precisely which repair validation gates can be applied.

### WP8 — Scoring, CI and reporting (P1/P2)

**Metrics**
- Per-case outcome and validator scope (`full`, `geometry_only`, `unsupported`).
- Per-rule pass/repair rates; introduced/resolved/persisted markers (with matching ambiguity recorded).
- Connectivity gate and edit-scope gate; patch area, touched layers/cells, wirelength/via deltas when available.
- Wall-clock time, peak memory, LLM tokens/cost, iterations, model identity and script provenance.
- Run-to-run variance over fixed cases and multiple LLM seeds (avoid data contamination).

**Reporting**
- `run_manifest.json` with input/deck/profile hash, exact commands, tool/model versions, environment and seed.
- `summary.json`/CSV and readable Markdown/HTML summary. All run artifacts stored under unique `reports/runs/<run_id>/` rather than global `reports/fix_layout.py`.
- Tests partitioned into `unit` (fast and hermetic), `integration_klayout`, `integration_dsh`, `e2e_openroad` (optional/heavy). CI cannot mask missing tool dependencies as benchmark success. Smoke tests use pinned fixtures; heavier suites are opt-in.

**Acceptance:** one command reproduces deterministic benchmark generation and one command evaluates the same fixed case list; dashboard accurately distinguishes repaired, partially repaired, invalid, unverified and no-op results.

## 4. Recommended PR sequence and merge gates

| PR | Work items | Merge gate |
|---|---|---|
| PR-00 | WP0 | Reproduction document, pinned manifest, baseline findings. No behavioral changes. |
| PR-01 | WP1 | Corrected layer/DBU/runner contracts; legacy suite isolated; new ASAP7 smoke test. |
| PR-02 | WP2 | Typed marker geometry, hierarchical windows, XML rule extraction/catalog and tests. |
| PR-03 | WP3 | Sandbox execution, GDS integrity, pre/post DRC delta, negative safety tests. |
| PR-04 | WP4 | DSH closed-loop flow with explicit statuses and no silent fallback. |
| PR-05 | WP5 | Audited BEOL rule subset and positive/negative boundary cases. |
| PR-06 | WP6 | Reproducible case generator, manifest and first 100 validated cases. |
| PR-07 | WP7 | OpenROAD ASAP7 routed-design fixtures and net-aware validation integration. |
| PR-08 | WP8 | Aggregate metrics, reproducibility and CI integration. |

PR-03 and PR-04 should not be declared fully complete without at least one end-to-end agent run. Parallelize only independent investigation and fixture work. Preserve main as runnable after each PR.

## 5. API/artifact contracts for Codex to propose before coding

### Technology profile (illustrative; verify complete map)

```yaml
id: asap7_openroad
upstream: The-OpenROAD-Project/OpenROAD-flow-scripts
commit: <PINNED_COMMIT>
rule_deck: <PINNED_PATH_TO_asap7.lydrc>
rule_deck_sha256: <CALCULATED>
runner:
  engine: klayout
  input_arg: in_gds
  report_arg: report_file
  format: lyrdb
layers:
  V0: [18, 0]
  M1: [19, 0]
  M2: [20, 0]
  V1: [21, 0]
units:
  geometry_dbu: read_from_gds
  manufacturing_grid: verify_from_technology
editing:
  policy: beol_only
  protected_cells: standard_cell_masters
validation:
  require_drc_recheck: true
  require_connectivity_for_full_success: true
```

### Benchmark case manifest (illustrative)

```yaml
case_id: asap7_m1w_boundary_seed0042
technology: asap7_openroad
suite: isolated
seed: 42
baseline_gds: reference.gds
mutated_gds: mutated.gds
rule_id: M1.W.1
mutation:
  op: reduce_width
  layer: M1
  amount_nm: 0.25
expected:
  target_rule_present: true
  protected_cell_changes: 0
  reference_connectivity_preserved: true
validation_level: geometry_only  # promote only if connectivity independently checked
```

### Run-result JSON (illustrative)

```json
{
  "case_id": "asap7_m1w_boundary_seed0042",
  "run_id": "<unique-run-id>",
  "mode": "agent",
  "model": "<actual-model>",
  "status": "success_geometry_only",
  "attempts": 2,
  "drc": {"before": 1, "after": 0, "introduced": 0, "resolved": 1},
  "integrity": {"gds_readable": true, "edit_scope_valid": true},
  "connectivity": {"status": "unverified"},
  "artifacts": {"input": "...", "output": "...", "before_lyrdb": "...", "after_lyrdb": "..."}
}
```

Use stable enum definitions in Python and TypeScript rather than silently inventing additional statuses in each runner.

## 6. Suggested test matrix and first experimental gates

| Stage | Test family | Check |
|---|---|---|
| Preflight | Invalid path, missing KLayout, deck argument mismatch, malformed report | Fail visibly; never emit false `zero violations` |
| Technology | Layer map and DBU pairs (1nm, 0.25nm input DBU), wrong layers | Correct physical semantics and explicit unsupported states |
| Checker | Minimum width/area, edge-conditioned spacing, via enclosure | Legal / boundary / illegal cases; category and marker identity |
| Context | Hierarchical/transformed instances, edge pairs, cap truncation | Coordinates and affected layers correct; completeness flagged |
| Agent | Valid patch, syntax error, no-op, bad output, timeout | Every stage and status recorded |
| Safety | Delete-all geometry, global growth/short, standard-cell mutation | Reject invalid repair even if markers vanish |
| Generalization | New random seed and unseen layout shape | No memorized fixture assumptions |
| OpenROAD | GCD (first), other blocks later | Exact pinned GDS/DEF/ODB/report provenance; baseline-aware scoring |

**Research metrics should initially be observational**—do not set arbitrary model-success thresholds as code gates. Infrastructure gates require correct classification, truthful reporting and reproducibility; benchmark scores can improve over time.

## 7. Codex execution instructions

1. Treat this document as an **implementation plan**, not as proof that its examples currently execute.
2. Start by inspecting the current branch and upstream ASAP7 PDK files; state any changed file paths or conflicting evidence.
3. Perform **WP0 first** and produce an issue-by-issue implementation diff proposal with tests. Then implement successive PR-sized groups, running focused tests before the next group.
4. Do not mix corrective migration of legacy mini fixtures with replacement of the public ASAP7 deck. Label rule scope in every output.
5. Avoid unnecessary third-party dependencies and major architectural rewrites. Reuse `uv`, pytest, `klayout.db`, DSH and current CLI wherever possible.
6. Add tests alongside changes. Preserve original layouts and pin every external data dependency; avoid brittle goldens based only on aggregate marker counts.
7. Provide a concise report at each checkpoint: files modified, commands/tests run, results, remaining unsupported cases and any changed assumptions.
8. Do not count any test as passed when required KLayout/DSH/OpenROAD dependencies were unavailable; label it skipped/blocked.
9. For ambiguous rules, checker errors, or missing net context, **fail closed and report uncertainty**. Do not claim repair correctness.
10. Do not add GT2N/GT3/FreePDK3 support until the ASAP7 stage has reproducible closed-loop evaluation.

## 8. Upstream technical references

- Project repository: https://github.com/ankdesh/build-with-terminator/tree/main/eda/gdsii/klayout-4-drc
- Official ASAP7 predictive PDK collateral: https://github.com/The-OpenROAD-Project/asap7
- OpenROAD Flow Scripts ASAP7 configuration: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/platforms/asap7/config.mk
- OpenROAD Flow Scripts ASAP7 KLayout deck: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/platforms/asap7/drc/asap7.lydrc
- Community ASAP7 KLayout runset: https://github.com/laurentc2/ASAP7_for_KLayout/blob/main/drc/drc_ASAP7.lydrc
- OpenROAD Flow Scripts DRC targets: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/Makefile
- KLayout DRC basics: https://www.klayout.org/downloads/master/doc-qt5/manual/drc_basic.html
- KLayout DRC layer API: https://www.klayout.org/downloads/master/doc-qt5/about/drc_ref_layer.html
- KLayout RDB API: https://www.klayout.org/downloads/master/doc-qt5/code/class_ReportDatabase.html
- Historical discussion documenting ASAP7 GCD public-deck violations (not a current baseline): https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/discussions/854

## 9. Definition of done for the initial ASAP7 milestone

The initial milestone is complete when: (1) actual ASAP7 mapping/units/deck work end-to-end, (2) the model's output is executed and independently rechecked, (3) unsupported or electrically unverified repairs cannot be scored as fully valid, (4) at least five distinct verified BEOL rule categories have legal/illegal boundary fixtures, (5) a deterministic seeded generator produces about 100 self-validating cases, and (6) per-case and aggregate reports preserve all inputs, checker and model provenance. Full OpenROAD scale-up is the following milestone unless the team chooses to bring it forward.
