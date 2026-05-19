## ADDED Requirements

### Requirement: Orchestrator Context Storage
The orchestrator SHALL allow instructions to specify an `output_key` argument, which instructs the orchestrator to save the result of the instruction to a shared Context Dictionary under that key.

#### Scenario: Storing instruction output
- **WHEN** an instruction executes successfully and provides `output_key: "parsed_data"`
- **THEN** the orchestrator stores the entire dictionary result of that execution into its context under the key `parsed_data`

### Requirement: Context Variable Interpolation
The orchestrator SHALL resolve string arguments prefixed with `$` by looking up the corresponding value in its Context Dictionary before passing the arguments to the Executor. Support nested property access (e.g., `$parsed_data.schema`).

#### Scenario: Injecting variables into an instruction
- **WHEN** an instruction argument is defined as `df: "$parsed_data.df"`
- **THEN** the orchestrator extracts the `df` object from `context["parsed_data"]` and injects it into the executor's arguments as the literal object reference
