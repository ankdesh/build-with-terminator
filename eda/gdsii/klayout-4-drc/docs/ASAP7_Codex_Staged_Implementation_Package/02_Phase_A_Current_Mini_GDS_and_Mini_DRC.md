# Phase A — Prove the Existing Small GDS + Mini DRC Pipeline

**Depends on:** Foundation 0 (single-shot Fix → Apply Patch → Report)  
**Goal:** End-to-end proof on *current synthetic fixtures*, not real ASAP7 compliance  
**Entry criterion:** Candidate execution and reporting exist and negative cases fail correctly.  
**Exit criterion:** Repeatable single-shot agent/known-script runs on the current mini deck with truthful before/after evidence.

## Why this stage is intentionally conservative

The current repo has a small synthetic GDS generator (`test_data/layouts/create_sample_layout.py`) and a three-category `test_data/rules/asap7_mini.drc` (`M1_W`, `M1_S`, `V1_M1_ENC`). Existing tests assert **eight** observed markers on the fixture and **zero** after the deterministic `DRCFixer`. This is the *source's expected test behavior*, not a newly measured result.

It presently treats `18/0` as M1 and `19/0` as V1, while the published ASAP7 KLayout convention uses `19/0` for M1 and `21/0` for V1. Its generator sets `layout.dbu=0.001 µm` while the knowledge/prompt mentions `0.00025 µm`. **Do not conflate this fixture with actual ASAP7 DRC.**

To minimize debugging dimensions, preserve the original fixture and mini deck under an explicitly named `legacy_mini` profile, even if their artificial conventions are not authentic ASAP7. Perform the real technology migration in Phase B.

## A0 — Establish the exact baseline

1. Pin the source revision, versions of Python, `klayout`, Node, `uv`, and DSH.
2. Run the original pytest suite. Record the observed counts and failures rather than assuming source assertions pass locally.
3. Run the existing CLI mini deck against the existing example; save its exact `.lyrdb` and text report.
4. Inspect sample GDS layers, top cell, DBU, and geometry. Record mismatch with official ASAP7 separately.
5. Keep the original eight-marker snapshot as a **legacy regression**. Do not overwrite it by fixing sample geometry in place.

**Example verification:**

```bash
cd eda/gdsii/klayout-4-drc
uv run pytest -q
uv run python -m klayout_drc.cli --mode run-drc --json \
  --gds test_data/layouts/asap7_test.gds \
  --deck test_data/rules/asap7_mini.drc \
  --report-db reports/phase_a_before.lyrdb
```

Any command incompatibility discovered in the active branch must be documented and corrected, not assumed to work as written.

## A1 — Demonstrate `Fix → Apply Patch → Report` three ways

- **A1.1 Injected known-good script:** An independently inspected repair script that produces an output passing the mini DRC and basic shape-integrity checks. This validates the toolchain independent of an LLM.
- **A1.2 Deterministic baseline:** Run the existing `DRCFixer` with `mode=heuristic_baseline`. Report any invalid electrical or geometric assumptions. Its success against the mini DRC alone is `geometry_only`, never automatically electrically validated.
- **A1.3 Agent-generated script:** Run the intended DSH/model entry point with `mode=agent`; save actual model ID, prompt/model response, saved candidate, command result, and DRC before/after. If model credentials are unavailable, mark this test **blocked**, not passed.

All three paths must invoke the **same** `apply_patch` and `report_result` validation infrastructure. The agent path must not fall back into A1.2 without explicitly switching modes.

## A2 — Build an honest small-fixture suite

Create versioned `legacy_mini_v2` fixtures **separate** from the original. Fix the confusing sample comment that labels a ~1 nm lateral via enclosure example as valid, either by correcting the polygon or moving it into a deliberately invalid fixture. Verify expected validity with DRC, not source comments.

Cover at least:

| Case | Intent | Expected report classification |
|---|---|---|
| A-W-1 | Isolated narrow wire | `M1_W` present before, absence only if actually corrected |
| A-S-1 | Close metal pair | `M1_S` present before; a repair joining separate known nets is invalid |
| A-E-1 | Insufficient via enclosure | `V1_M1_ENC` present before |
| A-OK-1 | Valid geometry under mini deck | No repair needed; acceptable `no_change` |
| A-MIX-1 | Multiple simultaneous violations | Reports all affected categories |
| A-INVALID-1 | Delete-all or global destructive script | Fails integrity/edit/connectivity safety gates |
| A-INVALID-2 | Syntax error, no GDS, timeout | Explicit failure, preserved input |
| A-DBU-1 | Physically identical geometry encoded with different DBU | Equivalent physical measurements |

For A-S-1, a simple synthetic two-net annotation/invariant is sufficient to detect prohibited joining; do not claim complete LVS from it. Preserve negative tests even when they use simplified connectivity annotations.

## A3 — Report contents for every case

Each `report.md` should show the same sections and audit links:

1. **Input:** GDS path/hash, mini-deck hash, `legacy_mini` profile, DBU/top cell and expected rule scope.
2. **Before:** actual marker categories/counts and any invalid/unreliable checker behavior.
3. **Fix:** candidate source (`agent`/`heuristic_baseline`/`script_file`), script hash, rationale, model details if applicable.
4. **Apply:** exit code, timeout/resource usage, stdout/stderr, output path/hash.
5. **After:** real rerun of the same mini deck; before/after marker comparison; introduced or remaining markers.
6. **Validation:** layout integrity and simple synthetic invariants; explicitly `connectivity_unverified` where applicable.
7. **Verdict:** status and supported evidence, plus remaining limitations.

Suggested summary table: `case_id | source_mode | DRC_before | DRC_after | new_markers | patch_valid | connectivity_scope | final_status`.

## A4 — Files likely touched

- Existing: `test_data/layouts/create_sample_layout.py`, `test_data/rules/asap7_mini.drc` **only for versioned additions, not silent migration**; `tests/test_drc_pipeline.py`.
- New: `tests/test_single_shot_pipeline.py`, `tests/fixtures/legacy_mini_v2/`, `tests/test_patch_failures.py`, `docs/phase_a_results.md` or equivalent.
- Foundation code reused: `repair_executor.py`, `validator.py`, `run_artifacts.py`, DSH operations, reporter/runner.

## A5 — Mandatory tests and exit gate

- The original tests remain runnable; deviations are explained before updating golden data.
- A fixed deterministic candidate can be applied once, a real before/after mini DRC run occurs, and every referenced artifact exists.
- At least one **real model-generated** run is attempted and its result truthfully recorded; if blocked by credentials, Stage A cannot claim verified agent efficacy.
- A no-op, delete-all, syntax error, missing output, incorrect deck invocation, and model failure all have correct distinct statuses.
- A report cannot say `success_full` unless an independent connectivity check actually ran and passed; otherwise use geometry-only classification.
- No iterative agent retries or automatic prompt revision are introduced.

## Deliberately deferred to B/C/D

- Correct official ASAP7 physical layer mapping, public deck, XML macro/rule catalog: **B**.
- Hierarchical cell windows, real routed layout growth, 100-case generator: **C** (prerequisites built in B).
- Automatic retry, reflection, planner/critic roles: **D, separate design**.

## Codex handoff

Implement this phase in one or two small PRs after Foundation. Provide a representative successful single-shot run and at least three failure reports, including actual commands and full artifact paths. Consult original findings F02, F04, F05, F12, F13 and original WP0/WP1/WP3 as they pertain to *legacy* fixtures.
