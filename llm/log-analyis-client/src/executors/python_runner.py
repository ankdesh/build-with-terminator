import ast
import contextlib
import io
from typing import Any

from executors.base import BaseExecutor


class PythonRunnerExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "python_runner"

    def capabilities(self) -> list[str]:
        return ["execute_python"]

    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        if action == "execute_python":
            return self._execute_python(args)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _execute_python(self, args: dict[str, Any]) -> dict[str, Any]:
        code = args.get("code")
        inputs = args.get("inputs", {})

        if not code:
            raise ValueError("code is required for execute_python action.")

        # AST analysis for basic guardrails
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self._verify_module(name.name)
                elif isinstance(node, ast.ImportFrom):
                    self._verify_module(node.module)
        except SyntaxError as e:
            return {"status": "failure", "error": f"Syntax error in code: {e}"}
        except ValueError as e:
            return {"status": "failure", "error": str(e)}

        # Inject inputs into local scope
        local_scope = dict(inputs)
        # Pre-import safe libraries to facilitate coding
        import pandas as pd

        local_scope["pd"] = pd

        # Capture stdout & stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                # Run execution
                exec(code, {}, local_scope)

            # Extract RESULT variable if it exists
            result_val = local_scope.get("RESULT", None)

            return {
                "status": "success",
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "result": result_val,
            }
        except Exception as e:
            return {
                "status": "failure",
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue() + f"\nRuntime Exception: {e}",
                "error": str(e),
            }

    def _verify_module(self, module_name: str):
        if not module_name:
            return

        banned = {"os", "sys", "subprocess", "pathlib", "shutil", "builtins", "requests", "urllib", "socket"}
        # check base module name (e.g. os.path -> os)
        base_mod = module_name.split(".")[0]
        if base_mod in banned:
            raise ValueError(f"Security Policy Violation: Import of module '{module_name}' is blocked.")
