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
from backend.models.chat import ChartSeries, ChartSpec, ExecutionResult, TableData
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
        retries_attempted: int = 0
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
        except Exception as exc:
            tb = traceback.format_exc()
            logger.warning("Code execution failed: %s\nTraceback:\n%s", exc, tb)
            raise CodeExecutionError(code=clean_code, traceback_str=tb)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        stdout_output = stdout_buffer.getvalue().strip()

        # Harvest output artifacts from locals
        chart = self._extract_chart_spec(exec_locals)
        table = self._extract_table_data(exec_locals)
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
        """Extract and sanitize chart specification dictionary from local scope."""
        chart_obj = local_scope.get("chart_spec") or local_scope.get("chart")
        if not isinstance(chart_obj, dict):
            return None

        try:
            raw_type = str(chart_obj.get("chart_type", chart_obj.get("type", "bar"))).lower()
            if raw_type not in ["bar", "line", "area", "pie", "scatter"]:
                raw_type = "bar"

            title = str(chart_obj.get("title", "Analysis Chart"))
            x_key = str(chart_obj.get("x_key", chart_obj.get("xAxis", "x")))
            raw_series = chart_obj.get("series", [])
            raw_data = chart_obj.get("data", [])

            # Handle if series is a list of strings
            series_list: List[ChartSeries] = []
            if isinstance(raw_series, list):
                for s in raw_series:
                    if isinstance(s, dict):
                        series_list.append(
                            ChartSeries(
                                key=str(s.get("key", "")),
                                name=str(s.get("name", s.get("key", ""))),
                                color=s.get("color")
                            )
                        )
                    elif isinstance(s, str):
                        series_list.append(ChartSeries(key=s, name=s))

            # Handle if data is a pandas DataFrame
            data_list: List[Dict[str, Any]] = []
            if isinstance(raw_data, pd.DataFrame):
                data_list = self._sanitize_records(raw_data.to_dict(orient="records"))
            elif isinstance(raw_data, list):
                data_list = self._sanitize_records(raw_data)

            if not data_list:
                return None

            return ChartSpec(
                chart_type=raw_type,  # type: ignore[arg-type]
                title=title,
                x_key=x_key,
                series=series_list,
                data=data_list,
                description=chart_obj.get("description"),
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

    def _sanitize_records(self, records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
        """Ensure all values in dict records are JSON-serializable."""
        sanitized: List[Dict[str, Any]] = []
        for r in records:
            clean_r: Dict[str, Any] = {}
            for k, v in r.items():
                if v is None or pd.isna(v):
                    clean_r[str(k)] = None
                elif isinstance(v, (np.integer, int)):
                    clean_r[str(k)] = int(v)
                elif isinstance(v, (np.floating, float)):
                    clean_r[str(k)] = None if np.isnan(v) or np.isinf(v) else round(float(v), 4)
                elif isinstance(v, (pd.Timestamp, np.datetime64)):
                    clean_r[str(k)] = str(v)
                else:
                    clean_r[str(k)] = str(v)
            sanitized.append(clean_r)
        return sanitized
