# API contracts

The builder and target expose different interfaces. Browser calls stay on the service's own origin. Builder OpenAPI is available through FastAPI's normal docs when enabled; the runtime disables OpenAPI/docs routes. The inventory below is extracted from route decorators without starting the application.

## Builder request examples

Use `Content-Type: application/json` for JSON bodies. Dataset upload uses multipart field `csv_file` and optional `description`.

```json
{"expected_version": 4, "parameters": {}}
```

Send this to `POST /api/projects/{project_id}/run`. It returns HTTP 202 with a job record. Poll the job or listen for project events, then fetch fresh state. It does not keep a browser stream open for the full execution.

```json
{"expected_version": 4, "action": "edit", "document": {"title": "...", "input_enabled": true}}
```

This workspace example is schematic. For an actual edit, load GET workspace and send its complete document with your supported changes; do not replace an existing graph with this short example. PATCH also accepts `action=undo` or `action=redo`. A stale version returns HTTP 409.

```json
{"expected_version": 5, "confirmed": false}
```

Send this to the stage deletion route for impact review. IDs have `input:`, `step:`, or `widget:` prefixes. Submit the reviewed request with `confirmed=true` and the expected version to commit one undoable deletion.

```json
{"run_id": "successful-run-id", "cleanup_confirmed": true}
```

Acceptance validates the current input/draft/defaults and cleanup confirmation. Export selects an accepted revision, with optional `include_data=false` or an earlier accepted `revision_id` query value.

## Runtime requests

`POST /api/runtime/run` accepts `{"parameters": {...}}`. It runs the saved desired revision against the current input and returns run/state. `POST /api/runtime/upload` uploads and runs a candidate CSV with defaults. `POST /api/runtime/cancel` requests cancellation. A second dashboard operation while the runtime lock is held returns HTTP 409. Input/parameter errors normally return HTTP 422.

`GET /api/runtime/state` is the source of truth for applied revision, display run, current input mode, pending state, active run, last error, controls notice, sequence, and process instance. `GET /api/runtime/events` sends notifications; it does not run calculations. Table export only exposes outputs used by table widgets in the applied revision.

## Internal server communication

TargetManager sends authenticated snapshots to `POST /internal/snapshot` on the live target. BrokerRunner sends authenticated execution requests to the builder under `/api/internal/targets/{project_id}`. These routes use `X-Target-Token`; the browser must not receive or supply that token. The execute response is newline-delimited JSON, not browser SSE.

Live control routes are only installed when a control token exists. Offline Use builder data is not usable because an offline app has no builder input. Target runtimes do not expose project editing or chat.

## Compatibility interfaces

`POST /api/projects/{project_id}/revisions/{revision_id}/run` is an older streaming run adapter. Prefer version-bound workspace jobs for new UI work. Session routes and supplied-row table CSV export remain for compatibility. The old question-answering chat executor is not mounted as the active authoring path. A function's presence in `chat_routes.py` is not proof that it is a mounted route.

## Extracted endpoint inventory

<!-- API_TABLES -->

### Builder application

| Method | Path | Handler/source |
| --- | --- | --- |
| GET | `/api/capabilities` | [capabilities](../../backend/app.py) · line 113 |
| GET | `/health` | [health_check](../../backend/app.py) · line 118 |

### Builder project API

| Method | Path | Handler/source |
| --- | --- | --- |
| GET | `/api/projects` | [list_projects](../../backend/routes/project_routes.py) · line 121 |
| POST | `/api/projects` | [create_project](../../backend/routes/project_routes.py) · line 126 |
| POST | `/api/projects/examples/energy` | [energy_example](../../backend/routes/project_routes.py) · line 131 |
| GET | `/api/projects/{project_id}` | [get_project](../../backend/routes/project_routes.py) · line 137 |
| POST | `/api/projects/{project_id}/accept` | [accept_revision](../../backend/routes/project_routes.py) · line 291 |
| POST | `/api/projects/{project_id}/chat` | [build_project](../../backend/routes/project_routes.py) · line 161 |
| GET | `/api/projects/{project_id}/chat/items/{item_id}` | [chat_item](../../backend/routes/project_routes.py) · line 172 |
| POST | `/api/projects/{project_id}/chat/items/{item_id}/apply` | [apply_chat_item](../../backend/routes/project_routes.py) · line 177 |
| POST | `/api/projects/{project_id}/chat/items/{item_id}/discard` | [discard_chat_item](../../backend/routes/project_routes.py) · line 185 |
| POST | `/api/projects/{project_id}/chat/items/{item_id}/run` | [run_and_reask](../../backend/routes/project_routes.py) · line 192 |
| PATCH | `/api/projects/{project_id}/context` | [describe_project](../../backend/routes/project_routes.py) · line 352 |
| POST | `/api/projects/{project_id}/dataset` | [upload_dataset](../../backend/routes/project_routes.py) · line 142 |
| GET | `/api/projects/{project_id}/events` | [project_events](../../backend/routes/project_routes.py) · line 383 |
| GET | `/api/projects/{project_id}/export` | [export_project](../../backend/routes/project_routes.py) · line 316 |
| GET | `/api/projects/{project_id}/jobs` | [list_jobs](../../backend/routes/project_routes.py) · line 368 |
| GET | `/api/projects/{project_id}/jobs/{job_id}` | [get_job](../../backend/routes/project_routes.py) · line 373 |
| POST | `/api/projects/{project_id}/jobs/{job_id}/cancel` | [cancel_job](../../backend/routes/project_routes.py) · line 378 |
| POST | `/api/projects/{project_id}/revisions/{revision_id}/rollback` | [rollback_revision](../../backend/routes/project_routes.py) · line 298 |
| POST | `/api/projects/{project_id}/revisions/{revision_id}/run` | [run_revision](../../backend/routes/project_routes.py) · line 271 |
| POST | `/api/projects/{project_id}/run` | [run_workspace](../../backend/routes/project_routes.py) · line 363 |
| POST | `/api/projects/{project_id}/runs/{run_id}/cancel` | [cancel_run](../../backend/routes/project_routes.py) · line 282 |
| GET | `/api/projects/{project_id}/runs/{run_id}/tables/{output_name}` | [export_table](../../backend/routes/project_routes.py) · line 306 |
| POST | `/api/projects/{project_id}/stages/{stage_id}/delete` | [delete_stage](../../backend/routes/project_routes.py) · line 342 |
| GET | `/api/projects/{project_id}/stages/{stage_id}/inspect` | [inspect_stage](../../backend/routes/project_routes.py) · line 242 |
| GET | `/api/projects/{project_id}/stages/{stage_id}/inspect.json` | [download_inspection](../../backend/routes/project_routes.py) · line 265 |
| GET | `/api/projects/{project_id}/target` | [target_status](../../backend/routes/project_routes.py) · line 402 |
| POST | `/api/projects/{project_id}/target/{action}` | [target_control](../../backend/routes/project_routes.py) · line 416 |
| GET | `/api/projects/{project_id}/workspace` | [get_workspace](../../backend/routes/project_routes.py) · line 326 |
| PATCH | `/api/projects/{project_id}/workspace` | [edit_workspace](../../backend/routes/project_routes.py) · line 331 |

### Compatibility data export

| Method | Path | Handler/source |
| --- | --- | --- |
| POST | `/api/sessions/{session_id}/export-csv` | [export_table_csv](../../backend/app.py) · line 72 |

### Compatibility session API

| Method | Path | Handler/source |
| --- | --- | --- |
| GET | `/api/sessions` | [list_sessions](../../backend/routes/session_routes.py) · line 40 |
| POST | `/api/sessions` | [create_session](../../backend/routes/session_routes.py) · line 33 |
| DELETE | `/api/sessions/{session_id}` | [delete_session](../../backend/routes/session_routes.py) · line 67 |
| GET | `/api/sessions/{session_id}` | [get_session_detail](../../backend/routes/session_routes.py) · line 46 |
| POST | `/api/sessions/{session_id}/upload` | [upload_dataset](../../backend/routes/session_routes.py) · line 76 |

### Internal target broker

| Method | Path | Handler/source |
| --- | --- | --- |
| POST | `/api/internal/targets/{project_id}/cancel/{run_id}` | [cancel_target](../../backend/routes/project_routes.py) · line 487 |
| POST | `/api/internal/targets/{project_id}/execute` | [execute_target](../../backend/routes/project_routes.py) · line 428 |

### Shared runtime API

| Method | Path | Handler/source |
| --- | --- | --- |
| GET | `/` | [dashboard](../../pipeline_core/runtime_http.py) · line 148 |
| POST | `/api/runtime/cancel` | [cancel](../../pipeline_core/runtime_http.py) · line 122 |
| GET | `/api/runtime/events` | [events](../../pipeline_core/runtime_http.py) · line 60 |
| POST | `/api/runtime/run` | [run](../../pipeline_core/runtime_http.py) · line 81 |
| GET | `/api/runtime/state` | [state](../../pipeline_core/runtime_http.py) · line 56 |
| GET | `/api/runtime/tables/{output_name}` | [table](../../pipeline_core/runtime_http.py) · line 128 |
| POST | `/api/runtime/upload` | [upload](../../pipeline_core/runtime_http.py) · line 91 |
| POST | `/api/runtime/use-builder-data` | [use_builder_data](../../pipeline_core/runtime_http.py) · line 111 |
| GET | `/health` | [health](../../pipeline_core/runtime_http.py) · line 52 |
| POST | `/internal/snapshot` | [snapshot](../../pipeline_core/runtime_http.py) · line 138 |

<!-- END_API_TABLES -->

Routes in the generated inventory are grouped by owner. Runtime nested route definitions are extracted statically; conditional live-only installation is stated in the notes above. Refer to the route's linked source for exact response payloads, query arguments, and error details.
