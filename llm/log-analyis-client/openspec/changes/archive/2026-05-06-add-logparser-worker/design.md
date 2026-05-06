## Context

The system currently uses an Orchestrator with a hardcoded mechanism for interacting with a C++ worker module. As we transition towards a "Workflow Engine" architecture where the Orchestrator executes a deterministic queue of declarative instructions, we need a unified interface for all workers. Additionally, to support intelligent log analysis by an AI Agent, we need to extract templates and structured parameters from raw logs. We will introduce a stateful `LogparserWorker` based on the `logparser` library (using the Drain algorithm) to fulfill this need. 

## Goals / Non-Goals

**Goals:**
- Design a `WorkerBase` abstract base class to enforce a unified execution interface for all workers.
- Design a Python-based `LogparserWorker` that wraps the `logparser` library.
- Ensure the `LogparserWorker` is stateful (can hold parsed DataFrames in memory) to serve subsequent queries without re-parsing or disk I/O.
- Define the JSON instruction schema for log parsing and querying.

**Non-Goals:**
- We are not porting Drain or other log parsing algorithms to C++.
- We are not altering the C++ Scanner logic in this design, only wrapping it in the new `WorkerBase` interface.
- We are not implementing the `LlmPlanner` logic yet; this design focuses strictly on the data plane workers.

## Decisions

**1. Unified Worker Interface (`WorkerBase`)**
- **Decision:** Create an abstract class with `name` (property), `capabilities()` (method returning a list of supported actions), and `execute(action: str, args: dict) -> dict` (method).
- **Rationale:** This standardizes how the Orchestrator interacts with workers. The Orchestrator can maintain a simple registry (e.g., `{"logparser": LogparserWorker(), "scanner": CppScannerWorker()}`) and blindly route instructions like `worker.execute(instruction["action"], instruction["args"])`.

**2. Stateful Logparser Worker**
- **Decision:** The `LogparserWorker` will hold parsed results in memory using pandas DataFrames.
- **Rationale:** The `logparser` library natively outputs to CSVs and DataFrames. By keeping the DataFrame in memory (e.g., `self._parsed_df`), the Orchestrator can quickly execute subsequent instructions like `get_templates` or `query_parameters` without heavy disk I/O.

**3. Instruction Schema**
- **Decision:** The worker will support:
  - `parse_templates(algorithm, log_format, target_file)`: Runs the algorithm.
  - `get_templates(sort_by, order, limit)`: Returns top N templates.
  - `query_parameters(event_id, limit)`: Returns rows for a specific template.

## Risks / Trade-offs

- **Memory Constraints:** Holding large DataFrames in memory could lead to Out Of Memory (OOM) errors on massive log files.
  - *Mitigation:* We will rely on the C++ Scanner to pre-filter logs when possible, passing only a subset of logs to the `LogparserWorker`. 
- **Log Format Regex:** The `logparser` library strictly requires a regex to separate log headers from content.
  - *Mitigation:* We will implement an `LlmWorker` in a future step to infer this regex, keeping the `LogparserWorker` strictly focused on deterministic parsing.
