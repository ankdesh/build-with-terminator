# llm-execution Specification

## Purpose
TBD - created by archiving change llm-analysis-workflow. Update Purpose after archive.
## Requirements
### Requirement: LLM Executor Implementation
The system SHALL provide an `LlmExecutor` capable of calling local LLM models to generate text and code based on prompt configurations.

#### Scenario: Generate Python Code
- **WHEN** an instruction with `action: "gen_pycode_fromtemplate"` is dispatched to the `llm` executor, providing inputs (like dataframe schema and templates)
- **THEN** the executor constructs a prompt, queries the LLM, extracts the generated Python code from the response (via markdown parsing), and returns the generated code string

