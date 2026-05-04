# Technical Note: Shared Memory & Mmap Architecture

## Overview
To achieve high-performance log analysis in a hybrid Python/C++ environment, we utilize **Memory-Mapped Files (mmap)**. This architecture allows the C++ Worker to own the data stream while providing the Python Orchestrator with zero-copy access to the log data.

## Key Concepts

### 1. Memory-Mapped Files (mmap)
By mapping a file directly into the process's virtual address space, we bypass the traditional overhead of copying data between kernel and user space. Both C++ and Python can address the same physical RAM segments that hold the file content.

### 2. The "Zero-Copy" Bridge
- **C++ Responsibility**: The worker maps the file and performs high-speed scans (e.g., regex, pattern matching) using native instructions.
- **The Handover**: Instead of passing strings, C++ passes an **offset** and a **length** to Python.
- **Python Responsibility**: Python uses the `mmap` module or `memoryview` to access the specific slice of memory directly. No string allocation occurs until the data is actually needed for high-level logic or display.

## Implementation Strategy

### C++ Side (The Worker)
- Use `mmap()` (Linux) to map the log file.
- Implement analysis logic that operates on `const char*` buffers.
- Use `pybind11` to expose functions that return memory views or buffer protocol objects.

### Python Side (The Orchestrator)
- Use `memoryview` to interface with the C++ allocated memory.
- For "Live" logs, handle file growth by occasionally re-mapping or using a sliding window approach.

## Benefits
- **Performance**: Significant reduction in CPU cycles by avoiding data serialization and copying.
- **Memory Efficiency**: Large files do not need to be loaded into the Python heap.
- **Latency**: Near-instantaneous random access to any part of a multi-gigabyte log file.

## Risks & Mitigations
- **Memory Safety**: Python must not access memory if the C++ worker has unmapped the file.
- **GIL Management**: C++ must carefully manage the Global Interpreter Lock when notifying Python of new data found in the map.
