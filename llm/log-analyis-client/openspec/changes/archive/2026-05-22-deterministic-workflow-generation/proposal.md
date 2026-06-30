## Why

The `log-analysis-client` currently runs dynamic, LLM-driven workflows that contain runtime LLM code-generation steps. This introduces runtime latency, high API inference costs, and unpredictability during workflow execution. By decoupling the workflow design (interactive, LLM-driven Analysis Phase) from workflow execution (completely offline, deterministic Execution Phase), we can ensure that once a workflow is successfully generated and verified with the user, it can be replayed repeatedly on any target log file with 100% determinism and zero LLM calls.

## What Changes

- **Interactive Analysis command (`analysis`)**:
  - Implements a conversational LLM-based ReAct loop in the control plane that takes a log file and a natural language query.
  - The LLM performs two distinct roles during this phase:
    1. **ReAct Control Loop**: Orchestrates template selection, analyzes intermediate outputs, interacts with the user, and processes conversational feedback.
    2. **Dynamic Executor Stages**: Runs dynamic `llm` executor instructions (e.g., Python code-generation `gen_pycode_fromtemplate`, parsing, or structural extraction) defined inside the template or synthesized on-the-fly.
  - The agent executes these candidate instructions in the background, prints the output to the user, and gathers feedback.
  - If approved, the agent compiles a fully resolved, 100% deterministic workflow trace (converting dynamic LLM executor stages into static ones, such as a python runner with the generated code embedded) and saves it to a hidden `.workflows/` directory in the project root.
- **Deterministic Execution command (`execute`)**:
  - Executes the concrete workflow trace YAML from `--workflow` fully offline and deterministically without any LLM calls.
  - If a `RESULT` key is populated in the final context, it prints it prominently as the `Final Answer`. Otherwise, it prints a summary of the context outputs.
- **Workflow Templates**:
  - Predefined parameterized templates stored in an internal `workflow_templates/` directory using the standard YAML workflow format.

## Capabilities

### New Capabilities
- `workflow-templates`: Predefined workflow templates used by the Analysis agent to synthesize deterministic workflow traces.
- `interactive-analysis`: LLM-based ReAct loop that interacts with the user, verifies intermediate execution outputs, and generates deterministic workflow traces.

### Modified Capabilities
- `cli-interface`: Updated subcommands for `analysis` (supporting interactive conversational loops and `--output`) and `execute` (fully deterministic, reading from `.workflows/` directory by default).
- `workflow-execution`: Execute workflow traces fully deterministically and extract final `RESULT` values.

## Impact

- `src/cli.py`: Complete implementation of interactive analysis loop and update to execute command.
- `src/orchestrator.py`: Integration with the interactive analysis runner and clean result display from final context.
- `workflow_templates/`: Storing internal templates.
- `.workflows/` (hidden, gitignored): Default directory for saving generated deterministic traces.
