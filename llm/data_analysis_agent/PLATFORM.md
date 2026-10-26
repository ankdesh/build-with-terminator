# Saved Data Analysis Platform

The Linux builder uses chat to create a saved analysis application. The Windows application runs the accepted Python pipeline on replacement CSV files. It has dashboard controls and CSV upload, with no chat or model client.

## Local builder

Use Python 3.12 and install Bubblewrap. User namespaces must be enabled. The runner fails closed when isolation cannot start. It never falls back to in-process execution.

```bash
uv venv --python 3.12
uv pip install -r requirements-runtime.txt
uv pip install -e '.[dev]'
cd frontend
pnpm install --frozen-lockfile
pnpm exec vite build
cd ..
python launcher.py
```

Configure the hosted model through `config.json` and `OPENAI_API_KEY`. The key is loaded only by the builder. The model receives the profile, bounded samples, business descriptions, saved project state, recent chat, and validation errors. It does not automatically receive the complete CSV.

Strict JSON schema output is enabled by default for the official OpenAI endpoint. Set `strict_model_outputs` to `false` in `config.json` for a compatible endpoint or model that supports JSON mode only. Application validation and bounded repair still apply. See the [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

The UI has projects, chat, dashboard preview, and a pipeline inspector. Use **Load example system** to validate a hand-written reference project without a model call. An equivalent CLI is:

```bash
python scripts/create_demo_project.py
```

The example remains a draft. Review its cleanup before accepting it. A generated draft runs on a copy of its input. Source data remains unchanged.

## Project contracts and persistence

`pipeline_core/models.py` defines the version 1 contracts. `ProjectRevision` contains input parsing, named steps, controls, dependencies, seed, and dashboard bindings. The saved revision is authoritative; chat is its development history.

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

During refinement, the model returns bounded JSON Pointer changes. The builder applies them to a copy of the current or failed draft, protects revision identity, and validates the complete result. A title change updates `/dashboard/title` without rewriting Python source.

Acceptance requires a successful run of the current draft against the current CSV with default parameters. Cleanup that changes data or is declared to change analytical meaning requires explicit confirmation. Previously accepted revisions remain available for rollback. New or failed drafts do not change the accepted pointer.

## Execution policy

The active builder routes use separate workers. Legacy question-answering chat routes are retired. Existing session upload and supplied-row CSV export routes remain for compatibility.

Linux workers use Bubblewrap with separate user, process, network, and mount namespaces, no capabilities, no inherited model credentials, read-only runtime code and input, and a dedicated output mount. This requires a working Linux namespace policy; a container or restricted development tool sandbox can prevent it.

Windows workers run trusted code from accepted application exports. Job Objects apply memory and process limits and kill workers when their job closes. They are not a full security sandbox for hostile application packages. Only run exports from a trusted author.

The default deadline is 120 seconds, with a 4 GiB worker memory limit. Cancellation stops the worker process. One pipeline operation runs at a time. Failed input validation or execution retains the last successful dashboard and identifies its dataset and revision.

Workers reject accidental outbound socket calls, and browser policy permits connections and assets only from the local application. These guards supplement the Linux namespace policy; they do not turn trusted Windows application code into an untrusted-code security sandbox.

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

Without this cache, export returns an explicit error. The archive must match the runtime ABI, version, and dependency versions. Export combines it with the accepted revision, inspectable Python source, initial data unless omitted, validation report, instructions, and a complete file inventory. A companion SHA-256 file is kept in the project's export directory. File hashes detect modification; they do not establish who authored a package.

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

Run Linux worker tests where Bubblewrap can create namespaces. Tests verify known cleanup and totals, replacement schema errors, controls, cache invalidation, full table export, forecast backtesting, worker cancellation, host-file isolation, accepted revisions, package integrity, and offline recovery. Model orchestration tests use a mock client and do not establish real-model generation quality.

`python scripts/benchmark_pipeline.py --size-mb 100` tests the declared capacity with a known sum and complete table export. The initial Linux run processed 100 MiB and 1,451,625 rows in about 15 seconds within the worker limits. This is one synthetic workload on the current host, not a production latency guarantee.

The Windows smoke test checks the real frozen launcher and worker with Python removed from the child's PATH and no model credentials. Full Windows release verification also requires a clean Windows VM with external network access blocked, browser interactions, replacement upload, cancellation, and numerical comparison. These checks cannot be completed on a Linux-only host.

Multiple CSVs, scheduled refresh, append history, shared network hosting, arbitrary React generation, general ML training, and offline pipeline editing are outside version 1.
