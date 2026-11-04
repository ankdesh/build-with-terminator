# Authoring and LLM access

## Authoring path

![Chat proposal, bounded repair, and versioned save](diagrams/authoring.svg)

| Component | Input | Output | Depends on |
| --- | --- | --- | --- |
| [LLMGateway](../../backend/services/llm_gateway.py) | Ordinary chat messages | Model response text or service error | AppConfig, OpenAI-compatible SDK client |
| [ProjectAgent](../../backend/services/project_agent.py) | Current/failed revision, profile, descriptions, request, recent messages, run diagnostics | Checked ProjectRevision | Gateway, models, source/graph validation |
| [ProjectService](../../backend/services/project_service.py) | Project ID and design request | Saved workspace/revision and chat/status events | Agent, store, Workspaces |
| [Workspaces](../../backend/services/workspace_service.py) | Proposed document and expected version | New editable version; optional presentation validation | Store, workspace/model contracts, saved-artifact renderer |

Chat saves a design without executing calculations. Syntax and contract checks run during proposal handling. Data-dependent failures appear after Run and require a repair request. The tutorial validator sends such repair requests explicitly; ordinary chat does not automatically run a calculation-repair loop.

## One model entry point

All application model calls use `backend/services/llm_gateway.py`. The legacy agent also uses this gateway. Do not create an SDK client in routes, runtime code, or a new feature module.

| Configuration | Source | Meaning |
| --- | --- | --- |
| `openai_api_base` | config.json | Endpoint base URL |
| `openai_model_name` | config.json | Model name |
| `llm_timeout_seconds` | config.json | Model request timeout |
| `llm_max_retries` | config.json | SDK/transport retry count |
| `llm_temperature` | config.json | Number from 0 to 2, or null to omit temperature and use the model default |
| `max_retries` | config.json | Proposal repair limit; distinct from transport retries |
| `OPENAI_API_KEY` | Environment only | Credential; file-config API keys are ignored |

The gateway creates its client lazily and closes it during builder shutdown. Missing credentials block new model requests, while saved dashboards and CSV import can still work. Malformed configuration fails at startup. See [config.py](../../config.py) for defaults and input validation.

### Model sampling compatibility

Use `llm_temperature=null` for models that require default sampling, including GPT-6 Luna with default reasoning. A rejected value of 0.1 produced HTTP 400 with `param=temperature` and `code=unsupported_value` during a live check. Temperature can be omitted without changing the selected model.

The gateway retries once without temperature only when HTTP 400 explicitly identifies that field with `unsupported_parameter` or `unsupported_value`. It remembers that restriction for its current client. It does not change the model. Other errors expose bounded provider message/parameter/code details with credential redaction, instead of hiding every cause behind a generic configuration message. A null setting avoids the compatibility retry entirely. Restart the builder to load changed settings or Python code.

## What the model sees

The authoring context includes the profile, bounded samples, business context, current workspace/revision, contract schema, recent conversation, relevant validation errors, and bounded run diagnostics. It does not automatically include every source CSV row. Treat any sample sent to the configured endpoint as model input; keeping the full CSV local does not mean no data is sent.

New projects request a complete revision. Refinements request bounded JSON Pointer patches. Arrays use numeric indices, such as `/steps/0/code`; `/-` appends an item. An object ID is not an array index. Identity fields and schema version cannot be patched through editable paths.

Authoring calls omit `response_format`. No provider-side JSON mode or strict schema support is required. Prompts request JSON text, which [model_output.py](../../backend/services/model_output.py) parses locally. A complete fenced JSON block is also accepted. Full revisions still have to satisfy the application contract. Malformed text or invalid proposals use the bounded repair path.

Patch changes use native JSON `value` fields. The decoder retains compatibility with older `value_json` responses. The removed `strict_model_outputs` configuration key has no effect.

## Requested execution repairs

[run_diagnostics.py](../../backend/services/run_diagnostics.py) collects evidence before each chat proposal. It includes up to three runs from the current project, prioritizing run IDs named in the request, then recent failures. Builder records come from SQLite; target records come from the project's target run directory. It never looks up another project's run.

Evidence includes run/revision/input identity, parameters, error, traceback, captured stdout/stderr, worker log tail, recent step events, and at most three raw input rows across twenty columns. The added context is bounded to 20,000 serialized characters, with individual log limits and credential redaction. Full result artifacts are excluded. Old small worker responses remain readable when no separate diagnostic file exists. These samples and logs are sent to the configured model endpoint along with the authoring context.

Example: **Fix the latest failed run using its logs. The supplier renamed amount to value; both use the same units. Save only; I will select Run.** Chat can update input parsing, cleanup, and calculation code together. For numeric strings such as `1,200`, a valid repair may read strings first and explicitly parse thousands separators in cleanup. If a required column is absent and cannot be derived, the agent must explain what data or mapping is needed. It must not invent observations or discard rows to hide an error.

Logs, CSV values, and tracebacks are evidence, not instructions. A repair creates a draft through the usual source checks and expected-version save. It does not execute generated Python. Select Run to validate the repair; failed runs retain the previous successful display. A target repair still needs a successful builder Run before the target can apply it to its separate input.

## Validation and repair boundaries

The agent assigns server-owned revision identity and parentage, then validates the full result. Checks include syntax, function shape, unique IDs and output names, graph completeness, valid parameters, and widget output references. A failed proposal can be supplied back to the model as the repair base; repair must edit existing items rather than append duplicate IDs.

The service serializes authoring per project. It captures the workspace version before model work and saves with that expected version. A concurrent edit returns a workspace conflict rather than silently overwriting newer work. Such conflicts are not an instruction to ask the model for a different proposal.

Model connection/refusal failures do not become code repair attempts. Generated data logic can still be wrong after schema validation. Run known inputs and independent numerical checks before accepting a revision.
