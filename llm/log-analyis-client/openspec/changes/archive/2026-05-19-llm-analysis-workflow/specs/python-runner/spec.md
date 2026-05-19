## ADDED Requirements

### Requirement: Python Runner Executor
The system SHALL provide a `PythonRunnerExecutor` capable of executing Python strings securely and returning the execution outputs.

#### Scenario: Execute Code with Local Variables
- **WHEN** an instruction with `action: "execute_python"` is dispatched with a `code` string and a dictionary of `inputs` (e.g., `df`)
- **THEN** the executor securely evaluates the code within a restricted local scope containing the `inputs`, captures any `sys.stdout` and `sys.stderr` output, extracts the `RESULT` variable if defined, and returns these as a dictionary.

### Requirement: Safe Execution Guardrails
The executor SHALL perform static analysis on the provided code before execution to prevent malicious or unsafe operations.

#### Scenario: Block unauthorized modules
- **WHEN** the code string contains imports for `os`, `sys`, or `subprocess`
- **THEN** the executor raises a ValueError before execution, preventing the script from running.
