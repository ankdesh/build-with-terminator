"""Out-of-process execution engine for layout repair candidate scripts.

Runs candidate Python scripts in a separate subprocess, captures stdout/stderr logs,
enforces timeouts, and verifies output layout generation.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time
from typing import Final

from .config import DEFAULT_TIMEOUT_SECONDS

EXEC_STATUS_SUCCESS: Final[str] = "success"
EXEC_STATUS_SYNTAX_ERROR: Final[str] = "syntax_error"
EXEC_STATUS_NONZERO_EXIT: Final[str] = "nonzero_exit"
EXEC_STATUS_TIMEOUT: Final[str] = "timeout"
EXEC_STATUS_MISSING_OUTPUT: Final[str] = "missing_output"


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of executing a candidate repair script."""

    status: str
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    output_gds: Path | None
    error_message: str | None = None


class RepairExecutor:
    """Executes layout repair scripts out-of-process and records execution diagnostics."""

    def __init__(
        self,
        candidate_script: Path,
        input_gds: Path,
        output_gds: Path,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        python_bin: str = sys.executable,
    ) -> None:
        """Initialize repair executor with target paths.

        Args:
            candidate_script: Path to Python repair script.
            input_gds: Path to immutable input GDS.
            output_gds: Destination path for patched GDS.
            timeout_seconds: Maximum wall-clock runtime before killing subprocess.
            python_bin: Python executable to run the script.
        """
        self.candidate_script = Path(candidate_script).resolve()
        self.input_gds = Path(input_gds).resolve()
        self.output_gds = Path(output_gds).resolve()
        self.timeout_seconds = timeout_seconds
        self.python_bin = python_bin

    def _check_syntax(self) -> str | None:
        """Perform static Python syntax check on candidate script before execution.

        Returns:
            str | None: Error message if syntax is invalid, None otherwise.
        """
        try:
            source = self.candidate_script.read_text(encoding="utf-8")
            ast.parse(source, filename=str(self.candidate_script))
            return None
        except SyntaxError as exc:
            return f"SyntaxError in {self.candidate_script.name} at line {exc.lineno}: {exc.msg}"
        except Exception as exc:
            return f"Failed to read/parse script: {exc}"

    def execute(self) -> ExecutionResult:
        """Execute candidate script out-of-process and return ExecutionResult."""
        # Check syntax first
        syntax_err = self._check_syntax()
        if syntax_err:
            return ExecutionResult(
                status=EXEC_STATUS_SYNTAX_ERROR,
                exit_code=1,
                duration_seconds=0.0,
                stdout="",
                stderr=syntax_err,
                output_gds=None,
                error_message=syntax_err,
            )

        # Remove prior output file if present
        if self.output_gds.exists():
            self.output_gds.unlink()

        # Build runner command: pass in_gds and out_gds as sys.argv
        # If candidate does not handle sys.argv directly, an inline adapter calls fix_layout if present
        adapter_code = (
            "import sys, runpy\n"
            "in_gds, out_gds = sys.argv[1], sys.argv[2]\n"
            f"mod = runpy.run_path({repr(str(self.candidate_script))}, run_name='__main__')\n"
            "if 'fix_layout' in mod and not sys.argv[0].endswith('patched.gds'):\n"
            "    # If script defines fix_layout but didn't execute it, invoke it\n"
            f"    from pathlib import Path\n"
            "    if not Path(out_gds).exists() or Path(out_gds).stat().st_size == 0:\n"
            "        mod['fix_layout'](in_gds, out_gds)\n"
        )

        cmd = [
            self.python_bin,
            "-c",
            adapter_code,
            str(self.input_gds),
            str(self.output_gds),
        ]

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(self.candidate_script.parent),
            )
            duration = time.perf_counter() - start_time

            if res.returncode != 0:
                return ExecutionResult(
                    status=EXEC_STATUS_NONZERO_EXIT,
                    exit_code=res.returncode,
                    duration_seconds=duration,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    output_gds=None,
                    error_message=f"Process exited with code {res.returncode}: {res.stderr.strip()}",
                )

            # Check if output GDS was materialized and is non-empty
            if not self.output_gds.exists() or self.output_gds.stat().st_size == 0:
                return ExecutionResult(
                    status=EXEC_STATUS_MISSING_OUTPUT,
                    exit_code=res.returncode,
                    duration_seconds=duration,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    output_gds=None,
                    error_message=f"Script completed with code 0 but '{self.output_gds}' was not created or is 0 bytes.",
                )

            return ExecutionResult(
                status=EXEC_STATUS_SUCCESS,
                exit_code=0,
                duration_seconds=duration,
                stdout=res.stdout,
                stderr=res.stderr,
                output_gds=self.output_gds,
                error_message=None,
            )

        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start_time
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return ExecutionResult(
                status=EXEC_STATUS_TIMEOUT,
                exit_code=None,
                duration_seconds=duration,
                stdout=stdout,
                stderr=f"Execution timed out after {self.timeout_seconds}s.\n{stderr}",
                output_gds=None,
                error_message=f"Process exceeded timeout limit of {self.timeout_seconds}s.",
            )
