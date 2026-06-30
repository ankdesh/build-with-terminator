# cli-interface

## MODIFIED Requirements

### Requirement: Analysis Mode Invocation
The CLI SHALL provide an `analysis` command that accepts a text-based request, a target log file, and an optional output path.

#### Scenario: User requests open-ended analysis with interactive loop
- **WHEN** the user invokes `analysis --request "find errors" --log app.log --output .workflows/my_workflow.yaml`
- **THEN** the CLI starts the interactive LLM analysis agent loop and writes the approved deterministic trace to the specified output path

### Requirement: Execution Mode Invocation
The CLI SHALL provide an `execute` command that accepts a workflow file or slug and a target log file.

#### Scenario: User executes a pre-defined workflow
- **WHEN** the user invokes `execute --workflow .workflows/my_workflow.yaml --log app.log`
- **THEN** the CLI parses the YAML and invokes the Orchestrator to execute the parsed deterministic instruction trace non-interactively without any LLM requests
