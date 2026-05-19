# cli-interface

## Purpose
TBD: Core capability handling command-line arguments and subcommands (analysis, execute).

## Requirements

### Requirement: Analysis Mode Invocation
The CLI SHALL provide an `analysis` command that accepts a text-based request and a target log file.

#### Scenario: User requests open-ended analysis
- **WHEN** the user invokes `analysis --request "find errors" --log app.log`
- **THEN** the CLI passes the request to the LLM Planner and saves the generated YAML workflow trace

### Requirement: Execution Mode Invocation
The CLI SHALL provide an `execute` command that accepts a YAML workflow file and a target log file.

#### Scenario: User executes a pre-defined workflow
- **WHEN** the user invokes `execute --workflow workflows/error_scan.yaml --log app.log`
- **THEN** the CLI parses the YAML and invokes the Orchestrator with the parsed instruction trace
