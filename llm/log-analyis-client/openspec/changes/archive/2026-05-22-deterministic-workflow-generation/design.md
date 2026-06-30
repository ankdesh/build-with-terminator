## Context

Currently, the `log-analysis-client` performs LLM-based logic execution sequentially inside the Orchestrator's execution loop (via `gen_pycode_fromtemplate` in `LlmExecutor`). This creates dynamic behavior, latency, and reliance on active LLM inference at replay time. We are transitioning to a split-plane design:
1. **Interactive Analysis Phase**: The user interacts with a conversational LLM agent that picks/synthesizes a workflow, runs it in the background to verify results, accepts corrections, and compiles a fully resolved trace.
2. **Deterministic Execution Phase**: The generated trace is replayed offline, executing C++ scanner, template parsing, or pre-generated python code with 100% determinism.

## Goals / Non-Goals

**Goals:**
- Implement a conversational ReAct agent loop in Python for the `analysis` command.
- Predefined internal templates saved as simple YAML in `workflow_templates/`.
- Concrete generated workflow traces written as simple YAML in a hidden `.workflows/` directory under the project root.
- Decouple LLM calls from the replay trace: convert dynamic `llm` actions in a template into static `python_runner` actions in the generated trace.
- Standardize printing of final execution answers via the `RESULT` key in orchestrator context.

**Non-Goals:**
- Storing workflows in database formats like SQLite (user explicitly requested simple YAML for now).
- Supporting remote/cloud sync of workflows.

## Decisions

### Decision 1: Run ReAct Loop in CLI Control Plane (`src/analysis_agent.py`)
- **Alternatives Considered**:
  - *Option A*: Implement the interactive loop inside a special executor.
  - *Option B (Chosen)*: Run a dedicated `AnalysisAgent` in the CLI control plane. It orchestrates sub-runs via `Orchestrator` instances, analyzes outputs, and interacts with the user.
- **Rationale**: Keeps the Orchestrator thin, stateless, and 100% deterministic. The control loop is cleanly isolated in the control plane.

### Decision 2: Store traces in hidden `.workflows/` directory
- **Alternatives Considered**:
  - *Option A*: Store in a public `workflows/` directory.
  - *Option B (Chosen)*: Store in a hidden `.workflows/` directory under the workspace root, which is added to `.gitignore`.
- **Rationale**: Keeps files out of standard directory listings to maintain clean work spaces while retaining simple YAML read/write operations.

### Decision 3: Resolving dynamic steps at trace compilation time
- **Alternatives Considered**:
  - *Option A*: Save the dynamic `llm` actions inside the trace but mock them at replay time.
  - *Option B (Chosen)*: Keep the `llm` executor as a dynamic stage inside templates (e.g., executing python code-generation, log formatting, or structural parsing during the interactive analysis phase). When compiling the final approved trace, replace these dynamic `llm` actions with static counterpart actions (e.g., replacing code-generation with `execute_python` containing the statically generated python code block; replacing summary generation with static string variables in context).
- **Rationale**: This preserves the flexibility of having dynamic LLM execution stages in internal templates, while ensuring that the compiled, saved replay trace remains 100% offline-capable, highly performant, and completely free of dynamic LLM calls.

### Decision 4: Global Log Path Parameter Injection
- **Choice**: Remove `target_file` from trace instructions. The Orchestrator stores a single global variable `self.log_path` (initialized via constructor). At runtime, if an instruction requires a log path and does not define a `target_file` in its arguments, the Orchestrator automatically injects its global `log_path` into `args`.
- **Rationale**: This removes redundant target file references from trace instructions, making generated YAML traces inherently transportable across different log files with zero override logic.

### Decision 5: Intermediate Execution via Persistent Orchestrator
- **Choice**: The `AnalysisAgent` instantiates a single persistent `Orchestrator` instance for the entire interactive analysis run. It executes actions sequentially via `send_instruction`, and directly reads execution outputs from `orchestrator.context` to inform the ReAct loop's next steps.
- **Rationale**: Keeps execution highly efficient and allows state (like parsed schemas and dataframes) to persist naturally between sequential tool steps in the background.

### Decision 6: Conversational Prompt Interface
- **Choice**: Use a standard console prompt (e.g. `Analysis Agent> `) during the analysis phase. It prints formatted intermediate execution results, allowing the user to type free-form natural language feedback (to adjust rules, filters, or code) or type `y`/`yes` to approve and compile the trace.
- **Rationale**: Provides a powerful, user-friendly feedback loop that doesn't restrict the user to binary yes/no choices.

## Risks / Trade-offs

- **[Risk]**: The user could manually modify or delete files inside the hidden `.workflows/` directory.
  - **Mitigation**: Provide warning banners, and handle file-not-found errors gracefully with user-friendly CLI messages.
- **[Risk]**: Generated Python code safety inside saved traces.
  - **Mitigation**: The `PythonRunnerExecutor` executes with strict AST parsing to block unsafe imports (`os`, `sys`, `subprocess`, etc.) during deterministic execution.
