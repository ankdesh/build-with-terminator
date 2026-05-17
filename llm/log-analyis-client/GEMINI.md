# Project Constitution: log-analysis-client

This document defines the foundational principles and technical direction for the `log-analysis-client`.

## Part 1: Mission
The mission of this project is to create a robust, extensible CLI client that acts as a Workflow Engine for log analysis, bridging local log environments and external AI Analysis Agents.

### Core Objectives
1.  **Workflow Engine**: Implement a "command-and-control" loop where the Orchestrator executes a deterministic queue of declarative instructions (the "Instruction Trace").
2.  **Dual-Plane Architecture**: Strictly separate the Control Plane (deciding what to do) from the Data Plane (doing the work).
    *   **Control Plane**: The Orchestrator routes instructions. When stuck or given open-ended tasks, it invokes an external **LLM Planner** to generate new instructions.
    *   **Data Plane**: Unified Executors (C++, Python, or LLM) run specific tasks (like grepping, parsing templates, or inferring log formats).
3.  **Replayable Traces**: Ensure that an instruction trace authored by an LLM on one log file can be deterministically replayed on similar log files without incurring further LLM inference costs.
4.  **Agent Abstraction**: Abstract all agent interactions to support seamless testing, mocking, and future agent swaps. The client provides the capability to use the LLM either as a Planner (generating workflows) or as an Executor (processing data within a workflow).
5.  **Operational Excellence**: Ensure a reliable CLI experience with clear arguments and predictable behavior.

## Part 2: High-Level Architecture (Workflow Engine)
The client operates on a standardized orchestration paradigm:
*   **Instruction**: A granular, declarative JSON/dictionary describing a specific operation (e.g., `{"action": "scan", "executor": "scanner", "pattern": "ERROR"}`).
*   **Instruction Trace (Workflow)**: A deterministic sequence of Instructions. This serves as a reproducible runbook that defines the full analysis pipeline for a log file.
*   **Executor**: A discrete, isolated component that registers with the Orchestrator to handle specific actions. Executors operate on the Data Plane. They do not decide *what* to do, only *how* to do it.
*   **Orchestrator**: The central Control Plane loop. It acts as the runtime, picking up instructions from the queue, invoking the requested Executor, managing state, and dispatching tasks asynchronously.

## Part 3: Code-Level Practices & Standards
*   **Directory Structure**: We maintain a flat, clean `src/` package layout.
    *   `src/orchestrator.py`: Contains the core Orchestrator logic.
    *   `src/executors/`: Contains all Python Executors (inheriting from `BaseExecutor`).
    *   `src/utils/`: Contains non-core utilities (like `llm_client.py`).
    *   `cpp/`: Contains C++ source code.
    *   `tests/`: Comprehensive unit tests.
*   **Python Tooling**: `uv` for dependency management and environment orchestration.
*   **Performance & Polyglot Integration**: 
    *   Time-critical data scanning is written in C++ and compiled as a shared library (`executor.so`) using `pybind11`. 
    *   Data transfer from C++ to Python must minimize overhead, heavily utilizing **Zero-Copy Memory Access** patterns (e.g., passing `memoryview` objects pointing to `mmap` buffers rather than copying strings).
*   **Testing**: 
    *   Use `pytest` and `pytest-asyncio` for comprehensive unit testing.
    *   Tests should simulate the Orchestrator loop using mocked instructions. Test files must reflect the Executor nomenclature (e.g., `test_orchestrator.py`, `test_stats_executor.py`).
*   **Documentation Standards**: 
    *   Add extensive comments to understand the semantics and rationale for any design decision.
    *   ALL C++ code must be thoroughly commented. Header files must describe class responsibilities and public API contracts.

## Part 4: Tech Stack & Workflow
*   **Workflow**: **Spec-Driven Development (SDD)**. Every feature must be preceded by an OpenSpec proposal, design, and task list.
*   **Management CLI**: `openspec` for orchestrating the SDD lifecycle.
*   **Constitution Updates (OPSX Check)**: At the time of each `/opsx-archive`, the AI agent MUST check if any architectural decisions, tooling changes, or coding practices discovered during the implementation need to be added to this constitution. The proposed changes should be shown to the user for review and then added/updated here.

## Part 5: Packaging
*   **Packaging**: **AppImage**. The project uses a hybrid build strategy:
    *   **Development**: `uv` for environment management and C++ build orchestration.
    *   **Distribution**: `python-appimage` to bundle the Python interpreter, dependencies, and compiled `pybind11` executors into a single, portable executable.

---
*This GEMINI.md serves as the primary instructional context for all AI interactions in this workspace.*
