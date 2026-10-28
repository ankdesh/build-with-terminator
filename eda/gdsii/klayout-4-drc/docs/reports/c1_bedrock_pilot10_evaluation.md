# C1 AWS Bedrock ten-case pilot

Date: 2026-10-27

The ten-case pilot completed using AWS Bedrock in `ap-southeast-2` with
`qwen.qwen3-coder-next`, read from `BEDROCK_MODEL`. Authentication used
`AWS_API_KEY` loaded from the user's shell environment. Ten requests received
ten responses. There were no model service errors and no retries.

## Results

The pilot selected one dirty isolated case and one clean negative control from
each of the five curated rule families. All ten layouts have distinct geometry
hash groups. Each case received one attempt. After the first case passed the
infrastructure and synthesis checks, up to four cases ran at once.

| Rule | Dirty input result | Clean control result |
|---|---|---|
| M1.W.1 | Repaired; 1 marker to 0 | Geometry unchanged |
| M2.W.1 | Invalid script: `Region.min_width` is unavailable | Geometry unchanged |
| M1.A.1 | Invalid script: `Region.each_polygon` is unavailable | Geometry unchanged |
| M1.S.1 | Invalid script: `Edges.MaxLength` is unavailable | Geometry unchanged |
| V1.W.1 | Repaired; 2 markers to 0 | Geometry unchanged |

Geometry repair success was **2/5 dirty cases (40%)**. All **5/5 clean controls**
stayed geometrically unchanged. The three invalid scripts stopped during Python
execution; their post-repair checker results are absent. They are not AWS
connection failures or valid repairs. Clean controls do not contribute repair
credit. Successful results establish compliance only with the curated geometry
checks and preservation constraints, not electrical correctness.

Batch elapsed time was 53.02 seconds. Summed case time was 160.50 seconds.
Recorded usage was 30,734 prompt tokens and 7,750 completion tokens, for 38,484
total tokens. Cost remains unknown because no verified price was supplied.

## Verification and artifacts

All 228 recorded artifact hashes matched. A scan of 265 campaign files found no
copy of the active AWS API key. Request bodies, responses, generated scripts,
sandbox logs, validation records, checker reports, source snapshots, and case
checkpoints remain local under:

`reports/runs/c1_bedrock_pilot10_20261027/`

The directory includes `report.md`, `summary.json`, `summary.csv`,
`campaign.json`, `timing.json`, and `verification.json`.

The earlier `c1_bedrock_agent_20261027` attempt stopped during restricted-session
Bubblewrap preflight and sent no requests. The subsequent proposed 100-case run
was rejected by automatic approval review and did not start. This ten-case pilot
is a separate campaign, requested by the user after that rejection. Candidate
execution retained Bubblewrap isolation in the host environment where its
namespace preflight passed.

## Reproduction and next step

With `AWS_API_KEY` and `BEDROCK_MODEL` in the process environment, run:

```bash
.venv/bin/python scripts/run_c1_bedrock_pilot.py \
  --output reports/runs/<new-pilot-directory>
```

The runner selects Bedrock explicitly and defaults to `ap-southeast-2` unless
`BEDROCK_REGION` is set. An existing completed campaign resumes from checkpoints
without another request. A new output directory starts a separate experiment.

The immediate improvement to evaluate is more explicit, verified KLayout API
guidance for Region iteration, width measurement, and edge filtering. Preserve
this pilot as the original result when changing prompts. A fresh run requires
new campaign provenance. The remaining 90 benchmark entries were not run.

This small development sample cannot estimate performance on the full dataset,
harder geometry, or repeated runs.
