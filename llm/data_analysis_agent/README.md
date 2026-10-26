# WPS-AI Data Analysis Studio

Build a reusable analysis application through chat on Linux. Review its cleanup and calculations, refine its dashboard, and accept a saved revision. Export that revision for a Windows workstation with no chat, LLM, or internet dependency.

The application supports one replacement CSV up to 100 MB, generated pandas and NumPy code, SciPy and statsmodels calculations, forecasts, linked filters, and what-if controls. It preserves the last successful dashboard when a refresh fails.

See [PLATFORM.md](PLATFORM.md) for contracts, execution policy, packaging, and release checks. The system design document is in [artifacts/data-analysis-system-design.docx](artifacts/data-analysis-system-design.docx).

## Start the Linux builder

Python 3.12, Node.js, pnpm, and Bubblewrap are required. Enable Linux user namespaces. Workers fail closed when isolation is unavailable.

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

Use the existing `config.json` for the model endpoint and model name. Supply credentials through `OPENAI_API_KEY`. The model receives bounded data context while the full CSV stays local.

Select **New project**, upload a CSV, and describe the system in chat. **Load example system** creates a validated energy dashboard without a model call. Open the pipeline inspector to review cleanup and source code. Accept a validated revision before export.

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

Linux worker tests need permission to create Bubblewrap namespaces. Runtime API tests verify CSV replacement, controls, complete table export, failure recovery, and the absence of chat and model routes. The legacy question-answering chat route is retired.
