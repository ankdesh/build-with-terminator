"""Direct Python code execution engine for pandas/numpy data queries."""

import contextlib
import io
import logging
import time
import traceback
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.exceptions import CodeExecutionError
from backend.models.chat import ChartSpec, ExecutionResult, TableData
from config import MAX_TABLE_PREVIEW_ROWS

logger = logging.getLogger(__name__)


class CodeExecutor:
    """Executes generated Python data manipulation scripts against a pandas DataFrame."""

    def __init__(self, max_table_rows: int = MAX_TABLE_PREVIEW_ROWS) -> None:
        self.max_table_rows = max_table_rows

    def execute_code(
        self,
        code: str,
        df: pd.DataFrame,
        plan: str = "",
        explanation: str = "",
        retries_attempted: int = 0,
        user_query: Optional[str] = None,
    ) -> ExecutionResult:
        """Run Python code with in-memory DataFrame in local scope, extracting visuals and results."""
        start_time = time.perf_counter()
        stdout_buffer = io.StringIO()

        # Clean code block markdown delimiters if present
        clean_code = self._clean_code_string(code)

        # Isolated execution namespace with fresh copy of DataFrame
        exec_globals: Dict[str, Any] = {
            "pd": pd,
            "np": np,
            "df": df.copy(),
            "__builtins__": __builtins__,
        }
        exec_locals: Dict[str, Any] = {}

        try:
            with contextlib.redirect_stdout(stdout_buffer):
                exec(clean_code, exec_globals, exec_locals)
        except ModuleNotFoundError as exc:
            tb = traceback.format_exc()
            missing_module = getattr(exc, "name", str(exc))
            tip = ""
            if missing_module in ("sklearn", "scikit-learn", "scipy"):
                tip = (
                    "\n[Execution Hint] 'sklearn' and 'scipy' are not installed in this air-gapped environment. "
                    "Use pure pandas and numpy instead (e.g. min-max scaling with (x - x.min()) / (x.max() - x.min()), "
                    "z-score with (x - x.mean()) / x.std(), or np.polyfit for regressions)."
                )
            elif missing_module in ("matplotlib", "seaborn", "plotly"):
                tip = (
                    "\n[Execution Hint] Python visualization libraries are not installed. "
                    "Do not import matplotlib/seaborn/plotly. Return an Apache ECharts option tree in chart_spec['option']."
                )
            tb_with_hint = tb + tip
            logger.warning("Code execution failed: %s\nTraceback:\n%s", exc, tb_with_hint)
            raise CodeExecutionError(code=clean_code, traceback_str=tb_with_hint)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.warning("Code execution failed: %s\nTraceback:\n%s", exc, tb)
            raise CodeExecutionError(code=clean_code, traceback_str=tb)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        stdout_output = stdout_buffer.getvalue().strip()

        # Harvest output artifacts from locals
        chart = self._extract_chart_spec(exec_locals)
        table = self._extract_table_data(exec_locals)

        # Do not include data table after plot unless explicitly asked for
        if chart is not None and table is not None and user_query is not None:
            if not self._is_table_requested(user_query, exec_locals):
                table = None

        custom_explanation = exec_locals.get("explanation") or exec_locals.get("summary")
        final_explanation = str(custom_explanation) if custom_explanation else explanation

        return ExecutionResult(
            success=True,
            plan=plan,
            explanation=final_explanation,
            code=clean_code,
            stdout=stdout_output,
            chart=chart,
            table=table,
            error_traceback=None,
            execution_time_ms=round(duration_ms, 2),
            retries_attempted=retries_attempted,
        )

    def _is_table_requested(self, user_query: str, local_scope: Dict[str, Any]) -> bool:
        """Check if user query or local scope explicitly requested tabular data alongside a plot."""
        if local_scope.get("show_table") is True or local_scope.get("include_table") is True:
            return True
        query_lower = user_query.lower()
        table_keywords = [
            "table",
            "raw data",
            "show data",
            "print data",
            "include data",
            "display data",
            "tabular",
            "records",
            "rows",
            "dataframe",
            "both",
        ]
        return any(kw in query_lower for kw in table_keywords)

    def _clean_code_string(self, code: str) -> str:
        """Strip markdown fences (```python ... ```) if included by LLM."""
        code = code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code

    def _extract_chart_spec(self, local_scope: Dict[str, Any]) -> Optional[ChartSpec]:
        """Extract and sanitize native Apache ECharts specification from local scope."""
        chart_obj = local_scope.get("chart_spec") or local_scope.get("echarts_option") or local_scope.get("chart")
        if not isinstance(chart_obj, dict):
            return None

        try:
            # 1. Determine the ECharts option tree
            option: Dict[str, Any] = {}
            if "option" in chart_obj and isinstance(chart_obj["option"], dict):
                option = chart_obj["option"]
            elif "echarts_option" in chart_obj and isinstance(chart_obj["echarts_option"], dict):
                option = chart_obj["echarts_option"]
            else:
                option = chart_obj

            # 2. Extract title & description
            title = str(chart_obj.get("title", "Analysis Chart"))
            if isinstance(option.get("title"), dict) and "text" in option["title"]:
                title = str(option["title"]["text"])
            elif isinstance(option.get("title"), str):
                title = str(option["title"])

            description = chart_obj.get("description")
            if not description and isinstance(option, dict):
                description = option.get("description")

            # 3. Recursively sanitize option tree for JSON transmission
            clean_option = self._sanitize_for_json(option)
            if not isinstance(clean_option, dict):
                return None

            # Must have at least series or dataset to be a valid ECharts spec
            if "series" not in clean_option and "dataset" not in clean_option:
                return None

            return ChartSpec(
                title=title,
                description=str(description) if description else None,
                option=clean_option,
            )
        except Exception as e:
            logger.warning("Could not construct ChartSpec from local scope: %s", e)
            return None

    def _extract_table_data(self, local_scope: Dict[str, Any]) -> Optional[TableData]:
        """Extract tabular output from 'result', 'table_data', or 'output_df'."""
        candidate = None
        for key in ["table_data", "result", "output_df"]:
            if key in local_scope and local_scope[key] is not None:
                candidate = local_scope[key]
                break

        if candidate is None:
            return None

        # If candidate is a pandas DataFrame
        if isinstance(candidate, pd.DataFrame):
            if candidate.empty:
                return None
            limited_df = candidate.head(self.max_table_rows)
            columns = [str(c) for c in limited_df.columns]
            rows = self._sanitize_records(limited_df.to_dict(orient="records"))
            return TableData(
                columns=columns,
                rows=rows,
                total_rows=int(len(candidate))
            )

        # If candidate is a pandas Series
        if isinstance(candidate, pd.Series):
            df_series = candidate.reset_index()
            columns = [str(c) for c in df_series.columns]
            rows = self._sanitize_records(df_series.to_dict(orient="records"))
            return TableData(
                columns=columns,
                rows=rows,
                total_rows=int(len(candidate))
            )

        # If candidate is a list of dicts
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            columns = list(candidate[0].keys())
            rows = self._sanitize_records(candidate[:self.max_table_rows])
            return TableData(
                columns=columns,
                rows=rows,
                total_rows=len(candidate)
            )

        return None

    def _sanitize_for_json(self, val: Any) -> Any:
        """Recursively convert numpy/pandas/datetime types into standard JSON-serializable primitives."""
        if val is None:
            return None
        if isinstance(val, (pd.Series, np.ndarray)) or (hasattr(val, "tolist") and hasattr(val, "__iter__")):
            return [self._sanitize_for_json(x) for x in val.tolist()]
        if isinstance(val, pd.DataFrame):
            return self._sanitize_for_json(val.to_dict(orient="records"))
        if isinstance(val, dict):
            return {str(k): self._sanitize_for_json(v) for k, v in val.items()}
        if isinstance(val, (list, tuple, set)):
            return [self._sanitize_for_json(x) for x in val]

        # Scalar checks
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass

        if isinstance(val, (np.integer, int)):
            return int(val)
        if isinstance(val, (np.floating, float)):
            return None if np.isnan(val) or np.isinf(val) else round(float(val), 4)
        if isinstance(val, (pd.Timestamp, np.datetime64)):
            return str(val)
        return val if isinstance(val, (str, bool)) else str(val)

    def _sanitize_records(self, records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
        """Ensure all values in dict records are JSON-serializable."""
        clean = self._sanitize_for_json(records)
        return clean if isinstance(clean, list) else []
