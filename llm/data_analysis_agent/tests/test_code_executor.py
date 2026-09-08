"""Unit tests for CodeExecutor service."""

import pandas as pd
import pytest
from backend.exceptions import CodeExecutionError
from backend.services.code_executor import CodeExecutor


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "zone": ["Zone-A", "Zone-B", "Zone-C", "Zone-A", "Zone-B"],
        "kwh": [10.5, 20.0, 15.2, 12.8, 22.1],
        "occupancy": [5, 10, 2, 6, 12],
    })


def test_code_executor_aggregations(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    code = """
result = df.groupby('zone')['kwh'].mean().reset_index()
chart_spec = {
    'chart_type': 'bar',
    'title': 'Average kWh by Zone',
    'x_key': 'zone',
    'series': [{'key': 'kwh', 'name': 'Mean kWh'}],
    'data': result.to_dict(orient='records')
}
explanation = "Zone-B shows highest average usage."
"""
    res = executor.execute_code(code, sample_df, plan="Calculate average kWh per zone")

    assert res.success is True
    assert res.table is not None
    assert len(res.table.rows) == 3
    assert "zone" in res.table.columns
    assert res.chart is not None
    assert res.chart.chart_type == "bar"
    assert len(res.chart.data) == 3
    assert res.explanation == "Zone-B shows highest average usage."
    assert res.execution_time_ms > 0


def test_code_executor_catches_error(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    bad_code = "result = df['non_existent_col'] + 10"

    with pytest.raises(CodeExecutionError) as exc_info:
        executor.execute_code(bad_code, sample_df)

    assert "KeyError" in exc_info.value.traceback_str


def test_code_executor_cleans_markdown_fences(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    fenced_code = "```python\nresult = df.head(2)\n```"
    res = executor.execute_code(fenced_code, sample_df)
    assert res.success is True
    assert res.table is not None
    assert len(res.table.rows) == 2
