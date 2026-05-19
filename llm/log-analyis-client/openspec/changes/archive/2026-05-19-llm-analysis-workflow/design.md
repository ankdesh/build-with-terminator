## Context

The system needs to execute AI-driven log analysis workflows by generating and running Python code dynamically based on parsed log data. Since Executors operate on the Data Plane and the Orchestrator on the Control Plane, we must establish a pattern for executors to exchange complex objects (like pandas DataFrames) and generated code scripts without tightly coupling the executors together.

## Goals / Non-Goals

**Goals:**
- Allow the Orchestrator to route output data from one executor to the input of another.
- Implement an LLM executor to generate data-science python scripts.
- Implement a Python Runner executor to run scripts securely.

**Non-Goals:**
- Creating a full-fledged agentic loop (where the LLM runs in a `while True` loop reacting to errors). For this iteration, we focus on a deterministic 1-pass generative workflow.
- Complete system sandboxing (like Docker isolation). We will rely on simple AST-based static analysis to prevent trivial malicious code, assuming the local LLM is largely cooperative.

## Decisions

- **Orchestrator Context Dictionary**: The `Orchestrator` will maintain a `self.context = {}` dictionary. When an instruction provides an `output_key`, the orchestrator stores the executor's return dictionary under that key.
- **Variable Interpolation**: When the orchestrator processes an instruction's `args`, any string value that starts with `$` (e.g. `"$parsed_data.df"`) will be intercepted. The orchestrator will traverse `self.context` and replace the string with the actual python object reference before passing it to the executor.
- **Python Runner Sandbox**: The `PythonRunnerExecutor` will use Python's `ast.parse` to scan the provided code string for `Import` and `ImportFrom` nodes. If modules like `os`, `sys`, `subprocess`, `pathlib`, or `shutil` are found, it blocks execution.
- **Code Execution**: The code will be run via `exec(code, restricted_globals, local_scope)`. The `inputs` dict provided by the orchestrator will be populated into `local_scope`. `contextlib.redirect_stdout/err` will capture prints.

## Risks / Trade-offs

- **Risk**: Variable interpolation only supports top-level `$path` strings (not substrings like `"The data is $data"`).
  - **Mitigation**: This is sufficient for object passing (like passing the entire DataFrame). String formatting can be handled inside executors if needed.
- **Risk**: AST sandboxing is not bulletproof against advanced obfuscated Python.
  - **Mitigation**: Acceptable trade-off for a local, experimental dev tool where the threat model is "a helpful local LLM hallucinating bad imports" rather than a malicious actor.
