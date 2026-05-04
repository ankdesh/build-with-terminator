## Context

The `log-analysis-client` is a new project. We need to establish the basic directories and build systems.

## Goals / Non-Goals

**Goals:**
- Initialize a Python project using `uv`.
- Create a `CMakeLists.txt` that can build a simple C++ extension.
- Implement a basic `main.py` that loads the C++ extension via `pybind11`.

**Non-Goals:**
- Implementing Shared Memory or `mmap`.
- Implementing Parallel Scanning.
- Implementing the full Agent interface.

## Decisions

### Decision: Environment Management with `uv`
Standard choice for fast, reliable Python environment management.

### Decision: Minimal pybind11 Bridge
We will use `pybind11` for the C++ bridge as it is standard and easy to integrate with CMake.

## Risks / Trade-offs

- **[Risk] Build Complexity** → **Mitigation**: Keep the initial CMake setup as simple as possible.
