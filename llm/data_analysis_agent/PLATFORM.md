# Saved Data Analysis Platform

The Linux builder uses chat and visual design tools to create a saved analysis application. Each opened project has a dashboard service on its own loopback port. The Windows application runs the accepted Python pipeline on replacement CSV files. It has dashboard controls and CSV upload, with no chat or model client.

See the [developer handbook](docs/developer/README.md) for component documents, architecture diagrams, dependency tables, supported analyses/visualizations, and an extracted API reference. The [HTML view](docs/developer/index.html) uses local assets.

## Local builder

Use Python 3.12. Workers launch Python directly; no sandbox package or Linux namespace setup is required. Calculations remain outside the API process.

```bash
uv venv --python 3.12
uv pip install -r requirements-runtime.txt
uv pip install -e '.[dev]'
cd frontend
pnpm install --frozen-lockfile
pnpm exec vite build
pnpm exec vite build --mode runtime
cd ..
python launcher.py
```

Configure the hosted model through `config.json` and `OPENAI_API_KEY`. The key is loaded only by the builder. The model receives the profile, bounded samples, business descriptions, saved project state, recent chat, validation errors, and bounded project run diagnostics. It does not automatically receive the complete CSV.

`backend/services/llm_gateway.py` is the only model entry point. Both agent services use its shared lazy client. Endpoint, model, timeout, transport retries, and temperature come from `config.json`; credentials come only from `OPENAI_API_KEY`. Malformed config files fail at startup. The gateway closes its client on builder shutdown.

Set `llm_temperature` to `null` to use a model's default sampling settings. The gateway can also retry one explicit HTTP 400 temperature rejection without that optional field, while preserving the selected model. Other provider errors retain sanitized message, parameter, and code details. Reload settings and code by restarting the builder.

`python launcher.py --csv /path/to/input.csv` creates a new project from a bounded CSV snapshot and selects its Data view. `--headless` prints that project's URL. Startup and API uploads share profiling, input persistence, and workspace invalidation. Import does not call the model or run a pipeline.

Authoring uses plain chat completions without `response_format`. Endpoints do not need JSON mode or strict schema support. JSON text, including a complete fenced JSON block, is parsed and validated locally; bounded proposal repair remains active. The old `strict_model_outputs` option is ignored. Chat receives project-scoped recent run diagnostics and small input previews so it can repair execution failures on request. Repairs save a draft; the developer selects Run to execute it.

The UI has a project switcher, Data, Pipeline, Dashboard, History, and a Chat/Properties dock. Use **Load energy example** to load a reference workspace without a model call, then select Run. The CLI below creates and validates the reference project explicitly:

```bash
python scripts/create_demo_project.py
```

The example remains a draft. Review its cleanup before accepting it. A generated draft runs on a copy of its input. Source data remains unchanged.

## Project contracts and persistence

`pipeline_core/models.py` defines revision contracts for versions 1 and 2. New revisions use version 2. Existing version 1 JSON remains immutable; missing presentation fields receive compatible defaults. `ProjectRevision` contains input parsing, named steps, controls, dependencies, seed, and dashboard bindings. The editable workspace is the development source of truth. Runs compile it into immutable executable revisions; acceptance identifies the exact version approved for download. Chat is development history.

Each function has three arguments:

```python
def calculate(inputs, parameters, context):
    df = inputs['cleaned']
    return {'total': float(df['amount'].sum()) * parameters['multiplier']}
```

Inputs refer to declared artifact names. The return mapping must contain exactly the declared output names. Cleanup precedes analysis. Filters operate on a named source or cleanup artifact before analysis. A table returns a DataFrame, a metric returns a scalar, a text widget returns computed text, and a chart returns `{'option': {...}}` in Apache ECharts JSON format. External chart assets and links are rejected. The frontend uses rich-text tooltips and never evaluates generated JavaScript.

Standard bar, line, scatter, and pie charts can also bind to a DataFrame using `chart_binding` with explicit `x` and `y` columns. One frame can serve both chart and table widgets; each widget has its own rendered view. Text widgets can display a computed scalar, such as the current row count. Complex charts can return native ECharts option trees from Python.

SQLite holds project pointers, messages, revision metadata, and run records. Files hold immutable CSV inputs and revision JSON plus run outputs. Set `WPS_PROJECTS_DIR` to override the default `data/projects` directory.

Checkpoints include code, input hashes, all parameter values, seed, runtime version, and output checksums. Presentation-only changes reuse matching outputs. Changing a calculation invalidates its checkpoint and any downstream artifact whose content changes. Cache tables use typed JSON, not pickle. Full CSV output is saved separately from the 500-row display preview.

During refinement, the model returns bounded JSON Pointer changes. Proposals are checked against the current workspace version and saved without executing calculations. Select Run to validate data-dependent behavior. The builder applies them to a copy of the current or failed draft, protects revision identity, and validates the complete result. A title change updates `/dashboard/title` without rewriting Python source.

Acceptance requires a successful run of the current draft against the current CSV with default parameters. Cleanup that changes data or is declared to change analytical meaning requires explicit confirmation. Previously accepted revisions remain available for rollback. New or failed drafts do not change the accepted pointer.

## Builder and target services

The builder listens on its configured port (8080 by default). A Target Manager starts a separate credential-free process for each opened project on ports 8100–8199. `WPS_TARGET_PORT_START` and `WPS_TARGET_PORT_END` configure the range. Preferred ports are stored in SQLite. The manager reserves and passes the listening socket to the child to avoid port-selection races.

Targets use the shared `pipeline_core.runtime` state machine and HTTP API. The live execution adapter calls an authenticated builder execution broker. The offline adapter uses the packaged ProcessRunner. Runtime processes do not import builder services, model clients, or model configuration. Control credentials use a parent-owned pipe; browser calls stay on their own origin. Live preview needs no Windows runtime ZIP.

Targets stop through the builder lifespan handler. A parent-pipe watcher also stops them after a builder crash. Server shutdown has a bounded grace period so an open event stream cannot keep a target running indefinitely.

Workspace edits, applied target state, and accepted revisions are separate. Presentation edits use complete immutable artifacts and record `validation_mode=presentation` plus `source_run_id`. The cache signature tracks calculation inputs, code, parameters, seed, and runtime versions. Layout edits do not execute generated Python. Incomplete workspaces can be saved, deleted from, and restored with Undo; Run and acceptance require a complete valid graph.

The canvas derives four fixed types from source, cleanup steps, analysis steps, and widgets. The engine keeps cleanup and analysis as executable step types. Stage creation and logic changes use chat; the UI has no code editor. The dashboard supports desktop use with one 12-column grid shared by the designer, live target, and exported application. Tablet and phone layouts, device previews, mobile navigation, and the mobile filter drawer are removed. Widget positions remain the same when the window resizes. The grid expands with available desktop space; narrow windows and browser zoom use scrolling. Minimum widths are 1100 CSS pixels for the builder, 1000 for the target shell, and 900 for the dashboard content. Keyboard editing, form controls, and reduced-motion support remain.

The Properties dock is scoped to the selected card. It shows input context, step properties, or widget display and geometry fields. Step controls are limited to the step's declared `parameters_used`; unrelated controls are omitted. Project renaming is available from the top-bar project name. Dashboard title and subtitle are in the Dashboard settings section, and all control labels, defaults, and ranges are in Filters and scenario defaults in the Dashboard view. Data owns the CSV, input contract, and business context. These edits use the existing versioned workspace save and Undo/Redo paths.

New APIs under `/api/projects/{id}` include `GET/PATCH /workspace`, stage deletion preview/commit, `POST /run`, job status/cancellation, target start/stop/restart/status, and persistent `/events`. Workspace writes require `expected_version` and return HTTP 409 on conflicts. Run jobs capture a workspace version and immutable dataset path. Browser disconnects do not cancel these jobs. Existing revision run routes remain as compatibility streams.

Both interfaces use persistent server-sent events for updates. Runtime events have a sequence and process instance ID so reconnects after a restart can accept a fresh snapshot. Targets retain the last successful result during failure or reconnect. A target replacement CSV is stored separately from the builder CSV; successful developer revisions are checked against the target's current input and controls before replacing its applied state.

The runtime release is 0.3.1 with ABI 2. Rebuild the Windows runtime cache for this release to include direct worker execution and removal of network guards. Older cached runtimes are rejected; previously exported applications keep their own bundled runtime. `python build.py` builds and packages both frontend entry points for the Linux builder.

## Execution policy

The active builder routes use separate workers. Legacy question-answering chat routes are retired. Existing session upload and supplied-row CSV export routes remain for compatibility.

Linux workers launch `python -m pipeline_core.worker` directly in their run directory. There is no code sandbox, namespace isolation, seccomp filter, or worker network guard. Code has normal file and network access under the service account. Workers receive a reduced environment without model credentials. A parent monitor stops the worker process group if its service exits. Syntax, step signatures, dependency graphs, output contracts, and reproducibility checks remain; import and built-in allowlists are removed.

Windows workers run trusted code from accepted application exports. Job Objects apply memory and process limits and kill workers when their job closes. They are not a full security sandbox for hostile application packages. Only run exports from a trusted author.

The default deadline is 120 seconds, with a 4 GiB worker memory limit. Cancellation stops the worker process. One pipeline worker runs at a time across the builder and its live targets. Run requests queue for this shared execution slot; cancellation also works while queued. Failed input validation or execution retains the last successful dashboard and identifies its dataset and revision.

Browser policy permits connections and assets only from the local application. This browser policy is separate from calculation execution and does not restrict worker network access.

The supported numerical libraries are pandas, NumPy, SciPy, and statsmodels. Install the pinned runtime release in both environments. Additional libraries require a runtime release; runtime package installation is not supported. The forecast helper validates equally spaced datetime input, evaluates a chronological holdout against a naive baseline, refits on the current dataset, and reports intervals only when the saved method provides them.

Chart series and datasets are limited to 5000 items; use explicit aggregation or sampling for larger inputs. Full tables are not truncated in CSV exports.

Saved steps must use explicit date parameters or dates from their input, not the system clock. Random generators need an explicit seed. Package compatibility checks include the Python major and minor version.

## Windows release and export

Windows 11 x64 is the initial target. Build the runtime on Windows with Python 3.12, Node.js, and pnpm. Those tools are build requirements, not deployment requirements.

```powershell
python -m pip install -r requirements-runtime.txt
python -m pip install -e '.[dev,packaging]'
cd frontend
pnpm install --frozen-lockfile
cd ..
python scripts/build_windows_runtime.py
python scripts/windows_smoke.py
```

The GitHub workflow `.github/workflows/windows-runtime.yml` performs these checks and uploads `windows-x64.zip`. It must pass on Windows before the release is considered verified. This repository does not contain a fabricated Windows executable.

In this monorepo, the registered workflow is `../../.github/workflows/wps-analysis-windows.yml`; it sets the project working directory and artifact paths. The project-local workflow is the standalone repository template.

Copy the verified runtime ZIP to the Linux builder and configure:

```bash
export WPS_WINDOWS_RUNTIME=/absolute/path/windows-x64.zip
```

Without this cache, export returns an explicit error. The archive must match the runtime ABI, version, and dependency versions. Export combines it with the accepted revision, inspectable Python source, its accepted CSV unless omitted, validation report, instructions, and a complete file inventory. New acceptances pin the validation run and dataset so later input replacement cannot change an accepted download. A companion SHA-256 file is kept in the project's export directory. File hashes detect modification; they do not establish who authored a package.

Extract the exported ZIP on Windows and run `WPSAnalysis.exe`. The launcher verifies the package, starts a server bound to `127.0.0.1`, and opens the dashboard. The target needs no Python, Node.js, model credentials, or external services. Runtime state is stored under `%LOCALAPPDATA%/WPSAnalysis/<revision_id>` outside the immutable package.

`--headless`, `--port`, `--state-dir`, and `--verify` are supported. Updating logic requires a new builder export. The offline API exposes state, upload, run, cancellation, and complete table export; it does not expose project editing or chat.

## Validation and release limits

```bash
pytest tests/ -q
cd frontend
pnpm exec tsc --noEmit
pnpm exec vite build
pnpm exec vite build --mode runtime
```

Run `python scripts/studio_smoke.py` for the real multi-process local workflow. Tests verify known cleanup and totals, replacement schema errors, controls, cache reuse, full table export, forecast backtesting, direct worker startup, file and local network access, worker cancellation, credential exclusion, accepted revisions, package integrity, and offline recovery. Model orchestration tests use a mock client and do not establish real-model generation quality.

`python scripts/benchmark_pipeline.py --size-mb 100` tests the declared capacity with a known sum and complete table export. The initial Linux run processed 100 MiB and 1,451,625 rows in about 15 seconds within the worker limits. This is one synthetic workload on the current host, not a production latency guarantee.

The Windows smoke test checks the real frozen launcher and worker with Python removed from the child's PATH and no model credentials. Full Windows release verification also requires a clean Windows VM with external network access blocked, browser interactions, replacement upload, cancellation, and numerical comparison. These checks cannot be completed on a Linux-only host.

Multiple CSVs, scheduled refresh, append history, shared network hosting, arbitrary React generation, general ML training, and offline pipeline editing are outside version 1.
