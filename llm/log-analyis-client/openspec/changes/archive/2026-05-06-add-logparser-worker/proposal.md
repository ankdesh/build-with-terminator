## Why

The current Orchestrator relies primarily on high-speed C++ filtering but lacks the ability to understand the structure of the logs it processes. To empower the AI Agent with robust insights, we need to extract templates and structured data from logs (using algorithms like Drain). This change introduces a stateful Logparser Python Worker that implements the unified `WorkerBase` interface, enabling the Orchestrator to execute deterministic parsing workflows.

## What Changes

- Introduce a unified `WorkerBase` abstract class to standardize execution and capability discovery across all workers.
- Implement `LogparserWorker`, a Python-based worker using the `logparser` library (Drain algorithm) to extract log templates and parameters.
- Define a set of declarative JSON instructions (`parse_templates`, `get_templates`, `query_parameters`) that the `LogparserWorker` can execute on behalf of the Orchestrator.
- Add an `LlmWorker` to handle in-pipeline data extraction (e.g., inferring regex formats) without mutating control flow.

## Capabilities

### New Capabilities
- `log-parsing`: The ability to run structure-extraction algorithms on log files and query the resulting templates and parameters.
- `declarative-workers`: The unified worker interface that allows the Orchestrator to dispatch instructions deterministically.

### Modified Capabilities
- None.

## Impact

- **Code**: Adds `worker_base.py` and `logparser_worker.py`. 
- **Dependencies**: Introduces the `logparser` Python library as a dependency.
- **Architecture**: Transitions the Orchestrator to route instructions to `WorkerBase` instances rather than ad-hoc method calls.
