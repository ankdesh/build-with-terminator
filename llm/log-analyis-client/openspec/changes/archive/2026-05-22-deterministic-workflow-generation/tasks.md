## 1. Setup and Directory Structures

- [x] 1.1 Create `workflow_templates/` directory to store predefined templates
- [x] 1.2 Create `.workflows/` directory to store generated deterministic traces
- [x] 1.3 Add `.workflows/` to the project's `.gitignore` file to hide it from version control

## 2. CLI Interface & Execution Refactoring

- [x] 2.1 Refactor `src/cli.py` to parse new arguments for `analysis` (like `--output` defaulting to `.workflows/`)
- [x] 2.2 Refactor `src/cli.py` to implement the new execution output logic (look for the `RESULT` key in `self.context` and print as `Final Answer`)
- [x] 2.3 Ensure the `execute` subcommand processes the trace deterministically, making no LLM executor calls at replay time

## 3. Workflow Predefined Templates

- [x] 3.1 Migrate current sample workflows in `workflows/` into `workflow_templates/` as parameterized YAML templates
- [x] 3.2 Add parameter placeholder resolving support (e.g. replacing `{{ log_file }}`) when loading a template

## 4. Interactive Analysis Agent Loop

- [x] 4.1 Implement `AnalysisAgent` in a new module `src/analysis_agent.py`
- [x] 4.2 Integrate the ReAct loop utilizing `execute_llm()` to orchestrate intermediate test runs on the Orchestrator
- [x] 4.3 Implement conversational prompt interface for user feedback loop in the terminal
- [x] 4.4 Implement deterministic trace compiler that takes the approved run trace, converts dynamic LLM steps to static python code, and writes it to `.workflows/` as a clean YAML file

## 5. Verification & Validation

- [x] 5.1 Create unit tests for template loading and variable resolution
- [x] 5.2 Create unit tests for deterministic execution and `RESULT` parsing
- [x] 5.3 Verify the complete interactive flow manually on HDFS and Apache sample log files
