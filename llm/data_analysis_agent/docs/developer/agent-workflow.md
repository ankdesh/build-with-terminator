# AI chat workflow

The Linux builder owns the workflow. A model selects a job. It cannot apply an edit, publish results, or grant itself a wider edit scope.

## Provider configuration

The checked-in `config.json` selects AWS Bedrock:

```json
{
  "llm_provider": "bedrock",
  "bedrock_region": "us-east-1",
  "bedrock_model_id": "us.anthropic.claude-sonnet-4-6",
  "bedrock_profile": null,
  "llm_timeout_seconds": 180,
  "llm_max_retries": 2,
  "llm_temperature": null
}
```

The client uses `boto3.client("bedrock-runtime")` and the standard AWS credential chain, as in `/home/ankdesh/temp/bedrock_sonnet.py`. Set `bedrock_profile` only to use a named local AWS profile. Keep credentials out of JSON, logs, prompts, and project exports. Structured output needs a recent boto3 version from `uv.lock`.

To select OpenAI or a compatible endpoint, set `llm_provider` to `openai`. Set `openai_api_base`, `openai_model_name`, and the `OPENAI_API_KEY` environment variable. `openai_agent_protocol=json_actions` is the default for compatible endpoints. Set it to `native` for an endpoint that supports strict JSON schemas. A configuration file without `llm_provider` retains the OpenAI default.

All live acceptance tests use Bedrock. OpenAI tests use a mock client. The Windows dashboard runtime has no model dependency or provider configuration.

## Jobs and scope

`agent_prompts.py` holds separate instructions for routing, input definitions, edit plans, visualization, step source, source repair, temporary analysis, and evidence-based answers. `agent_contracts.py` defines their small typed responses. Bedrock receives strict JSON schemas. Compatible text endpoints receive the same contracts in their prompts, with local validation and one response-format repair.

With no selected stage, edit scope is Project. The open page is advisory. A selected stage or category limits edits. The application checks each changed field and requires a reason for necessary linked edits. It asks before an edit expands to Project scope. Reading evidence and temporary analysis can use the project without expanding edit permission.

Saved edits use add/update/remove operations with stable IDs. A separate writer generates each affected Python function. The server checks schema, source, graph, scope, the current complete dataset, and an empty filtered selection when a cleanup table is available. A failed candidate and its diagnostics go back to the repair job. At most two calculation repairs run by default. The proposal remains pending until Apply. Run and acceptance keep their existing explicit controls.

## Temporary calculations

Data questions use the complete selected dataset. They prefer current draft cleaning. If no cleaning exists, the result is labelled raw. Independent cleaning branches require a source choice. A cleaning failure prompts for repair or explicit use of raw data.

Common filters, grouping, aggregation, sorting, selection, correlation and descriptions use deterministic DataFrame operations. Other calculations use a Python function. Both paths run in a Linux bubblewrap worker with no network, no credentials, read-only runtime files, and a private output directory. Install `bubblewrap` and permit user/network namespaces. If isolation is unavailable, the application reports that capability error; it does not run automatic Python in the builder process.

Temporary tables retain full CSV output. The chat shows at most 100 rows and 20 columns. Charts use the existing JSON-only ECharts renderer. Provenance records the input hash, source, workspace version, calculation hash, parameters, project-rule version, and installed runtime package versions. Reuse requires matching input, calculation, source, parameters, rules, and runtime code/package hashes; cached files must pass integrity checks. Temporary work does not replace a saved dashboard run.

## Clarification and recovery

A request can pause on an inline question card. Choices and free text resume the original request. Only an explicit checkbox saves a business answer as a project rule. The rules editor supports add, update, delete and review after input-schema changes.

Request IDs make submissions idempotent. SQLite stores request state, answers, model usage, numbered events and artifacts. A second request cannot overlap an active request for the same project. Disconnecting a listener does not cancel work. Reload reads the active request from the project view. Event replay is available at `/chat/turns/{id}/events?after=N`. Explicit Cancel stops the workflow and its worker. Startup marks unfinished computation as interrupted; unanswered question cards remain resumable. Changed data or workspace versions require a fresh context before resume.

Context is limited to 128,000 serialized characters. The planner receives focused source; each affected step writer receives its complete source, direct producer source, parameter specs, and widget bindings. Metadata is applied before source generation so later widget/control operations are visible to the writer.

Default limits are 12 model steps, 600 active-work seconds, 120 execution seconds and 4096 MB worker address space. Configuration keys use the `agent_` prefix in `config.py`. Temporary files expire after seven days or the 500 MB project budget. `DELETE /analysis` clears unpinned files. Result metadata remains available after expiry.

## Validation

Run local regression tests outside a restrictive namespace sandbox, because tests exercise asyncio threads and bubblewrap:

```sh
uv run --extra dev pytest -q
uv run --extra dev mypy backend pipeline_core config.py
pnpm --dir frontend exec tsc --noEmit
pnpm --dir frontend build
```

Run the disposable live suite with the configured AWS account:

```sh
.venv/bin/python -m scripts.evaluate_agent --repeats 3 --output /tmp/wps-agent-evaluation.json
```

The suite covers 40 requests per repeat, including a new project built from scratch. Requests run one at a time by default to respect the shared AWS quota. Use --concurrency only when account limits allow it. It checks numerical artifacts, source selection, routing, ambiguity, stage scope, execution-validated edits, and preservation of workspace and saved results. `--case NAME` selects a case for diagnosis. Reports contain per-job latency, provider request IDs and token usage. Never treat a correct-looking model sentence as a numerical test result.

The browser smoke test starts and removes its own disposable builder project:

```sh
.venv/bin/python -m scripts.agent_browser_smoke
```

Install the matching Playwright Chromium browser first, or pass --browser-executable with an installed Chromium path. It checks clarification/resume, temporary output, reload, project rules, and cancellation. Screenshots and logs go to TEMP_agent_validation/browser by default.
