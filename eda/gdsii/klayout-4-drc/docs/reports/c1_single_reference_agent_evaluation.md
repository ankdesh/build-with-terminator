# Ten-case agent rerun with the single API reference

Date: 2026-10-27

The agent rerun completed using AWS Bedrock in `ap-southeast-2` and requested
model `qwen.qwen3-coder-next`, read from the environment. It made ten requests
and received ten responses, with one attempt per original case and no retries.
No manually corrected candidate was supplied to the agent or substituted for
its output.

## Results

**3/5 dirty inputs were repaired (60%). All 5/5 clean controls completed with
unchanged geometry. Two generated scripts failed on nonexistent API members.**

| Measure | Original pilot | Previous guidance | Single reference |
|---|---:|---:|---:|
| Dirty cases repaired | 2/5 | 2/5 | 3/5 |
| Clean controls completed unchanged | 5/5 | 4/5 | 5/5 |
| Invalid scripts | 3 | 4 | 2 |
| Missing-member failures | 3 | 1 | 2 |
| API argument/type failures | 0 | 3 | 0 |
| Batch elapsed time | 53.02 s | 59.73 s | 59.78 s |
| Prompt tokens | 30,734 | 44,214 | 63,724 |
| Completion tokens | 7,750 | 12,756 | 10,325 |
| Total tokens | 38,484 | 56,970 | 74,049 |

The model service returned no errors. Cost is unknown because no verified price
was supplied. Clean controls do not contribute repair credit.

| Dirty case | Result | Evidence |
|---|---|---|
| `m1_w1_iso_01` | Repaired | 1 marker to 0; preservation checks passed |
| `m2_w1_iso_01` | Repaired | 1 marker to 0; preservation checks passed |
| `m1_a1_iso_01` | Repaired | 1 marker to 0; preservation checks passed |
| `m1_s1_iso_01` | Invalid script | Called nonexistent `Edge.to_p1()` |
| `v1_w1_iso_01` | Invalid script | Accessed nonexistent `PolygonWithProperties.polygon` |

All five corresponding `*_neg_01` controls were `clean_unchanged`. The two failed
scripts stopped during Python execution, so their after-DRC observations are
absent. They were not repaired locally as part of this rerun.

## Reference and experiment integrity

The run used the 16,169-character self-contained reference for KLayout 0.30.8:
63 behavior-checked call contracts and 12 executable example groups. Each saved
request contained the complete document exactly once.

Reference SHA-256:
`ad5b7aab61cfeb241a0bbf8188485f49a2629056f325a56e4a2f6593ea8dbac5`.

Comparison preflight required the original case IDs, model/provider/region/
temperature, profile, deck hash, dataset manifest hash, and case geometry hashes.
The new run used a separate directory and kept Bubblewrap isolation, baseline
oracle checks, preservation validation, and the pinned DRC checker.

All **242 new-run artifact hashes**, **234 previous-guidance artifact hashes**,
and **228 original-pilot artifact hashes** matched. The original campaign and
summary hashes remained unchanged. Saved context and prompt hashes matched their
generation records. A local scan of 280 new-run files found no copy of the active
AWS API key.

## Interpretation and artifacts

Observed repair success increased from 2/5 to 3/5 and the clean-control outcome
returned to 5/5. Total API execution failures fell from four to two compared with
the previous guidance run. **The zero-API-error target was not met.** The
reference checks validate the supplied guidance; they do not check arbitrary
generated Python. The new failures use calls outside the supplied contract.

These are single-attempt development results, not evidence of consistent or
held-out performance. Success is geometry-only within the curated scope and
does not establish electrical correctness.

Artifacts: `reports/runs/c1_bedrock_pilot10_single_reference_20261027/`.
The directory contains the campaign source snapshot, exact requests/responses,
candidate scripts, sandbox/DRC evidence, `comparison.json`, `verification.json`,
and the verification runner. No 100-case campaign was started.
