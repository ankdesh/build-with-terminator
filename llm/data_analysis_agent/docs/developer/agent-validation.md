# Agent refactor validation

Date: 2026-11-16. Live provider: AWS Bedrock, `us.anthropic.claude-sonnet-4-6`, `us-east-1`.

## Result

The local regression suite, backend type checks, frontend type checks, frontend build, and browser smoke test pass. All issues found in the live acceptance matrix have passing focused retests. The complete matrix was not rerun after the last fixes; the reports retain the initial failures and the subsequent retests.

| Check | Result |
| --- | --- |
| Local pytest suite | 390 passed |
| mypy, backend / pipeline core / config | Pass, 64 source files |
| Frontend TypeScript | Pass |
| Frontend production build | Pass; Vite reports its existing large-chunk advisory |
| Browser: clarify, resume, temporary chart/table, reload | Pass |
| Browser: project-rule add, persistence, delete | Pass |
| Browser: explicit cancellation | Pass |
| Browser console errors | None |

## Live acceptance and corrections

The suite uses disposable project stores and an independently known CSV. It checks calculated artifacts, saved-state preservation, routing, ambiguity, scope, execution validation, and a complete new project. It does not use model prose as a numerical oracle. No user project is changed. All live AI calls use Bedrock; OpenAI compatibility tests use mock clients.

The last complete matrix ran 40 scenarios three times. It passed **109 of 120** on the code before the final corrections. The eleven failures fall into three groups:

| Finding | Initial failures | Change | Focused retest |
| --- | ---: | --- | ---: |
| Stage rename echoes source in metadata | 3 | Remove source from planner metadata schemas; accept only an exact unchanged-source echo | 5/5 pass |
| New project input access and empty numeric chart tables | 2 | Give writers complete graph/bindings, specify named inputs and preserve numeric types for empty chart tables | 3/3 pass |
| AWS account throttling during concurrent test runs | 6 | Run acceptance requests serially by default; retain typed provider errors | 6/6 pass |

Earlier diagnostic runs also found and corrected an incorrect needs-run route for a data question, invalid source names, artificial row limits, an ignored null predicate inside an aggregate, and missing entity schemas. The missing-row calculation passed five repeated retests. An ambiguous test request was changed to name the `value` column; the agent's clarification for the original wording was valid.

The Windows runtime source, ABI, release version, and export contract stay unchanged. New project creation passed both complete-data and empty-selection checks under that contract. The generated project was executed again to verify that its total was 30.

## Reports and reproduction

Reports and browser screenshots from this session are in the ignored `TEMP_agent_validation/` directory:

- `reports/matrix.json`: the 120-request matrix, including its failures.
- `reports/rename.json`: five stage-rename retests.
- `reports/creation.json`: three new-project retests under the unchanged runtime.
- `reports/quota.json`: six serial retries of requests that were throttled.
- `reports/missing.json`: five missing-value calculation retests.
- `browser/result.json`, `browser/clarification.png`, `browser/result.png`: browser checks.

Run the live matrix again with:

```sh
.venv/bin/python -m scripts.evaluate_agent --repeats 3 --concurrency 1 --output /tmp/agent-evaluation.json
```

Run the browser checks with:

```sh
.venv/bin/python -m scripts.agent_browser_smoke
```

See [AI chat workflow](agent-workflow.md) for setup, configuration, limits and execution details. A passing finite suite does not guarantee that every new analytical request will succeed. The application retains bounded repair, clarification, explicit Apply, and clear provider failures for those cases.
