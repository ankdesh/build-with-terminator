# interactive-analysis

## Purpose
TBD: Core capability to orchestrate log analysis through an interactive ReAct loop with LLMs and deterministic trace compilation.

## Requirements

### Requirement: Interactive ReAct Analysis Loop
The system SHALL provide an interactive conversational LLM-based ReAct agent loop for analyzing log files based on user requests.

#### Scenario: Agent analyzes log and verifies output
- **WHEN** the user starts the analysis loop with a log file and a query
- **THEN** the agent dynamically synthesizes a candidate trace, runs it in the background, prints the intermediate outputs to the user, and waits for user confirmation/feedback

### Requirement: Deterministic Trace Generation and Saving
The system SHALL compile the successful interactive trace into a fully resolved, 100% deterministic workflow trace, resolving dynamic `llm` executor instructions into static actions (such as static `execute_python` with generated code blocks), and saving it to the `.workflows/` directory.

#### Scenario: User approves analysis results and trace is saved
- **WHEN** the user confirms that the displayed analysis results are correct
- **THEN** the system compiles the trace (saving generated python code blocks in static `execute_python` instructions, and replacing dynamic `llm` executor steps with their resolved static counterpart results) and writes it as a YAML file inside the hidden `.workflows/` directory
