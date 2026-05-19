## Why

The current log analysis client is highly capable of parsing logs and generating templates deterministically, but it lacks the dynamic reasoning capabilities described in its mission. The user needs an **Analysis Mode** workflow that bridges the gap between structured log data (Data Plane) and natural language queries using an LLM. By formally adding the LLM as an executor and introducing a secure Python code execution engine, we can empower the client to automatically generate data-science code to answer complex user queries.

## What Changes

- **Orchestrator Context State**: Update the Orchestrator to support passing data between executors. We will introduce `output_key` to save an instruction's result to the Orchestrator's internal context, and variable interpolation (using `$`) to inject those saved outputs into subsequent instructions.
- **`LlmExecutor`**: A new executor on the Data Plane responsible for calling the local LLM interface (`llm_client.py`). It will accept prompt configurations and dynamic inputs (e.g. DataFrame schemas, templates) to generate code.
- **`PythonRunnerExecutor`**: A new executor on the Data Plane responsible for safely executing generated Python code over the `df`. It will capture `stdout`, `stderr`, and any explicit result (e.g. `RESULT` variable) while blocking unauthorized modules via AST scanning.
- **`logparser` Updates**: Introduce a new action `get_parsed_info` (or similar) to `logparser` to expose the schema and underlying DataFrame for the Orchestrator's context.

## Capabilities

### New Capabilities
- `llm-execution`: The capability to execute generative AI tasks using prompt templates and context injection.
- `python-runner`: The capability to execute restricted Python scripts and capture execution outputs.
- `context-orchestration`: The orchestrator's capability to store execution outputs via `output_key` and inject them as `$` variables into future steps.

### Modified Capabilities
- `logparser`: Exposing `get_parsed_info` to share memory state.

## Impact

- **Affected code**: `src/orchestrator.py` (context passing), `src/executors/` (new executors), and `src/utils/llm_client.py` integration.
- **Risk**: Executing arbitrary Python code is dangerous. This will be heavily mitigated by AST parsing and execution isolation.
