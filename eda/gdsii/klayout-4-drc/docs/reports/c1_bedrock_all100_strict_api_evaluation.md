# Bedrock: all 100 cases with strict API instructions

Date: 2026-10-27

The requested run completed with `qwen.qwen3-coder-next` through AWS Bedrock in `ap-southeast-2`. The environment supplied the model and credentials. The user expanded the requested scope from 50 isolated cases to all 100 entries, then explicitly approved the payload and destination.

**37/78 dirty inputs were repaired (47.4%). 19/22 clean inputs completed unchanged. There were 17 API/type execution failures: 15 KLayout binding failures and 2 Python value-type failures.**

## Change and checks

The system message, repair instructions, and final prompt reminder now require the model to use only KLayout API forms supplied in the verified reference. They prohibit extra methods, properties, constructors, overloads, and conversions from memory. They require receiver/argument/return-type checks and preservation of affected geometry when no supported operation exists. Standard-library use is allowed. The reference document itself was not changed.

Local checks: 132 Python checks passed in the restricted session. All seven previously skipped Bubblewrap integration checks passed on the host. Both harness test files and the TypeScript no-emit check passed. The route-contract test checks that both synthesis routes receive the same stricter messages.

## Outcomes

| Outcome | Cases |
|---|---:|
| clean_success | 37 |
| clean_unchanged | 19 |
| failed_unchanged | 10 |
| invalid_patch | 25 |
| model_error | 5 |
| partial_success | 1 |
| regression | 3 |

| Rule | Dirty repaired / inputs | Clean unchanged / controls | Invalid scripts or patches |
|---|---:|---:|---:|
| M1.A.1 | 11/15 | 4/5 | 2 |
| M1.S.1 | 2/15 | 4/5 | 11 |
| M1.W.1 | 9/16 | 3/4 | 4 |
| M2.W.1 | 6/16 | 4/4 | 4 |
| V1.W.1 | 9/16 | 4/4 | 4 |

API/type execution failures are AttributeError/TypeError crashes in candidate logs. This count does not measure every unsupported API use in all generated source. Invalid patches also include preservation rejection and Python syntax failures.

AttributeError crashes: 8. TypeError crashes: 9. Traceback review separates Decimal/float arithmetic and tuple-member access from the 15 KLayout binding failures.

| Case | Recorded exception |
|---|---|
| `m1_w1_iso_10` | AttributeError: 'Box' object has no attribute 'left_bottom' |
| `m1_w1_neg_01` | AttributeError: 'PolygonWithProperties' object has no attribute 'polygon' |
| `m2_w1_iso_03` | TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'float' |
| `m2_w1_iso_10` | AttributeError: 'PolygonWithProperties' object has no attribute 'polygon' |
| `m1_a1_bnd_03` | TypeError: 'builtin_function_or_method' object cannot be interpreted as an integer |
| `m1_s1_iso_02` | TypeError: No overload with matching arguments. Variants are: |
| `m1_s1_iso_03` | TypeError: No overload with matching arguments. Variants are: |
| `m1_s1_iso_04` | TypeError: No overload with matching arguments. Variants are: |
| `m1_s1_iso_09` | TypeError: No overload with matching arguments. Variants are: |
| `m1_s1_iso_10` | AttributeError: 'Edge' object has no attribute 'to_box' |
| `m1_s1_bnd_02` | TypeError: No overload with matching arguments. Variants are: |
| `m1_s1_bnd_03` | AttributeError: 'pya._Iterator' object has no attribute 'at_end' |
| `m1_s1_int_02` | TypeError: No overload with matching arguments. Variants are: |
| `v1_w1_iso_01` | TypeError: No overload with matching arguments. Variants are: |
| `v1_w1_iso_04` | AttributeError: 'EdgePairs' object has no attribute 'each_merged' |
| `v1_w1_bnd_01` | AttributeError: 'PolygonWithProperties' object has no attribute 'polygon' |
| `v1_w1_int_03` | AttributeError: 'tuple' object has no attribute 'first' |

Failure-stage counts:

| Stage | Cases |
|---|---:|
| geometry_reasoning | 11 |
| preservation | 4 |
| python_execution | 21 |
| regression | 3 |
| synthesis | 5 |

Responses rejected by the candidate JSON contract:

| Case | Returned fields |
|---|---|
| `m2_w1_int_03` | `["python_script"]` |
| `m1_a1_iso_01` | `["python_script"]` |
| `m1_a1_iso_03` | `["python_script"]` |
| `m1_a1_iso_08` | `["python_script"]` |
| `v1_w1_int_01` | `["python_script"]` |

## Same ten cases from the previous run

These entries are an overlap within the expanded campaign. Single attempts and other pre-existing source changes prevent a claim that the prompt change alone caused an outcome difference.

| Case | Previous single-reference run | Current strict-instruction run |
|---|---|---|
| `m1_w1_iso_01` | clean_success | clean_success |
| `m1_w1_neg_01` | clean_unchanged | invalid_patch |
| `m2_w1_iso_01` | clean_success | clean_success |
| `m2_w1_neg_01` | clean_unchanged | clean_unchanged |
| `m1_a1_iso_01` | clean_success | model_error |
| `m1_a1_neg_01` | clean_unchanged | clean_unchanged |
| `m1_s1_iso_01` | invalid_patch | failed_unchanged |
| `m1_s1_neg_01` | clean_unchanged | clean_unchanged |
| `v1_w1_iso_01` | invalid_patch | invalid_patch |
| `v1_w1_neg_01` | clean_unchanged | clean_unchanged |

## Runtime and audit

- Model requests: 100; completed JSON responses: 100.
- Returned models: `{"qwen.qwen3-coder-next": 100}`.
- Batch elapsed: 550.74 seconds.
- Reported tokens: `{"completion_tokens": 126724, "prompt_tokens": 694913, "total_tokens": 821637}`.
- Cost: unknown; no verified price was supplied.
- One attempt per case. No automatic retries or manually corrected substitutions.
- Bubblewrap execution, pinned checker, accepted baseline evidence, and preservation checks were retained.
- All 2369 recorded per-run artifact hashes matched.
- All 899 recorded files from earlier campaigns stayed unchanged.
- Every saved request contained the full reference exactly once and the strict API instructions.
- Prompt/context hashes and reference metadata matched the generation records.
- No active AWS key was found in 2681 campaign files scanned.

Reference: KLayout 0.30.8; 63 call contracts; 12 executable example groups. SHA-256:

`ad5b7aab61cfeb241a0bbf8188485f49a2629056f325a56e4a2f6593ea8dbac5`.

The complete campaign source snapshot is saved. The shared workspace also contains C2/C3 development changes outside this task. The audit records live differences from the snapshot and source-hash variants across cases in `verification.json`; they must be considered when comparing campaigns.

Live source differences at final audit:

- `harness/lib/drc-operations.js`
- `harness/lib/types.d.ts`
- `harness/lib/types.js`
- `src/klayout_drc/benchmark/c2c3/evaluator.py`
- `src/klayout_drc/benchmark/c2c3/generator.py`
- `src/klayout_drc/benchmark/c2c3/rules.py`
- `src/klayout_drc/benchmark/c2c3/toolchain.py`
- `src/klayout_drc/edit_policy.py`

Files with per-case source-hash variation:

- `src/klayout_drc/benchmark/c2c3/generator.py`
- `src/klayout_drc/benchmark/c2c3/rules.py`
- `src/klayout_drc/edit_policy.py`
- `src/klayout_drc/benchmark/c2c3/toolchain.py`

## Limits and files

The three clean controls that did not pass all stopped during Python execution. They are not counted as preserved successes, and their missing after-results do not establish that their geometry was changed.

Results cover geometry compliance in the curated deck. They do not establish electrical correctness or performance on held-out layouts. Documentation and prompt restrictions do not enforce arbitrary generated Python API use.

Campaign directory: `reports/runs/c1_bedrock_all100_strict_api_20261027/`.

The campaign includes exact requests/responses, scripts, sandbox errors, DRC reports, `summary.json`, `summary.csv`, `analysis.json`, `verification.json`, and source snapshots. Failed candidates and their original results are retained.
