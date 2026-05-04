# Project Constitution: log-analysis-client

This document defines the foundational principles and technical direction for the `log-analysis-client`.

## Part 1: Mission
The mission of this project is to create a robust, extensible CLI client that acts as the bridge between local log environments and an external AI Analysis Agent.

### Core Objectives
1.  **Agent Abstraction**: Provide a clean interface for an external AI agent. The agent itself is **not** part of this project; the client must abstract all agent interactions to support seamless testing, mocking, and future agent swaps.
2.  **Data Collection & Dispatch**: Efficiently collect data and metadata from input logs and transmit them to the agent for analysis, incorporating user confirmation and input where necessary.
3.  **Dynamic Instruction Execution**: Implement a "command-and-control" loop where the client receives, parses, and executes instructions from the agent. Required core capabilities include:
    *   `grep`: Executing pattern searches on local log files.
    *   `execute_py`: Safely running Python snippets for complex data processing.
4.  **Operational Excellence**: Ensure a reliable CLI experience with clear arguments and predictable behavior.

## Part 2: Tech Stack
*   **Workflow**: **Spec-Driven Development (SDD)**. Every feature must be preceded by an OpenSpec proposal, design, and task list.
*   **Management CLI**: `openspec` for orchestrating the SDD lifecycle.
*   **Python Tooling**: `uv` for dependency management and environment orchestration.
*   **Architecture (Orchestrator + Worker Model)**:
    *   **Orchestrator (Python)**: The main CLI entry point and agent interface. Handles network communication, state management, and the `execute_py` instruction.
    *   **C++ Integration**: `pybind11` for high-performance shared library access.
    *   **Performance Workers (C++)**: Compiled as shared libraries (`.so`/`.pyd`) for time-critical tasks (e.g., heavy log parsing, high-speed filtering).
*   **Packaging**: **AppImage**. The project uses a hybrid build strategy:
    *   **Development**: `uv` for environment management and C++ build orchestration.
    *   **Distribution**: `python-appimage` to bundle the Python interpreter, dependencies, and compiled `pybind11` workers into a single, portable executable.

---
*This GEMINI.md serves as the primary instructional context for all AI interactions in this workspace.*
