# Phase B — Prove the Pipeline with Real Public ASAP7 DRC

**Depends on:** Foundation 0 and Phase A  
**Goal:** Replace synthetic rule/technology assumptions for this stage with a pinned public ASAP7 stack and verify a diverse BEOL rule subset.  
**Excluded:** Large-scale GDS generation (Phase C) and automatic retries (Goal D).

## Precise success claim

A model-authored **single** repair patch is applied and independently rechecked using a **real public ASAP7 KLayout deck or an explicitly audited subset** against correctly mapped ASAP7 GDS. Report what rule scope was checked. Do not call an arbitrary two-box GDS `full-ASAP7-clean`, and do not call public-deck checks manufacturing signoff.

## B0 — Pin and audit an ASAP7 verification stack

- Use OpenROAD Flow Scripts' `flow/platforms/asap7` at a pinned commit. Record exact upstream URL/SHA, deck SHA256, library GDS, LEF and technology-file provenance/licensing.
- Treat the ASAP7 design-rule manual as technology reference and the public KLayout deck as the executable research checker.
- Inspect and record `OFFGRID`, `DEBUG`, other switches, input variable names, output category quality, behavior on real standard-cell GDS and version of KLayout.
- Explicitly audit the suspicious `M1.S.2` blank output category and reused categories in the public `.lydrc`. Never silently change the upstream deck for scoring; if a local patch is necessary, version it as a separately reviewed verifier.

**References:**
- PDK: https://github.com/The-OpenROAD-Project/asap7
- OpenROAD deck: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/flow/platforms/asap7/drc/asap7.lydrc
- Community KLayout deck: https://github.com/laurentc2/ASAP7_for_KLayout/blob/main/drc/drc_ASAP7.lydrc

## B1 — Introduce an authentic ASAP7 profile without breaking Phase A

The pinned public KLayout ASAP7 deck maps the following physical layers:

| Physical layer | GDS layer/datatype |
|---|---|
| V0 | 18/0 |
| M1 | 19/0 |
| M2 | 20/0 |
| V1 | 21/0 |

All other layers must be sourced from the pinned deck/technology files. Do not infer from the legacy mini test. Input geometry uses actual `layout.dbu`; manufacturing grid is a separate technology constraint and must be verified. A `0.001 µm` layout DBU and `0.00025 µm` layout DBU should represent equivalent physical dimensions after correct conversion when representable on both grids.

Define three explicit profiles/scopes:

```yaml
legacy_mini:         # Synthetic and unchanged; intended for A regressions
  deck_params: {input: input_gds, report: output_lyrdb}
asap7_curated:       # Only independently tested selected categories
  base_pdk: pinned_asap7
  checker_coverage: explicit_rule_list
asap7_public_full:   # Entire pinned public KLayout deck, not foundry signoff
  deck_params: {in_gds: input_gds, report_file: output_lyrdb}
```

Implement as actual typed configuration, not as loosely coupled hardcoded constants. Never change Phase A `legacy_mini` data silently.

## B2 — Correct checker invocation and output validation

- `runner.py` must receive deck-specific argument names. Published OpenROAD deck uses `in_gds` and `report_file`; mini deck expects `input` and `report`.
- Require a newly produced, parseable `.lyrdb`, not merely a successful process exit code. Reject missing, stale, empty-placeholder, corrupt, or unsupported outputs.
- If the full deck triggers errors, preserve stderr, KLayout version, flags and environment in report. Do not treat errors as zero markers.
- Test a known small, correctly layered GDS with actual KLayout. The selected top cell and output path must be deterministic.

**Illustrative invocation:**

```bash
klayout -b -r <pinned>/flow/platforms/asap7/drc/asap7.lydrc \
  -rd in_gds=<verified_ASAP7_GDS_path> \
  -rd report_file=<unique_run_dir>/before.lyrdb
```

## B3 — Make DRC and geometric context suitable for full decks

Original `drc_context.py` currently looks for a rule name on one source line and extracts one scalar threshold. That is insufficient for KLayout `.lydrc` files (XML macro wrapper, escaped entities, Ruby DSL, multi-expression checks, derived layers).

Implement:

1. Parse actual macro `<text>` with correct XML entity decoding, preserving line/location provenance.
2. Maintain an audited **rule catalog** (`category`, `source_span`, `derived_layers`, `geometry_semantics`, `constraints[]`, `ambiguity_status`). No invented scalar threshold when several constraints exist.
3. Parse ReportDatabase marker geometries as **typed numeric geometry** (`edge`, `edge_pair`, `polygon`, `box`, text as text) instead of regexing rendered strings.
4. Handle empty/reused category IDs explicitly; report `unresolved_rule_mapping` with source fragments as needed.
5. Traverse GDS instances with their transforms, including repeated cells, rather than examining only direct top-cell shapes.
6. Make context limits/configuration deterministic and record truncation/completeness flags.
7. Preserve DBU/top/hierarchy provenance in normalized marker coordinates and comparisons.

Likely files: `parser.py`, `drc_context.py`, `gds_context.py`, `reporter.py`, new `rule_catalog.py` and typed geometry helpers. Include parser and hierarchy regression fixtures.

## B4 — Validate actual rule classes and generate *small* real ASAP7 cases

**Rule inventory first.** Inventory public deck categories with `supported`, `unsupported`, `under_review`, `known_problem`, `not_applicable` statuses and exact source links. Then prioritize:

| Order | Rule family | Notes |
|---|---|---|
| 1 | `M1.W.1` and `M2.W.1` | Width and legal-boundary cases |
| 2 | `M1.A.1` / M2 area | Area restrictions |
| 3 | M1/M2 spacing families | Edge-length, end-of-line and corner conditions; **not** one generic 18 nm rule |
| 4 | V0/M1 and V1/M1/M2 enclosure/alignment | Requires legal surroundings, interacting layers |
| 5 | Other BEOL checks (including M3+) | Expand only after initial categories are trustworthy |

For **at least five independently verified categories**, create a legal case, a legal boundary case, an illegal one-grid-step case, and a clearly illegal case; include an interaction example where practical. KLayout's actual output must confirm predictions. If the complete deck requires active/gate/fin context absent from a tiny hand-built pattern, use a clearly labeled curated fixture/checker for that rule and separately test the public deck on real PDK geometry.

Be explicit when a public-deck anomaly makes a category impossible to identify reliably; do not train/score the agent against bad ground truth.

## B5 — Prove single-shot agent repair under the new rule scope

Use the Foundation workflow without any automatic iteration:

1. Baseline DRC under an explicitly chosen public ASAP7 scope.
2. Generate **one** patch from DSH, saving exact model/rationale and source snapshot.
3. Apply it once in a sandbox to a new GDS output.
4. Verify edits are limited to declared BEOL geometry; standard-cell masters are protected unless the particular test expressly allows otherwise.
5. Rerun same pinned checker and compute before/after results. Include typed resolved/persisted/introduced/ambiguous markers when marker matching is reliable.
6. Report `geometry_only` unless independent circuit/connectivity evidence is present.

An agent that alters FEOL transistor geometry, erases layout contents, or joins separate nets must not be accepted because the DRC count decreases.

## Required acceptance tests

- Real ASAP7 layer mapping and physically equivalent coordinate conversion are verified; legacy Phase A still passes under its own profile.
- Public KLayout deck launches with correct arguments and produces a **real parseable RDB**, not a placeholder.
- XML-wrapped source, multi-rule expressions, repeated/blank category cases, edge-pair markers, hierarchical transformed shapes are handled or explicitly marked unsupported.
- Five selected rule categories pass legal/illegal boundary tests and source-to-marker traceability checks.
- One actual model-generated repair is executed and checked under the published deck **or** a clearly labeled selected rule scope; its failure is also a valid experimental result if faithfully reported.
- No false `full_validated` claim is made when net ownership is absent.

## Exit gate B

Codex can reproduce a correctly mapped ASAP7 DRC-before/after agent run, and the checker, rule catalog, geometry context, and report state exactly what was evaluated. Results are not derived from Phase A's artificial layer map.

## Deferred

- Bulk randomized case generation and design growth: C.
- Repeated self-revision using reports: D.

## Codex handoff

Treat this as technology migration **without deleting Phase A**. First prepare an upstream artifact/format audit and data-model proposal; only then update runner, parser, context, catalog and tests. Primary original work packages: WP1, WP2, WP5. Findings: F01, F02, F06–F10, and the deck category caution.
