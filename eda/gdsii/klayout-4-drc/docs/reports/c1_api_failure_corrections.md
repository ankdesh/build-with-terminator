# Local correction of the four API failures

Date: 2026-10-27

All four failed scripts from the verified-guidance pilot were corrected in
separate copies and validated locally. Three dirty inputs now pass the pinned
DRC and preservation checks. The clean control completes with unchanged
geometry. **No model requests were made.**

## Corrections and observed results

| Case | API correction | Local result |
|---|---|---|
| `m1_w1_iso_01` | Read `edge_pair.first` as a property; replace `polygon.contains(point)` with `polygon.inside(point)` | 1 marker to 0; preservation passed |
| `m1_w1_neg_01` | Replace both `markers.empty()` calls with `markers.is_empty()` | 0 markers; geometry unchanged |
| `m2_w1_iso_01` | Construct the Region from the Shapes collection instead of inserting individual Shape handles | 1 marker to 0; preservation passed |
| `m1_s1_iso_01` | Insert the shifted Region directly instead of passing its polygon iterator to `insert()` | 1 marker to 0; preservation passed |

The width script contained the unsupported `Polygon.contains()` call after its
first failing statement. Inspection identified and corrected it before local
execution. `Polygon.inside(point)` includes a point on the polygon boundary,
which is needed when locating a polygon from a DRC marker edge.

Validation used the existing benchmark acceptance records, immutable GDS inputs,
pinned curated deck, Bubblewrap worker, component/protected-region validation,
layout diff, and before/after checker comparison. Candidate mode was
`script_file`, with provenance labeled `manual_api_correction`.

## Reference and regression coverage

The canonical reference now has **nine** executable example groups. New examples
cover marker emptiness and iteration, EdgePair/Edge/Point properties, Region
construction and insertion, and polygon inside/boundary tests. The prompt and
knowledge notes name the unsupported forms and show the verified replacements.

Regression tests reproduce the failing calls and verify that their replacements
preserve existing destination geometry, source geometry, holes, and boundary
semantics. Both synthesis routes receive the expanded reference.

- Relevant Python suite: **57 passed**, 7 sandbox tests deselected in the
  restricted test command. The four local correction runs executed separately
  with working host Bubblewrap isolation.
- Harness tests: **7 passed**.
- All **56 local-run artifact hashes** and **234 original model-run artifact
  hashes** matched. Original script hashes and corrected-copy hashes matched
  their correction records. No original candidate script was overwritten.
- Whitespace checks passed.

Runtime: `klayout.db 0.30.8`.

Expanded reference SHA-256:
`905507da337f31f850f768590640346c6c0694c9bacf0a1401b2571ca115c2e7`.

## Artifacts and interpretation

Local corrections are under `reports/runs/c1_api_failure_corrections_20261027/`:

- `scripts/`: corrected candidate copies and minimal unified diffs.
- `corrections.json`: original paths, original/corrected hashes, and replacements.
- `local_campaign.json`, `local_runner.py`, and `frozen_source.json`: provenance.
- `summary.json`, `summary.csv`, `report.md`, and `verification.json`: results.
- `runs/`: individual sandbox, validation, geometry-diff, and checker evidence.

The original AWS campaign remains
`reports/runs/c1_bedrock_pilot10_api_guidance_20261027/`. Its recorded model scores
remain 2/5 dirty cases repaired and 4/5 clean controls completed unchanged. The
local corrections must not increase those model scores. The expanded reference
has not been evaluated in a new live model campaign.

These results establish geometry-only validity for the four selected inputs.
They do not establish electrical validity or repair behavior on other layouts.
