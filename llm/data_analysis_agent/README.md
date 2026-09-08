# WPS-AI — Lightweight Air-Gapped Data Analysis Chatbot

**WPS-AI** is a self-contained, air-gapped data analysis chatbot. It enables non-technical and technical operators to upload CSV datasets alongside column description text files, ask questions in natural language, and receive plain-English explanations with interactive charts, sortable data tables, and an inspectable side panel detailing every step of the calculation.

---

## Key Features

- **Air-Gapped & Self-Contained**: Operates with strictly zero external internet access. Connects only to your designated OpenAI-compatible API endpoint (e.g., local vLLM, Ollama, or internal gateway).
- **Direct Python Code Execution**: In-memory data manipulation using `pandas` and `numpy`. No heavy sandboxing or complex container orchestration required.
- **Client-Side Interactive Visualizations**: All charts (bar, line, area, pie, scatter) are rendered directly in the browser via **Recharts**, keeping the Python backend lean (~35 MB compressed download / ~100 MB on disk) without bundling heavy libraries (`matplotlib`, `seaborn`, `plotly`).
- **Automated Data Profiling**: On upload, computes schema types, sample preview rows, descriptive statistics (min, max, mean, median), and missing value metrics.
- **Toggleable Data Quality Report**: Automatically flags duplicate rows, extreme outliers, constant columns, and format anomalies with a single-click UI toggle.
- **Plan → Execute → Explain Workflow**: Real-time token streaming (SSE) displaying the preliminary plan as it is formulated, followed by visual artifacts and a clear explanation in simple English.
- **Self-Correcting Error Recovery**: If generated code fails with a syntax or runtime error, the agent intercepts the traceback, re-prompts the model, and recovers automatically (up to 3 retries).
- **Persistent Step-by-Step Side Panel**: Dedicated collapsible right panel displaying the execution plan, syntax-formatted Python code, execution duration (ms), retry counts, and raw standard output.
- **Data & Visual Export**: One-click download for charts (SVG) and tables (CSV).
- **Local Session Persistence**: All datasets, profiles, and conversation turns are stored locally on disk (`~/.wps-ai/sessions/` or `./data/sessions/`), allowing full session resumption across app restarts.

---

## Architecture Overview

```
User (Browser / Webview)
       ↕  (HTTP / Server-Sent Events)
FastAPI Backend (Localhost) ↔ OpenAI-compatible API (Internal / Air-gap)
       ↕
Python Code Runner (pandas, numpy)
       ↓ (Emits structured JSON: metrics, tables, chart series)
Frontend (React + assistant-ui + Recharts)
```

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | React 18, `@assistant-ui/react`, Tailwind CSS, Lucide | Responsive enterprise light theme UI |
| **Charts & Visuals** | **Recharts** (Client-side) | Interactive hover tooltips, legends, animations, SVG export |
| **Backend** | Python 3.12, FastAPI, Uvicorn | API routing, session management, static asset serving |
| **Data Engine** | **pandas, numpy** | Data aggregations, metrics, time-series analysis, IQR anomaly checks |
| **Packaging** | `uv`, Vite static export, `launcher.py` | Single portable directory distribution |

---

## Getting Started

### Prerequisites
- Python 3.11+
- `uv` package manager (recommended) or `pip`
- Node.js 20+ (only required if building frontend from source)

### 1. Environment Configuration

Set the environment variables pointing to your OpenAI-compatible endpoint:

```bash
# Required: URL to your local or internal OpenAI-compatible endpoint
export OPENAI_API_BASE="http://127.0.0.1:11434/v1"   # Example: local Ollama or vLLM

# Optional (defaults shown)
export OPENAI_API_KEY="EMPTY"                         # API key if required
export OPENAI_MODEL_NAME="gpt-4o-mini"                 # Model name
export PORT="8080"                                    # Port to bind
export HOST="127.0.0.1"                               # Host to bind
```

*Note: On Windows PowerShell:*
```powershell
$env:OPENAI_API_BASE = "http://127.0.0.1:11434/v1"
$env:OPENAI_MODEL_NAME = "gpt-4o-mini"
```

### 2. Quick Launch (Development / Local)

```bash
# 1. Setup virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Launch the application
python launcher.py
```

`launcher.py` will verify port availability, start the FastAPI server, perform a health check, and automatically open your default browser to `http://127.0.0.1:8080`.

To start in headless mode (no browser popup):
```bash
python launcher.py --headless
```

---

## Sample Dataset

A realistic sample dataset is included in `sample_data/`:
- `sample_data/electric_usage.csv`: 360 hourly readings of electricity consumption (`kwh_consumed`), peak power demand (`peak_demand_kw`), outdoor temperature (`temperature_f`), and occupant count across three facility zones (`Zone-A`, `Zone-B`, `Zone-C`).
- `sample_data/electric_usage_desc.txt`: Detailed descriptions and units for each column.

**To load the sample in the UI:**
Click **"Upload Data"** in the top bar, then click **"Load Electric Usage Sample"**.

**Suggested questions to ask:**
- *"What was the average energy consumption by building zone?"*
- *"Plot an hourly trend of kilowatt-hours consumed over time."*
- *"What was the highest peak demand hour, and what was the temperature then?"*
- *"Are there any unusual power spikes or outliers in the data?"*

---

## Running Tests & Quality Verification

```bash
# Run pytest test suite (7 unit & integration tests)
.venv/bin/pytest tests/ -v

# Run mypy static type checking (strict typing)
.venv/bin/mypy backend/ config.py tests/
```

---

## Packaging for Air-Gapped Deployment

To compile the frontend static assets and assemble the self-contained distribution:

```bash
python build.py
```

The resulting package will be created in `dist/wps-ai/`:
- Contains the compiled React frontend embedded directly into `backend/static/`.
- Includes `launcher.py`, `start.sh` (Linux), and `start.bat` (Windows).
- Transfer `dist/wps-ai/` via USB drive to the target air-gapped system.
- Run `./start.sh` (or `start.bat` on Windows).
