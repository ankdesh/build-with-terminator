# OpenAI versus Bedrock: same 100-case C1 setup

Date: 2026-10-28

The OpenAI campaign requested `gpt-6-luna` at `https://api.openai.com/v1/chat/completions`, using `OPENAI_MODEL` and `OPENAI_API_KEY` from the environment. The baseline used `qwen.qwen3-coder-next` on AWS Bedrock in `ap-southeast-2`.

**OpenAI repaired 72/78 dirty inputs (92.3%); Bedrock repaired 37/78 (47.4%). OpenAI preserved 22/22 clean controls; Bedrock preserved 19/22.**

## Comparison controls

The live workspace had changed after the Bedrock campaign. To keep the comparison controlled, the OpenAI run used a separate workspace reconstructed from the saved Bedrock source snapshot. Live development files were not reset. The snapshot includes the strict API-only instructions, reference renderer, synthesis contract, sandbox code, validator, checker setup, and scorer.

The source digest, deck, dataset, profile, case order, worker count, and explicit temperature setting match the baseline. 100/100 saved request payloads match the Bedrock payloads exactly after removing the model field. This includes system/user messages and JSON response mode.

Both runs use one attempt per entry and the same Bubblewrap isolation. No candidate retries or manually corrected substitutions were used. The model and provider change together; results do not isolate an endpoint effect. Reasoning and sampling defaults were not overridden, so model-specific defaults can differ. Local preflight executed all 63 reference contracts and 12 example groups. Both request-contract test files passed with mocked model calls.

## Results

| Measure | OpenAI | Bedrock |
|---|---:|---:|
| Dirty layouts repaired | 72/78 | 37/78 |
| Geometry repair rate | 92.3% | 47.4% |
| Clean controls passed unchanged | 22/22 | 19/22 |
| KLayout binding failures (reviewed) | 1 | 15 |
| API or Python type crashes | 1 | 17 |
| Model request timeouts | 2 | 0 |
| Candidate response-contract errors | 0 | 5 |
| Model requests / JSON responses | 100 / 98 | 100 / 100 |
| Batch wall time | 1558.87 s | 550.74 s |
| Prompt tokens | 657,487 | 694,913 |
| Completion tokens | 394,121 | 126,724 |
| Total tokens | 1,051,608 | 821,637 |

The Bedrock API/type total contains 15 KLayout binding failures and two Python value-type failures. The common comparison metric counts AttributeError and TypeError crashes; the underlying tracebacks are saved. Syntax failures and response-contract errors are separate. Token counts use each provider's reported usage and can use different tokenizers. Calls without a response do not contribute reported usage, so token totals are not a billing audit. Batch time includes local checking as well as model generation. Both runs retain the same 90-second model timeout. Costs are not reported as billed values.

| Verdict | OpenAI | Bedrock |
|---|---:|---:|
| clean_success | 72 | 37 |
| clean_unchanged | 22 | 19 |
| failed_unchanged | 3 | 10 |
| invalid_patch | 1 | 25 |
| model_error | 2 | 5 |
| partial_success | 0 | 1 |
| regression | 0 | 3 |

| Rule | Dirty cases | OpenAI repaired | Bedrock repaired | OpenAI clean controls | Bedrock clean controls |
|---|---:|---:|---:|---:|---:|
| M1.A.1 | 15 | 14 | 11 | 5/5 | 4/5 |
| M1.S.1 | 15 | 12 | 2 | 5/5 | 4/5 |
| M1.W.1 | 16 | 15 | 9 | 4/4 | 3/4 |
| M2.W.1 | 16 | 15 | 6 | 4/4 | 4/4 |
| V1.W.1 | 16 | 16 | 9 | 4/4 | 4/4 |

## Paired dirty-case outcomes

| Outcome | Cases |
|---|---:|
| Both repaired | 36 |
| OpenAI repaired; Bedrock did not | 36 |
| Bedrock repaired; OpenAI did not | 1 |
| Neither repaired | 5 |

The paired table compares the exact same 78 dirty entries. The CSV records every case verdict and its OpenAI failure stage.

## OpenAI execution and synthesis failures

| Stage | Cases |
|---|---:|
| geometry_reasoning | 3 |
| python_execution | 1 |
| synthesis | 2 |

API/type exceptions:

| Case | Exception |
|---|---|
| `m2_w1_iso_03` | AttributeError: 'pya._Iterator' object has no attribute 'at_end' |

Other unsuccessful OpenAI entries:

| Case | Outcome | Stage |
|---|---|---|
| `m1_w1_int_03` | model_error | synthesis |
| `m2_w1_iso_03` | invalid_patch | python_execution |
| `m1_a1_iso_04` | model_error | synthesis |
| `m1_s1_iso_02` | failed_unchanged | geometry_reasoning |
| `m1_s1_iso_05` | failed_unchanged | geometry_reasoning |
| `m1_s1_int_03` | failed_unchanged | geometry_reasoning |

## Audit and limits

- Verified 2,478 OpenAI artifact hashes and 2,369 Bedrock artifact hashes.
- All 2,681 saved Bedrock campaign files remain unchanged.
- Exact payload matches after excluding model: 100/100.
- Python, KLayout, Node, checker, and harness package versions match: True.
- No active OpenAI key was found in 2,789 campaign files scanned.
- Returned OpenAI models: `{"gpt-6-luna": 98}`.
- OpenAI response finish reasons: `{"stop": 98}`.
- Reported OpenAI usage detail: `{"completion_tokens": 394121, "completion_tokens_details.accepted_prediction_tokens": 0, "completion_tokens_details.audio_tokens": 0, "completion_tokens_details.reasoning_tokens": 286316, "completion_tokens_details.rejected_prediction_tokens": 0, "prompt_tokens": 657487, "prompt_tokens_details.audio_tokens": 0, "prompt_tokens_details.cache_write_tokens": 503468, "prompt_tokens_details.cached_tokens": 153725, "total_tokens": 1051608}`.

Reference: KLayout 0.30.8, 63 checked call contracts and 12 example groups; reference digest `ad5b7aab61cfeb241a0bbf8188485f49a2629056f325a56e4a2f6593ea8dbac5`.

These are single-attempt development results for 100 entries representing 93 distinct layout groups. They do not establish repeatability, held-out performance, or electrical correctness. Failed clean controls are not counted as preserved successes. Missing after-checks remain unknown.

Campaign: `reports/runs/c1_openai_all100_strict_api_20261028/`.

The campaign stores exact requests/responses, candidate scripts, DRC reports, `summary.json`, `comparison.json`, `comparison.csv`, and `verification.json`. The separate setup directory contains the reconstructed source workspace and the Bedrock preservation ledger.

## Official API documentation checked

- [GPT-6 Luna model and endpoint support](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Chat Completions and JSON object response mode](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
