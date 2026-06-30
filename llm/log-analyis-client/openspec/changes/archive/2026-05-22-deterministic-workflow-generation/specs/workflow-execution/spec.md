# workflow-execution

## MODIFIED Requirements

### Requirement: Parse YAML Traces
The system SHALL parse a valid YAML workflow file into a deterministic sequence of instructions recognized by the Orchestrator.

#### Scenario: Valid YAML trace is parsed
- **WHEN** a syntactically correct YAML trace file is provided
- **THEN** it is translated into a list of Instruction objects or dictionaries

## ADDED Requirements

### Requirement: Final Result Presentation
The system SHALL check the orchestrator's context upon completion. If a `RESULT` key is populated, it SHALL print it prominently as the `Final Answer`. Otherwise, it SHALL print a summary of all output keys.

#### Scenario: Print the RESULT key
- **WHEN** the orchestrator completes a trace and `RESULT` exists in the context
- **THEN** the system prints `Final Answer:` followed by the value of the `RESULT` key

### Requirement: Global Log Path Injection
The system SHALL support removing target log file paths from individual trace instructions. At instruction dispatch time, if an instruction requires a log path and `target_file` is not provided in its arguments, the Orchestrator SHALL automatically inject its configured global `log_path` into the instruction's arguments.

#### Scenario: Target file is injected at runtime
- **WHEN** the orchestrator dispatches an instruction requiring a log file that does not contain a 'target_file' key
- **THEN** the orchestrator injects the global log path into the arguments before passing them to the executor
