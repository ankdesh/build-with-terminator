# Project Constitution: log-analysis-client

This document defines the foundational principles and technical direction for the `log-analysis-client`.

## Part 1: Mission
The mission of this project is to create a robust, extensible CLI client that acts as a Workflow Engine for log analysis, bridging local log environments and external AI Analysis Agents.

### Core Objectives
1.  **Workflow Executor**: Implement a "command-and-control" loop where the Orchestrator executes a deterministic queue of declarative instructions (the "Instruction Trace").
2.  **Dual-Plane Architecture**: Strictly separate the Control Plane (deciding what to do) from the Data Plane (doing the work).
    *   **Control Plane**: The Orchestrator routes instructions. When stuck or given open-ended tasks, it invokes an external **LLM Planner** to generate new instructions.
    *   **Data Plane**: Unified Workers (C++, Python, or LLM) execute specific tasks (like grepping, parsing templates, or inferring log formats).
3.  **Replayable Traces**: Ensure that an instruction trace authored by an LLM on one log file can be deterministically replayed on similar log files without incurring further LLM inference costs.
4.  **Agent Abstraction**: Abstract all agent interactions to support seamless testing, mocking, and future agent swaps. The client provides the capability to use the LLM either as a Planner (generating workflows) or as a Worker (processing data within a workflow).
5.  **Operational Excellence**: Ensure a reliable CLI experience with clear arguments and predictable behavior.

## Part 2: Tech Stack
*   **Workflow**: **Spec-Driven Development (SDD)**. Every feature must be preceded by an OpenSpec proposal, design, and task list.
*   **Management CLI**: `openspec` for orchestrating the SDD lifecycle.
*   **Python Tooling**: `uv` for dependency management and environment orchestration.
*   **Architecture (Orchestrator + Worker Model)**:
    *   **Orchestrator (Python)**: The main CLI entry point and Workflow Executor. Manages the instruction queue, invokes the LLM Planner when necessary, and dispatches tasks to Workers.
    *   **Unified Worker Interface**: All workers inherit from an abstract `WorkerBase` class to provide a common execution interface.
    *   **Python Workers**: For stateful data management and pure Python processing (e.g., `LogparserWorker` for log templates, `LlmWorker` for data inference).
    *   **C++ Integration & Performance Workers**: Compiled as shared libraries (`.so`/`.pyd`) for time-critical tasks (e.g., heavy log parsing, high-speed filtering) via `pybind11`.
*   **Documentation Standards**: 
    *   **General**: Add extensive comments to understand the semantics and rationale for any design decision.
    *   **C++ Code**: ALL C++ code must be thoroughly commented. Header files must describe class responsibilities and public API contracts. Implementation files must explain complex logic, threading behavior, and memory management decisions.
*   **Testing Standards**: 
    *   **Unit Tests**: Comprehensive unit tests (using `pytest` for Python-facing components) MUST be written for all new features. Tests should serve as both verification of correctness and documentation of intended usage.

## Part 3: Packaging
*   **Packaging**: **AppImage**. The project uses a hybrid build strategy:
    *   **Development**: `uv` for environment management and C++ build orchestration.
    *   **Distribution**: `python-appimage` to bundle the Python interpreter, dependencies, and compiled `pybind11` workers into a single, portable executable.

---
*This GEMINI.md serves as the primary instructional context for all AI interactions in this workspace.*
