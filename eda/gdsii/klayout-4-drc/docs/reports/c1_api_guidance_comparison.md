# Verified KLayout API guidance: ten-case comparison

Date: 2026-10-27

The verified reference and dispatch checks are implemented and tested. The
matched AWS pilot completed, but **the model acceptance targets were not met**.
This change does not establish that API hallucinations have been eliminated.

## Implementation and local validation

The canonical reference in `src/klayout_drc/api_reference.py` supplies seven
executable example groups. It covers layout I/O and layers, DBU and grid
conversion, polygon iteration and area with holes, rectangle-only measurement,
width-check return types, sizing and translation, edge-filter overloads, and
physical-box conversion. Each example includes notes, official documentation
links, and checks on returned values or geometry.

The knowledge loader renders the reference into the existing knowledge string.
Both synthesis routes verify the reference with the candidate Python environment
before dispatch and record the runtime version and reference digest. Failed
reference checks produce a configuration error and a `blocked` benchmark result.
Markdown and candidate scripts are not executed by this gate. Candidate
execution still uses Bubblewrap. The candidate output schema is unchanged.

The repair guidance now distinguishes length and area units, requires component
area checks, explains Python versus Ruby API differences, and removes the
suggestion to merge wires when net ownership is unknown. The synthesis prompt
requires tested call forms and an explicit rationale when a needed operation is
unsupported.

Validation completed before the paid experiment:

- Full Python suite with host Bubblewrap support: **128 passed, 2 skipped** in
  322.37 seconds. Live model tests remained opt-in.
- Harness request tests: **7 passed**, including identical reference delivery
  through both synthesis routes and zero requests on reference failure.
- TypeScript build/type checking and whitespace checks passed.

Verified runtime: `klayout.db 0.30.8`.

Reference SHA-256:
`e0f8a5a8d5a2ac0f4f7a008d90473465c5db37ec351f2a5ad5fb5527d0f17f66`.

## Matched experiment

The runner's comparison gate verified the same ten case IDs, five dirty cases
and five clean controls, requested model, provider, region, temperature, profile,
deck hash, dataset manifest hash, and case geometry hashes. The new output
directory preserves the original campaign and summary hashes and saves the
pilot runner source.

Both runs used `qwen.qwen3-coder-next` through AWS Bedrock in `ap-southeast-2`.
Each run made exactly ten requests and received ten responses, with one attempt
per case and no retries. Neither run had a model service error.

| Measure | Original pilot | Verified-guidance pilot |
|---|---:|---:|
| Dirty cases repaired | 2/5 (40%) | 2/5 (40%) |
| Clean controls completed unchanged | 5/5 | 4/5 |
| Invalid scripts | 3 | 4 |
| Missing API member failures (`AttributeError`) | 3 | 1 |
| Wrong API call/type failures (`TypeError`) | 0 | 3 |
| Total API execution failures | 3 | 4 |
| Batch elapsed time | 53.02 s | 59.73 s |
| Prompt tokens | 30,734 | 44,214 |
| Completion tokens | 7,750 | 12,756 |
| Total tokens | 38,484 | 56,970 |

Cost remains unknown because no verified price was supplied. Clean controls do
not contribute repair credit. A rejected script has no accepted repaired layout
or after-DRC observation; it is not a successful unchanged control.

## Per-case outcomes and remaining failures

| Case | Original | Verified guidance |
|---|---|---|
| `m1_w1_iso_01` | Repaired | Invalid: called `EdgePair.first` as a method |
| `m1_w1_neg_01` | Unchanged | Invalid: called nonexistent `EdgePairs.empty()` |
| `m2_w1_iso_01` | Invalid: `Region.min_width()` | Invalid: passed a `Shape` to `Region.insert()` |
| `m2_w1_neg_01` | Unchanged | Unchanged |
| `m1_a1_iso_01` | Invalid: `Region.each_polygon()` | Repaired |
| `m1_a1_neg_01` | Unchanged | Unchanged |
| `m1_s1_iso_01` | Invalid: `Edges.MaxLength` | Invalid: passed an iterator to `Region.insert()` |
| `m1_s1_neg_01` | Unchanged | Unchanged |
| `v1_w1_iso_01` | Repaired | Repaired |
| `v1_w1_neg_01` | Unchanged | Unchanged |

The area case now passes; the M1 width case and one clean control no longer
complete successfully. Although missing-member failures fell, total API
execution failures increased. The target of zero missing-member failures and
five successful unchanged controls therefore failed. Do not present this pilot
as an overall model improvement.

The next reference gaps to address are EdgePairs inspection (`is_empty()`,
`each()`, and the `first`/`second` properties), conversion of `Shape` objects to
supported geometry types, and the accepted insertion forms for Regions versus
Python iterators. That is follow-up work; this campaign was not retried or
expanded. The gate verifies the supplied examples, not arbitrary model code.

These are single-attempt development observations. They do not establish a
causal effect, repeatability, generalization, or electrical repair validity.
Successful repairs remain geometry-only within the curated checker scope.

## Audit artifacts

Original run: `reports/runs/c1_bedrock_pilot10_20261027/`.

New run: `reports/runs/c1_bedrock_pilot10_api_guidance_20261027/`.

The new directory includes `comparison.json`, `verification.json`,
`comparison_baseline.json`, campaign/summary files, exact requests and responses,
candidate scripts, checker evidence, and execution logs.

All **234 new-run artifact hashes** and **228 original-run artifact hashes**
matched. Original campaign and summary hashes remained unchanged. All saved
request prompt hashes and context hashes matched generation records, and all
ten requests used the expected reference metadata. A local scan of 272 new-run
files found no copy of the active AWS API key.

No additional 90-case campaign was started.
