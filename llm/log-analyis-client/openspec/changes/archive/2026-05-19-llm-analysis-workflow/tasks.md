## 1. Orchestrator Context Implementation

- [x] 1.1 Update `src/orchestrator.py` `__init__` to initialize `self.context = {}`.
- [x] 1.2 Update `_instruction_consumer` to store execution results into `self.context[output_key]` if `output_key` is present in the instruction dictionary.
- [x] 1.3 Create a `_resolve_args` helper in Orchestrator that recursively scans instruction arguments and replaces `$variable.path` strings with actual objects from `self.context`. Update `_instruction_consumer` to use it before calling executor.


## 2. Executor Modifications & Additions

- [x] 2.1 Update `LogparserExecutor` to add `get_parsed_info` capability that returns `{"df": self._parsed_df, "templates": self._templates_df.to_dict("records"), "schema": list(self._parsed_df.columns)}`.
- [x] 2.2 Create `src/executors/llm.py` with `LlmExecutor`. Implement `gen_pycode_fromtemplate` capability using `src/utils/llm_client.py`. Add prompt logic that accepts `df_schema`, `templates`, and `query`, and uses a regex to extract the ````python...```` code block.
- [x] 2.3 Create `src/executors/python_runner.py` with `PythonRunnerExecutor`. Implement `execute_python` capability. Add AST parsing to block `os`, `sys`, `subprocess`, etc. Use `exec` with injected `inputs` and capture output.

## 3. Workflow Integration

- [x] 3.1 Update `Orchestrator` to register the new `LlmExecutor` and `PythonRunnerExecutor` in `_load_executors`.
- [x] 3.2 Create a sample workflow file `workflows/llm_analysis.yaml` that orchestrates: parsing logs -> getting parsed info (with `output_key`) -> generating code (referencing context) -> executing python (referencing context).

## 4. Testing & Verification

- [x] 4.1 Run the `workflows/llm_analysis.yaml` workflow using the CLI and verify that it correctly extracts data, generates safe code, executes it, and prints the result.
