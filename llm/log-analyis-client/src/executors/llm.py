import re
from typing import Any

from executors.base import BaseExecutor
from utils.llm_client import execute_llm


class LlmExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "llm"

    def capabilities(self) -> list[str]:
        return ["gen_pycode_fromtemplate"]

    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        if action == "gen_pycode_fromtemplate":
            return self._gen_pycode_fromtemplate(args)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _gen_pycode_fromtemplate(self, args: dict[str, Any]) -> dict[str, Any]:
        df_schema = args.get("df_schema")
        templates = args.get("templates")
        query = args.get("query")
        model = args.get("model", "hf.co/unsloth/gpt-oss-20b-GGUF:Q4_K_M")

        if not df_schema or not templates or not query:
            raise ValueError("df_schema, templates, and query are all required args.")

        # Build prompt
        prompt = f"""System: You are an expert Python data analyst. You are provided with a pandas DataFrame named `df` containing parsed log data.

### DataFrame Context
The `df` contains the following columns: {df_schema}.
- `Content`: The raw, original log message.
- `EventId`: A unique hash identifying the log template.
- `EventTemplate`: The static structure of the log message, where `<*>` represents dynamic variables.
- `ParameterList`: A Python list of the dynamic variables extracted from the `Content` that replace the `<*>` in the template.

### Templates
For reference, here are the top templates in this log file:
{templates}

### Task
User Query: "{query}"

Write a Python script to answer the user query using the `df`.

### Rules
1. Assume `import pandas as pd` and `import ast` are already imported.
2. Assume the variable `df` is already loaded in your environment.
3. If you need to search for specific events, filter by `EventId` rather than doing expensive string matching on `Content`.
4. If you need to analyze variables, extract them from the `ParameterList` column (remember it is a list of strings).
5. Assign your final answer to a variable named `RESULT`. You may also print intermediate steps.
6. Do NOT use `os`, `sys`, or network calls.
7. Output ONLY valid Python code inside ```python ... ``` blocks. Do not explain your code.
"""

        response = execute_llm(prompt, model=model)

        # Extract python code block
        code_match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if code_match:
            code = code_match.group(1).strip()
        else:
            # Fallback: if no markdown blocks, maybe it returned the code directly
            code = response.strip()

        return {"status": "success", "code": code, "raw_response": response}
