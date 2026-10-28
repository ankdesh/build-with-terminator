# C2+C3 five-level benchmark

This benchmark uses real ASAP7 cells and complete routed GCD/UART blocks. It
keeps case generation separate from candidate generation and scoring. C1 files
and checker profiles remain separate.

## Corpus and acceptance

The release target is 50 accepted files across five levels. Each level has two
source groups. Each group supplies three repair cases, one clean control, and
one read-only challenge. Read `test_data/benchmark_c2c3/manifest.json` for actual
coverage. Its `complete` field stays false when a source, level, or case fails
qualification. Missing cases are not model failures.

L1 uses 10/15 real standard-cell instances. L2 uses 101/146 instances, repeated
masters, four hierarchy levels, rotations, reflections, and arrays. L3 uses two
GCD configurations at 65% and 50% core utilization. L4 uses UART configurations
with 8-bit and 12-bit data widths. These source differences remain in the stress
builds; nominal placement density alone did not create distinct GCD geometry. L5 uses the highest
measured local-occupancy build from three stress configurations per UART source.
Each L5 repair must have two checker-observed categories and local M2/M3 metal
occupancy at least 25% above its matching L4 window.

Cases are admitted only after checker and reference-repair validation. Generation
uses integer DBU and the 1 nm manufacturing grid stated by the pinned technology LEF. Failed candidates remain in the rejection log. Their geometry
is not published as an accepted case. Native baseline markers are recorded and
can persist. A clean control has no target defect in its declared scope; the
whole source can still have native violations.

## Pinned source and tools

- ORFS: `64939f3717ad7c694199ba04cb98924b98022868`.
- Container: `openroad/orfs@sha256:6810dbf0e03dddbc89ed8c0a1e13cad09ce4c98d40c4ac0ab99fdc04b0676347`.
- Scored profile: `asap7_c2c3_v1`, with its own deck hash and provenance record.
- Public audit deck: the existing pinned `asap7.lydrc`; it is not rewritten.

The container's OpenROAD version string is `unknown`. The toolchain receipt
therefore also records the binary SHA-256 and image digest. Do not claim that
the prebuilt binary was compiled from the ORFS OpenROAD submodule revision.
The receipt records the source submodule pins separately.

Builds run serially, with two threads, no container network, a 60-minute timeout,
and an 8 GiB memory cap. The actual memory limit is reduced to leave 1 GiB for
the host. A build is blocked if less than 2 GiB is available. Each attempt keeps
its own receipt and logs. A failed attempt is never reported as a complete GDS.

Keep final GDS, DEF, ODB, netlist, SDC, logs, metrics, and hashes. ODB net identities
are exported with Tcl because the selected image has no Python interface.
KLayout imports DEF wires with net properties. Explicit DEF NETS via statements
supply via ownership when KLayout omits these properties. Only supported,
unrotated via statements are eligible. Ownership is checked against ODB names;
geometry is checked against the merged GDS. Ambiguous geometry is excluded.
The reported route-segment count covers eligible, unambiguous signal geometry.
The via count covers decoded regular-net via instances. Full files also retain
protected power, clock, and other routing geometry. Instance counts include
the editable route cells and structural hierarchy cells.

Clock protection is checked against ODB signal types, clock terminals, CTS
buffer connections, and conservative clock-net names. Ambiguous clock
classification blocks the source.

Only routing via cells are expanded when preparing editable route cells. Real
standard-cell masters and their placements remain hierarchical. The preparation
and route partition must preserve the exact flattened source geometry.

## Rule qualification and policy

The scored profile retains the five C1 families and adds M2 spacing, M3 width,
V2 width, V1/M2 enclosure, and V2/M2/M3 enclosure checks. The qualification record
contains legal, legal-boundary, illegal-boundary, and clearly illegal cases.

The public enclosure expressions have grid-sensitive behavior. For the pinned
checker, the V1/M2 cap transition is 21 DBU and the V2/M3 transition is 19 DBU,
against the nominal 20-DBU/5-nm description. The record states this difference.
These fine-DBU transitions describe checker behavior; they are not new process limits.
Published boundary fixtures use the verified 1 nm manufacturing grid. The V1/M2
legal boundary is therefore a 6 nm cap; its 5 nm cap is checker-illegal.

The copied V2/M2 expression did not detect the tested defects. The C2+C3 profile
uses `v2.enclosed(m2, 5.nm, projection, one_side_allowed,
two_opposite_sides_allowed)` to report errors directly on the via. A separate
orientation matrix verifies opposite-side acceptance and adjacent-side rejection.
The public and C1 decks remain unchanged. This is scoped research checking, not
foundry signoff.

Each public edit policy names editable route cells, layers, local DBU masks,
and fixed anchors. Changed geometry must use the verified 1 nm grid. It also defines top-level inspection windows. All other cell
contents, properties, and instance definitions are immutable. Route components
must remain present. New same-layer overlap with protected geometry is rejected.
An empty editable-cell map requires unchanged geometry.

Model context contains current geometry in local and top-level coordinates,
instance paths, transforms, and the public policy. Required geometry is never
silently truncated. More than 1,024 shapes or 120,000 context characters blocks
the case. Transistor layers outside the routing context are listed as omitted.
Reference GDS, mutation records, and expected actions are not model inputs.

## Commands

Run commands from the project directory. Use the host environment when Docker
or Bubblewrap requires access outside the restricted session.

```bash
PY=.venv/bin/python
$PY -m klayout_drc.benchmark.c2c3.cli prepare --root output/c2c3/toolchain
$PY -m klayout_drc.benchmark.c2c3.cli qualify --output output/c2c3/qualification
$PY -m klayout_drc.benchmark.c2c3.cli generate-cells \
  --output test_data/benchmark_c2c3 \
  --library output/c2c3/toolchain/orfs/flow/platforms/asap7/gds/asap7sc7p5t_28_R_220121a.gds \
  --qualification output/c2c3/qualification/qualification.json
$PY -m klayout_drc.benchmark.c2c3.cli build --root output/c2c3/toolchain --design gcd --group 0
$PY -m klayout_drc.benchmark.c2c3.cli export-nets --build-dir output/c2c3/toolchain/builds/gcd_g0
$PY -m klayout_drc.benchmark.c2c3.cli generate-routed \
  --dataset test_data/benchmark_c2c3 --bundles output/c2c3/source_bundles.json \
  --platform output/c2c3/toolchain/orfs/flow/platforms/asap7
$PY -m klayout_drc.benchmark.c2c3.cli verify --dataset test_data/benchmark_c2c3
$PY -m klayout_drc.benchmark.c2c3.cli evaluate --dataset test_data/benchmark_c2c3 \
  --output reports/runs/c2c3_no_change --mode no_change
```

Use groups 0 and 1 for GCD and UART. For each UART group, stress builds use
`--density 0.75 --factor 1.0`, then factors `0.9` and `0.8`. `--attempt N` starts
a separate build attempt after a recorded infrastructure correction. It does
not overwrite the previous attempt.

Use `select-sources --root output/c2c3/toolchain --output
output/c2c3/source_bundles.json` after the builds. This command recomputes
occupancy and records every stress trial.

The source-bundle JSON is a list of objects with `level`, `group`, and
`build_dir`. L5 entries also need `matched_baseline_dir`. Select the completed
stress build with the largest `congestion_score` from `routed_generator`.

## Experiments and interpretation

Freeze the 50-case manifest, source, prompts, policies, model settings, and hashes
before the agent campaign. The CLI selects Bedrock explicitly and defaults to
`qwen.qwen3-coder-next`. It reads credentials only from the process environment.
There is one model request per case, at most 50 requests, and no repair retry.
An interrupted claim cannot be resumed by issuing the request again.

Run modes `no_change`, `heuristic`, and `agent` in separate output directories.
Only local baselines permit `--allow-incomplete`. The agent campaign requires
all 50 cases and all level gates. The existing heuristic is unchanged; it can
fail on child route cells or protected top-level routes. Report that limitation.

Repair credit requires a completed candidate, valid policy checks, all injected
targets resolved, and no introduced or ambiguous scored markers relative to the
original baseline. Both types of control require a successful unchanged output.
A script error does not earn control credit. The public full-deck audit is
reported separately and does not change the scored scope.

Reports contain JSON, CSV, Markdown, per-case run bundles, usage when returned,
sampled worker memory, and artifact hashes. Memory sampling is a lower bound.
Cost stays unknown without verified pricing. Results have separate denominators
of 30 repairs, 10 clean controls, and 10 read-only controls. A single attempt on
six repair cases per level does not establish repeatability or broad model
generalization. Electrical connectivity and timing remain unverified.

The full public-deck audit has a 600-second checker limit. Scored checks retain
the 120-second limit. Each completed audit records its runtime and command.
An audit timeout is recorded as a failure; it does not change the scored rules.

Generate a second corpus in a separate directory, using the same source bundles
and qualification record. Compare the two corpora with:

```bash
.venv/bin/python scripts/verify_c2c3_reproduction.py \
  test_data/benchmark_c2c3 output/c2c3/reproduced_final \
  --output output/c2c3/reproducibility_final.json
```

This check compares input and reference GDS bytes, canonical geometry and
hierarchy, canonical markers, policies, metrics, and source metadata. It also
lists report byte differences caused by marker ordering.

After qualification, run `.venv/bin/python scripts/export_c2c3_windows.py
test_data/benchmark_c2c3` to export the 50 local inspection clips. The clips keep
the original coordinates and database units. They contain the routing layers
in each public inspection window. `windows/manifest.json` maps each clip to its
full input file and hashes. Evaluation always uses the full GDS files.
