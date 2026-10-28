# Corrected C1 evaluation

Date: 2026-10-22

Status: evaluation corrections and heuristic campaign complete. The agent campaign is blocked pending explicit external-payload approval.

## Verification

- Full Python suite: 93 passed, 1 optional live test skipped (335.08 seconds).
- Final regression subset after the last changes: 30 passed.
- Harness type checking passed; both mocked model-contract tests passed.
- All 100 cases and 100 synthetic legal references passed the pinned curated checker.
- Fresh generation matched all case GDS hashes, marker records, and stable manifest metadata.
- Dataset release 1.1.0 preserves all original case geometry: 100 entries, 93 distinct layouts, 78 dirty entries, 22 clean controls.
- All 1,340 recorded heuristic artifact hashes were verified after the campaign.

## Heuristic comparator

One attempt per entry. Up to four entries ran independently at once. Batch wall time: 193.50 seconds.

Geometry repair success: **59/78 dirty entries (75.64%)**. This is curated-scope geometry compliance with component preservation, not electrical repair validation.

| Outcome | Dirty entries | Clean controls |
|---|---:|---:|
| clean_success | 59 | 0 |
| clean_unchanged | 0 | 4 |
| invalid_patch | 17 | 3 |
| regression | 2 | 2 |
| unnecessary_edit | 0 | 13 |

The 22 clean controls are excluded from the repair denominator. Only four stayed geometrically unchanged. Thirteen received unnecessary edits; three patches were rejected and two produced regressions. These outcomes must not increase the repair rate.

## Category results

| Category | Entries | Geometry repair successes | Rejections | Regressions |
|---|---:|---:|---:|---:|
| M1.A.1 | 20 | 14 | 1 | 0 |
| M1.S.1 | 20 | 0 | 18 | 2 |
| M1.W.1 | 20 | 15 | 1 | 0 |
| M2.W.1 | 20 | 14 | 0 | 2 |
| V1.W.1 | 20 | 16 | 0 | 0 |

Category entry totals include clean controls; repair successes only count dirty entries.

## Agent campaign

**Not measured. Zero model requests were sent.** Automatic approval review rejected the campaign because external transfer of the local geometry, DRC context, and project guidance requires explicit payload and destination approval.

The proposed destination is `https://api.openai.com/v1/chat/completions`, with requested model `gpt-6-luna`. All 100 proposed request bodies and their hashes are saved locally for review. They exclude clean references, manifest expectations, mutation records, full project source, and credentials. The existing API key would be used only in the Authorization header.

Blocked agent summary fields are completion accounting, not a model-performance estimate. Do not interpret zero clean-success counts as model failure.

## Artifacts

- Heuristic campaign: `reports/runs/c1_corrected_heuristic/` (JSON, CSV, Markdown, source snapshot, case checkpoints, and full run bundles).
- Agent approval record: `reports/runs/c1_corrected_agent/approval_request.json`.
- Agent payload review: `reports/runs/c1_corrected_agent/payload_review.md`.
- Proposed request bodies: `reports/runs/c1_corrected_agent/prepared_requests/`.

Run bundles remain local and ignored by Git. This report and the corrected dataset metadata are versioned.

## Limits

This is a development benchmark with assisted prompts and one attempt per entry. Duplicate groups remain visible in the summaries. These results do not establish held-out generalization, model consistency, connectivity preservation, enclosure compliance, or full-deck correctness. Legal references are synthetic component seeds, not recovered pristine originals.

See [C1 evaluation corrections](../C1_EVALUATION_CORRECTIONS.md) for contracts, execution limits, and reproduction commands.
