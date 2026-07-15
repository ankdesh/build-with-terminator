# Project Constitution: SystemC TLM 2.0 AT Performance Models

This document serves as the project constitution (`GEMINI.md`) for the SystemC TLM 2.0 Approximately-Timed (AT) performance modeling repository.

---

## 1. Project Overview & Architecture

The project contains four performance modeling examples demonstrating TLM 2.0 Approximately-Timed (AT) interfaces in C++:
0. **Simple Pipeline Stage** (Example 0)
1. **Pipelined ALU** (Example 1)
2. **FIFO-based Backpressure** (Example 2)
3. **Switch Arbitration** (Example 3)

### Architectural Standards
- **Core Engine**: Built entirely on C++ using the Accellera SystemC 2.3.3 library.
- **Protocol**: Strictly utilizes the non-blocking transport interface (`nb_transport_fw`/`nb_transport_bw`) with a **2-phase AT protocol**:
  - `BEGIN_REQ` -> `END_REQ` (Request phase, closing the interface handshake).
- **Time Representation**: All log traces print standardized cycle numbers `[CYCLE: X]` (where 1 cycle = 10ns) to display clean, cycle-based timestamps.
- **Modularity**: Components are written in modular header files (`.h`) to represent IP blocks and instantiated in `main.cpp` testbenches.

---

## 2. Dependency Setup

- **SystemC**: Cloned from GitHub (tag `2.3.3`) and compiled locally into `systemc-dist/`. Linked via `CMakeLists.txt` using the modern `SystemCLanguage` cmake package.
- **Python**: A local virtual environment (`.venv`) is created using `uv` to install `pytest` for executing integration tests.

---

## 3. Testing Strategy

- **Integration Tests**: Verification is performed by end-to-end integration tests written in `tests/test_performance_models.py`.
- **Methodology**: The test suite runs the compiled binaries, captures stdout log traces, and checks timing relationships (latencies, pipeline delays, stall cycles) and handshakes using regex matching.
- **Test Command**: `.venv/bin/pytest tests/test_performance_models.py -v`
