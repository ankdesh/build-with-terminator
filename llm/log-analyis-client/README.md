# Log Analysis Client (Workflow Engine)

A robust, extensible CLI client that acts as a **Workflow Engine** for log analysis, bridging local log environments and external AI Analysis Agents.

---

## 🚀 High-Level Architecture

The project is designed around a **Dual-Plane Architecture** to cleanly decouple operational decisions from target execution:

1. **Control Plane (Orchestrator)**: Manages instruction routing, queues, state handling, and execution dispatching.
2. **Data Plane (Executors)**: Standalone workers (written in Python or C++) that register with the Orchestrator to execute deterministic, declarative instructions (e.g. scanning patterns, parsing log templates, extracting statistics).

### Core Highlights
* **Declarative Instruction Traces (Workflows)**: Runs reproducible runbooks defined as simple YAML list instructions. An trace designed on one log file can be replayed identically on similar logs without extra LLM overhead.
* **Polyglot & Zero-Copy Performance**: High-performance scanning layers compiled as C++ shared libraries utilizing `pybind11` and memory-mapped buffers for ultra-fast, zero-copy interactions.
* **Unified Registry**: Executors easily register their capabilities dynamically, making it a highly extensible engine.

---

## 🛠 Setup & Installation

The project uses `uv` for modern, fast Python package and environment management.

To set up the development environment, execute:

```bash
# Sync environment dependencies and build components
uv sync
```

---

## 📖 Usage & Commands

Run commands via `uv run` to ensure you are executing inside the managed environment.

### 1. Execute Predefined Workflows
Deterministic execution of YAML-based instruction runs over a target log file.

```bash
uv run python src/cli.py execute --workflow <workflow_file> --log <log_file>
```

#### Examples:
* **Parse templates & retrieve summary**:
  ```bash
  uv run python src/cli.py execute \
    --workflow workflows/parse_and_get_templates.yaml \
    --log datasets/loghub_raw_logs_2k/HDFS_2k.log
  ```
  
* **Retrieve file statistics**:
  ```bash
  uv run python src/cli.py execute \
    --workflow workflows/extract_stats.yaml \
    --log datasets/loghub_raw_logs_2k/Apache_2k.log
  ```

### 2. Analysis Mode (Placeholder)
Designed for future LLM-driven planning. Generates a workflow trace dynamically from a natural language query.

```bash
uv run python src/cli.py analysis --request "<your prompt>" --log <log_file>
```

---

## 📂 Repository Structure

* `src/`: Core Python packages
  * `cli.py`: Command-line entry point.
  * `orchestrator.py`: Main Orchestrator engine control loop.
  * `executors/`: Registerable executors (`logparser`, `stats`, `base`, etc.).
* `cpp/`: Performance C++ scanning components.
* `workflows/`: Reusable, declarative YAML workflow runs.
* `datasets/`: Raw sample logs (HDFS, Apache, Windows, etc.) for testing and replication.
* `tests/`: Comprehensive unit tests.
