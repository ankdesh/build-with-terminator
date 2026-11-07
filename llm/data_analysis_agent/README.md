# WPS-AI Data Analysis Studio

Design a reusable analysis application through chat on Linux. Review its stages, arrange its dashboard, and select Run to apply calculations. Use the resulting dashboard on its own local port. Accept a validated revision and export it for Windows with no chat, LLM, or internet dependency.

The application supports one replacement CSV up to 100 MB, generated pandas and NumPy code, SciPy and statsmodels calculations, forecasts, linked filters, and what-if controls. It preserves the last successful dashboard when a refresh fails.

See [PLATFORM.md](PLATFORM.md) for contracts, execution policy, packaging, and release checks. The system design document is in [artifacts/data-analysis-system-design.docx](artifacts/data-analysis-system-design.docx).

## Developer documentation

Open the [developer handbook](docs/developer/index.html) or its [Markdown index](docs/developer/README.md). It includes component architecture, eight diagrams with editable sources, dependencies, data/state contracts, API routes, analysis and chart support, and build/extension guidance. Run `python scripts/build_developer_docs.py` to refresh the local HTML, diagrams, API inventory, and package tables. Graphviz is required only for documentation generation.

## Start the Linux builder

Python 3.12, Node.js, and pnpm are required. No system sandbox packages or Linux namespace permissions are required.

```bash
uv venv --python 3.12
uv pip install -r requirements-runtime.txt
uv pip install -e '.[dev]'
python launcher.py
```

The launcher prepares both frontend bundles before starting the server. On the first launch, or after dependency changes, it runs `pnpm install --frozen-lockfile`. Missing, altered, or outdated UI files trigger the builder and runtime Vite builds. Source and output hashes let unchanged bundles start without rebuilding. Node.js and pnpm must be available on PATH when a rebuild is needed. A failed install or build stops startup with an error instead of serving old files.

To update a checkout, stop the builder, run `git pull`, then launch again. The launcher does not update Git automatically. Python changes take effect after restart. No separate manual frontend build is needed.

Use the existing `config.json` for the model endpoint and model name. Supply credentials through `OPENAI_API_KEY`. The model receives bounded data context while the full CSV stays local.

To load a CSV at startup, use:

```bash
python launcher.py --csv "/path/to/data.csv"
# Start without opening a browser:
python launcher.py --headless --csv "/path/to/data.csv"
```

This creates a new project, copies and profiles the CSV, and opens its Data view. In headless mode, use the Builder URL printed in the terminal. Each launch with `--csv` creates a new project. The same size and data checks apply to command-line input and UI uploads. No model call or calculation runs during import.

### Access from other machines

The checked-in `config.json` binds the builder and live project dashboards to `0.0.0.0` (all IPv4 interfaces). Start the host with:

```bash
python launcher.py --headless --host 0.0.0.0 --port 8080
```

On another machine, open `http://<server-IP>:8080`. Use the hosting machine's IP address or DNS name, not `0.0.0.0`, `localhost`, or `127.0.0.1`. Dashboard links use that same host with each project's target port. Allow inbound TCP 8080 and 8100–8199 through the host firewall; use your configured builder port if it differs. The builder uses exactly `server_port` (or `--port`) and exits with an error if it cannot bind that port; it never selects a different port. `WPS_TARGET_PORT_START` and `WPS_TARGET_PORT_END` set the target range.

`server_host` in `config.json` sets the default bind address. `--host` overrides it for both builder and live targets. Set it to `127.0.0.1` for local-only access. Startup health checks and the host's browser use a reachable local address when binding all interfaces.

`allowed_hosts` defaults to `["*"]`, accepting LAN IP addresses and DNS names. To limit host names, set it to a list such as `["analysis.lan", "192.168.1.10"]` without schemes or ports. Loopback names remain allowed for internal service calls. Restart the builder after a configuration change. Browser requests must still use the service's own origin; remote clients do not need CORS changes.

Use this deployment on a trusted network. There is no user login or project isolation between clients; clients can edit projects and run trusted Python under the host's account. The downloaded Windows application's default remains local-only.

All model requests pass through `backend/services/llm_gateway.py`, including the legacy agent service. Set these options in `config.json`:

```json
{
  "openai_api_base": "https://api.openai.com/v1",
  "openai_model_name": "gpt-4o-mini",
  "llm_timeout_seconds": 90,
  "llm_max_retries": 0,
  "llm_temperature": null
}
```

Set `OPENAI_API_KEY` in the environment before launch. API keys in the config file are ignored. For a local endpoint with no authentication, set this environment variable to a non-secret value such as `EMPTY`. `llm_max_retries` controls transport retries; `max_retries` controls proposal repair. A missing key blocks model requests but allows data import and existing dashboard use. Invalid config files fail at startup.

For models that require their default sampling settings, set `"llm_temperature": null`. The gateway then omits temperature. This is the setting used for `gpt-6-luna` with its default reasoning behavior. If a provider explicitly rejects temperature with HTTP 400, the gateway retries once without that field and remembers the restriction for the current client. It keeps the selected model. Other API errors include the provider message, parameter, and code with credentials redacted. Restart the builder after changing its configuration or gateway code. See the [official GPT-6 parameter guidance](https://developers.openai.com/api/docs/guides/latest-model).

Authoring uses ordinary chat completions. It does not send `response_format` or require provider-side JSON mode or strict schema support. The model returns JSON text; the application parses it and checks the revision, source, and graph locally. A complete fenced JSON block is accepted. The old `strict_model_outputs` setting is ignored.

To repair a failed calculation, ask Chat: **“Fix the latest failed run using its logs. Save the repair; I will select Run.”** Chat receives bounded recent builder and target diagnostics for the current project, including errors, traceback, output logs, step events, and a three-row input preview. Include a run ID to select an older run. Explain a column rename or intended datatype when needed. Chat prepares a repair for review. Select Apply to save it without executing it. Select **Run** to check the repair. The previous successful results remain visible until a new run succeeds.

Calculations run as trusted Python in a separate worker process, without code sandboxing or file and network restrictions. Workers use a reduced environment without model credentials. Time and memory limits, cancellation, progress reporting, and parent-exit cleanup remain active. Source checks validate the calculation contract and reproducibility; they do not restrict Python imports or file access.

Select **New project**, upload a CSV in **Data**, and describe the system in **Chat** or interactively on any stage page. The agent creates and refines four stage types: Data input, Data cleaning, Analysis, and Visualization. Dedicated pages for **Data cleaning** and **Analysis** display the complete internals of each stage—its configuration, inputs/outputs, Python code, parameter bindings, cleanup impacts, and table results—with an interactive AI stage creator bar at the top for conversational creation and refinement.

Use **Pipeline** to inspect the high-level flow from data to insight and jump directly to any stage's dedicated configuration page. Stage deletion includes an impact review; Undo and Redo restore development edits. Use **Dashboard** (Visualization) to drag and resize widgets or change their properties, or prompt AI to add charts and KPI metrics. Layout and display edits update the target after saving, using saved calculation artifacts. Data and calculation edits stay pending until Run.

Select a pipeline card or dashboard widget to set chat context. Its type and title appear above the composer. Questions receive answers; edits show a before/after review with Apply and Discard. Necessary linked changes and downstream effects are listed. Clear the context to work on the whole project. One transcript retains the original context labels and result provenance.

When current results are unavailable, chat offers **Run and ask again** or **Skip**. New calculations require a reviewed edit first. The follow-up after a successful run is answer-only; it cannot start another edit or run automatically.

To inspect stage code and configuration, start with `python launcher.py --developer-mode`. Select a card, then open **Inspect** for Python, JSON, producer links, controls, saved results, and diagnostics. Copy or download the inspection. This mode is read-only and applies to every client of that builder instance; it is not a user permission system.

The builder and generated dashboards support desktop use. The designer, live target, and exported application share one 12-column grid. There are no tablet or phone layouts or preview modes. The grid resizes within desktop windows; narrower windows and browser zoom use scrolling instead of changing widget positions. Minimum workspace widths are 1100 CSS pixels for the builder and 1000 for the target.

Properties shows only the selected card and controls used by that stage. Select the project name in the top bar to rename the project. Use **Dashboard settings** in Dashboard to edit its title and subtitle, and **Filters and scenario defaults** to set control labels, defaults, and ranges. CSV, column types, and business context stay in Data.

Each opened project starts a separate dashboard service on an available port from `8100` to `8199`. Select **Open dashboard** to use it. Targets stay open when you switch projects and stop when the builder stops. Set `WPS_TARGET_PORT_START` and `WPS_TARGET_PORT_END` to use a different range. Restart reuses the preferred port when it is available.

The target starts with the builder CSV. A target-side CSV upload uses separate runtime state and does not change the development input. **Use builder data** returns to the builder input. A failed refresh or incompatible developer update keeps the last successful revision and results.

Review cleanup and select **Accept revision** before downloading a Windows application. **History** keeps earlier accepted downloads available. The download contains the selected accepted revision and its accepted CSV when included; pending development changes and target-side CSV replacements are excluded.

## Practical scenarios

Start with the [step-by-step Markdown scenarios](docs/scenarios/README.md) to explore energy costs, build a ten-row sales report, inspect demand trends, and reuse a report with a new CSV. Each guide includes result checks and a short demonstration script. The first scenario needs no model access; the sales guide includes small synthetic practice files.

## Guided analysis tutorials

Open [the tutorial start page](tutorials/index.html) in a desktop browser, or extract [the complete tutorial ZIP](artifacts/wps-ai-tutorial-pack.zip). Keep all folders beside the HTML files. The pack includes four public CSVs, local interactive reference charts, copyable prompts, result checkpoints, and replacement/invalid-schema practice files. The pages work offline and do not call the builder API.

Use one new project per lesson: Palmer Penguins, Q1 2011 Online Retail, Wine Quality, and daily Bike Sharing. Follow the steps in the builder and compare the results with the guide. Source licences, transformations, hashes and model validation records are included in the pack.

To rebuild the guide from the repository root:

```bash
uv pip install -e '.[tutorials]'
python scripts/tutorial_data.py
python scripts/tutorial_validate.py --live-model
python scripts/build_tutorials.py
```

Live validation uses the configured model and API tokens. It writes isolated projects under `data/tutorial_validation`; it does not change existing projects or model configuration. Matching successful validations are reused. Data preparation caches the publisher downloads under `data/tutorial_sources`. A page build fails if validation does not match the current prompts and CSV hashes.

The guide documents the Windows runtime requirement. It does not include that runtime or replace a real Windows smoke test.

## Build and cache the Windows runtime

Run on Windows 11 x64 with Python 3.12, Node.js, and pnpm:

```powershell
python -m pip install -r requirements-runtime.txt
python -m pip install -e '.[dev,packaging]'
cd frontend
pnpm install --frozen-lockfile
cd ..
python scripts/build_windows_runtime.py
python scripts/windows_smoke.py
```

The Windows CI workflow builds and tests the same package. Copy its verified `windows-x64.zip` to Linux and set `WPS_WINDOWS_RUNTIME` to the archive's absolute path. Export then attaches the accepted project to this runtime.

Without a compatible runtime cache, export reports an error. It never substitutes a source-only package. The target workstation needs no development tools or model credentials. Extract the exported ZIP and run `WPSAnalysis.exe`.

Windows release verification requires the real build and a clean Windows machine with external network access blocked. Linux tests cannot prove this release gate.

## Verify changes

```bash
pytest tests/ -q
mypy pipeline_core backend config.py offline_app.py runtime_launcher.py
cd frontend
pnpm exec tsc --noEmit
pnpm exec vite build
pnpm exec vite build --mode runtime
```

For the full local service check, run `python scripts/studio_smoke.py`. It uses temporary projects, real target processes, and separate workers without model calls or a Windows runtime cache. It checks ports, live presentation, deletion and Undo, independent CSV input, failure recovery, credentials, restart, shutdown, and parent-crash cleanup.

Worker tests verify direct Python startup, file and local network access, cache reuse, cancellation, and credential exclusion. Runtime API tests verify CSV replacement, controls, complete table export, failure recovery, and the absence of chat and model routes. The legacy question-answering chat route is retired.
