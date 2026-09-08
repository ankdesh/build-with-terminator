# Project Constitution: WPS-AI

This document outlines the architectural principles, design constraints, and engineering guidelines governing **WPS-AI**.

---

## 1. Environment & Dependency Management
- **Primary Package Manager**: `uv` and `uv venv` are standard for all Python workflows.
- **Size Optimization Principle**: Never introduce heavy external binary packages (such as `matplotlib`, `seaborn`, `plotly`, `scipy`, `scikit-learn`) into the backend runtime when client-side alternatives (such as `Recharts` in React) can satisfy the user requirement with zero backend footprint.
- **Air-Gap Guarantee**: Zero runtime external HTTP calls except to the explicit `OPENAI_API_BASE` endpoint.

---

## 2. Architecture & Code Structure
- **Modular, Interface-Driven Design**: Services are separated strictly by capability:
  - `SessionStore`: Local file-based persistence for sessions, raw data, profiles, and messages.
  - `DataProfiler`: Pandas-based schema analysis, descriptive stats, and data quality checks.
  - `CodeExecutor`: Direct in-memory Python script execution producing JSON-serializable outputs.
  - `AgentService`: LLM orchestration, plan-execute-explain streaming pipeline, and self-correction loop.
- **One Primary Class Per File**: Every Python file hosts one primary domain class (`SessionStore` in `session_store.py`, `DataProfiler` in `data_profiler.py`, `CodeExecutor` in `code_executor.py`, `AgentService` in `agent_service.py`).
- **Separation of Visualization**: Visual chart generation is handled client-side in the React layer via Recharts specifications (`ChartSpec`). The backend only emits data series and configuration.

---

## 3. Error Handling & Reliability
- **Fail Explicitly and Early**: All domain errors use precise custom exceptions inheriting from `WPSAIBaseException` (`SessionNotFoundError`, `DatasetNotLoadedError`, `DataProfilingError`, `CodeExecutionError`, `LLMServiceError`).
- **Automatic Self-Correction**: When user data queries trigger syntax errors or schema mismatches in generated Python code, the system intercepts the traceback and automatically re-prompts the model up to 3 times before failing gracefully.
- **Static Typing**: Full static type coverage enforced via `mypy` with `disallow_untyped_defs = true` and `pydantic.mypy` plugin.

---

## 4. Testing Strategy
- **Balanced Pyramid**:
  - Unit tests for data profiling, descriptive statistics, and quality flags (`test_data_profiler.py`).
  - Unit tests for code execution, DataFrame isolation, and error traceback capturing (`test_code_executor.py`).
  - Unit tests for agent self-correction and retry loops (`test_agent_service.py`).
  - End-to-end integration tests verifying API routes, file uploads, and session persistence (`test_integration.py`).

---

## 5. Configuration & Readability
- **Centralized Configuration**: All environment variables, defaults, timeouts, and file limits are hoisted in `config.py`. Magic numbers and strings are strictly prohibited in application code.
- **Document Intent**: Functions and classes include docstrings explaining purpose, inputs, and behaviors.
