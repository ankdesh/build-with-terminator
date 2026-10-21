# Phase C — Expand GDS Coverage and Benchmark Difficulty

**Depends on:** Foundation 0 + A + B  
**Goal:** Test the **same single-shot** Fix → Apply Patch → Report pipeline on increasingly diverse real-ASAP7 geometry.  
**No new closed loop:** One patch per test case; repeat experiments as distinct runs, never automatic agent self-correction.

## Approach

Increase difficulty on three distinct axes: **rules**, **layout complexity**, and **electrical/contextual realism**. Do not generate a large random corpus before proving checker-ground-truth quality. Maintain separate benchmarks for (1) generated synthetic geometry, (2) actual standard-cell-derived layouts, and (3) routed OpenROAD designs.

## C1 — Deterministic, rule-driven geometry generation (first)

### C1.1 Define benchmark case data

For each case store `case_id`, source/seed identity, ASAP7 profile and deck hash, selected rule IDs, legal baseline, controlled mutation, expected vs **observed** markers, source connectivity constraints if any, protected regions, difficulty tier and checker reproducibility evidence.

**Recommended file layout:**

```text
benchmark/
  generate.py
  mutations.py
  manifest.py
  evaluate.py
  rule_catalog.py                # or reuse src/klayout_drc/rule_catalog.py
  cases/                       # generated or indexed artifacts (avoid huge git binaries)
tests/
  test_benchmark_generation.py
  test_mutation_reproducibility.py
  test_benchmark_scoring.py
```

### C1.2 Target mutations

Operate on KLayout integer DBU and snap to the verified physical manufacturing grid:

| Mutation | Intended rule signal | Negative/control variant |
|---|---|---|
| Narrow metal/neckdown | Min width | Exact legal width |
| Move one wire nearer another | Length-dependent spacing | Just legal gap |
| Shorten or trim a polygon | Min length/area | Legal area boundary |
| Move via relative to metal | Enclosure / overlap | Legal via alignment |
| Move/rotate shapes | Corner/end-of-line | Legal orientation and spacing |
| Intentionally overlap rule constraints | Multiple correlated DRC categories | One constraint changed back |
| Edit a master vs one cloned instance | Hierarchy/cell reuse | Protected master remains unchanged |
| Mutate a “baseline dirty” design | Known original violations retained | No newly created target marker |

For every generated case:

1. Start from an **immutable** legal seed for a **stated checker scope**. When no full-deck-clean seed exists, explicitly label `baseline_dirty` and record existing markers.
2. Clone the intended cell/instance, preserve hierarchy and net tags when known.
3. Apply one deterministic mutation selected by seed; record actual geometric delta.
4. Run actual pinned KLayout DRC and assert that the intended category appears, and additional categories comply with the case's declared allowance.
5. Reject and log any generation case that cannot prove expected checker behavior; **do not** force expected labels by hand.
6. Store baseline and mutated `.lyrdb`, hashes, rule/scoping metadata, and reference GDS.
7. Separate dataset generation from agent evaluation: do **not** disclose the original clean GDS or exact mutation parameters to the agent.

**Target after generator validation:** ~100 reproducible cases across at least five verified rule categories; preserve varying difficulty rather than overfitting to 100 nearly identical cases.

### C1.3 Suggested case types

- `isolated`: only intended DRC signal under the selected scoped deck.
- `interaction`: designed multiple violations with jointly constrained repairs.
- `negative`: already legal case where no repair should be made, or immutable object that must be rejected.
- `hierarchy`: repeated, rotated or transformed cell instance.
- `baseline_dirty`: real starting GDS with pre-existing unrelated markers, against which differential scoring is used.

**Acceptance C1:** Running generation twice with same seed, tools and pinned inputs reproduces equivalent geometry, observed DRC markers, and case metadata; 100-case experimental target reached only after self-validation.

## C2 — Real ASAP7 standard-cell and hierarchical GDS

- Import PDK standard-cell GDS/LEF under pinned upstream provenance. Use these as **real geometry context**, not necessarily as repair-edit targets.
- Test crop/window extraction across instance transformations and repeated master instances. Confirm marker coordinates in top-level reference frame.
- Protect standard-cell internals in the default edit policy. Inject mutations into **separate route/test cells** or instance-specific editable copies where the benchmark explicitly permits them.
- Choose varied standard-cell families/placement configurations to create realistic obstacles. Check collision between proposed repairs and immovable cell geometry.
- If a single source master is deliberately modified, require a special test specifying whether edits to all instances are acceptable; otherwise clone the relevant master before editing.

**Acceptance C2:** At least one hierarchical repeated-cell benchmark returns correct transformed geometry, and a patch touching a protected master is rejected.

## C3 — Generate routed ASAP7 blocks with OpenROAD Flow Scripts

**Primary source:** https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts

1. Pin ORFS commit and toolchain. Start with `flow/designs/asap7/gcd/config.mk` and verify configuration file in current upstream checkout.
2. Generate a genuine placement/routing/final merged GDS. Retain accompanying final DEF, netlist, SDC, routing database (ODB) and logs where produced.
3. Run pinned public ASAP7 KLayout deck. **Do not assume** final GDS is free of public-deck violations. Record baseline and categorize known deck/library/flow caveats.
4. Extract edited **routing** shapes together with reliable net ownership from DEF/ODB. Do not infer a wire's net from GDS layer number or proximity.
5. Mutate only permitted route nets and enforce immutable standard-cell interiors, power rails and protected instances by default.
6. Run the same Foundation pipeline. When complete connectivity or equivalent logical/topological validation is unavailable, score as `geometry_only` and report the missing gate.
7. Vary designs and feasible density/timing/routing settings, not merely RNG seed. Include congestion-induced coupled violations only after net-aware validation works.

**Illustrative commands, contingent on installed ORFS and upstream path verification:**

```bash
cd OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/asap7/gcd/config.mk
make DESIGN_CONFIG=./designs/asap7/gcd/config.mk drc
```

Do not hardcode total marker counts. The public deck is research-level, not foundry signoff.

### Why C3 needs a stronger connectivity oracle

DRC-clean geometry can have **new opens or shorts**. To claim electrical validity on routed cases, compare intended net connectivity from a trusted DEF/ODB/netlist reference with post-edit geometry (or run a verified LVS/network extraction pipeline). If that facility cannot be built reliably in C3's first iteration, keep candidate-generation and geometry-only reporting, **do not** promote it to fully validated repair.

## C4 — Benchmark scale, metrics, and CI

### Suggested increasing benchmark sizes (targets, not achieved results)

| Level | Example | Target case count | Minimum invariant |
|---|---|---:|---|
| C1-small | Isolated legal/boundary/illegal shapes | 30 | Correct DRC target and edit diff |
| C1-mixed | Multiple rule interactions and negatives | 70 additional | Expected category set, source integrity |
| C2-hierarchy | PDK cells with transformed contexts | Expand as valid fixtures accrue | Master protection and geometry context |
| C3-route | GCD and additional routed blocks | Initially a few reproducible designs | Baseline-dirty accounting and net-owner provenance |

### Score and report

- Per-case status: valid full, geometry-only, partial, rejected, unsupported, blocked.
- Before/after by rule; *introduced/resolved/persisted/ambiguous* with robust marker matching and recorded caveats.
- Connectivity and immutable-region outcomes.
- Modified area, layer/cell counts, wirelength/via overhead when available.
- Elapsed time, subprocess memory, tokens/cost, model ID and prompt/deck/code hashes.
- Multiple independent seeds, variation by source design and family, and confidence intervals when reporting empirical rates.
- `summary.json`, `summary.csv`, readable Markdown/HTML summary; each run retains detailed artifacts in `reports/runs/<run_id>/`.

Partition CI into fast `unit`, `integration_klayout`, `integration_dsh`, and optional heavy `e2e_openroad` suites. Missing heavy-tool dependencies mean `blocked/skipped`, never benchmark passes.

## C5 — Ground-truth integrity and leakage controls

- Split cases by underlying design, cell family, and seed group so nearly identical mutations do not appear in both development and held-out test sets.
- Prevent agents from seeing the original reference geometry, expected rule label generated by the injector beyond checker-observable information, or mutation recipe.
- Keep candidate scoring independent from patch-generation prompts.
- Store exact provenance and license/redistribution restrictions for third-party GDS/PDK collateral; do not commit bulky upstream binaries unnecessarily.

## Exit gates

**C1:** ~100 checked deterministic cases from >=5 verified rule categories, generation seed reproducibility, case manifest, legal/illegal validation.  
**C2:** Hierarchical windows and protected-master cases working with real ASAP7 standard-cell layout.  
**C3:** At least one ORFS ASAP7 RTL-to-GDS build and public DRC run reproduced, with actual net-context availability and claimed validation scope documented.  
**C4:** Aggregate report partitions success from invalid/unverified/blocked; no aggregate DRC reduction is mislabeled electrical repair success.

## Codex work packaging

- **C-PR1:** Generator/manifest/test infrastructure and self-checks (original WP6).
- **C-PR2:** Hierarchical standard-cell fixtures, protections and geometry tests (original WP2/WP6).
- **C-PR3:** ORFS ASAP7 integration and baseline artifacts/net-aware context (original WP7).
- **C-PR4:** CI/per-rule scoring/aggregate reporting (original WP8).

No multistep agent planning/revision is needed to finish C. Consult original findings F09–F15 and original WP5–WP8 for detailed requirements.
