## Context

Building on the basic project skeleton, we are now implementing the performance-critical components.

## Goals / Non-Goals

**Goals:**
- Implement the Global Memory Manager (GMM) in C++.
- Implement `mmap`-based file reading.
- Implement a slab-based parallel scanner using a thread pool.
- Implement an asynchronous command queue in Python.

**Non-Goals:**
- Implementing the final AppImage distribution.
- Implementing complex AI agent communication protocols (will use mocks).

## Decisions

### Decision: Global Memory Manager
Centralized mapping to ensure a file is only mapped once and shared between C++ and Python.

### Decision: Slab-based Parallel Scanning
Dividing large files into chunks for multi-core processing, handling line boundaries correctly.

### Decision: Atomic Cancellation
Using `std::atomic<bool>` to safely stop C++ threads from the Python orchestrator.

## Risks / Trade-offs

- **[Risk] Line Boundary Clipping** → **Mitigation**: Workers will scan for newlines at the start and end of their slabs to avoid partial lines.
