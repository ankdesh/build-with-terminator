"""Unit tests for CodeExecutor service."""

import numpy as np
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
    'title': 'Average kWh by Zone',
    'description': 'Mean kWh aggregated by building zone',
    'option': {
        'xAxis': {'type': 'category', 'data': result['zone'].tolist()},
        'yAxis': {'type': 'value', 'name': 'Mean kWh'},
        'series': [{'type': 'bar', 'data': result['kwh'].tolist()}],
    }
}
explanation = "Zone-B shows highest average usage."
"""
    res = executor.execute_code(code, sample_df, plan="Calculate average kWh per zone")

    assert res.success is True
    assert res.table is not None
    assert len(res.table.rows) == 3
    assert "zone" in res.table.columns
    assert res.chart is not None
    assert res.chart.title == "Average kWh by Zone"
    assert res.chart.description == "Mean kWh aggregated by building zone"
    assert "series" in res.chart.option
    assert res.chart.option["series"][0]["type"] == "bar"
    assert len(res.chart.option["series"][0]["data"]) == 3
    assert res.explanation == "Zone-B shows highest average usage."
    assert res.execution_time_ms > 0


def test_code_executor_dual_axis_chart(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    code = """
agg = df.groupby('zone').agg({'kwh': 'mean', 'occupancy': 'mean'}).reset_index()
echarts_option = {
    'title': {'text': 'kWh Usage and Occupancy by Zone'},
    'tooltip': {'trigger': 'axis'},
    'xAxis': {'type': 'category', 'data': agg['zone'].tolist()},
    'yAxis': [
        {'type': 'value', 'name': 'kWh', 'position': 'left'},
        {'type': 'value', 'name': 'People', 'position': 'right'},
    ],
    'series': [
        {'name': 'kWh', 'type': 'bar', 'data': agg['kwh'].tolist()},
        {'name': 'Occupancy', 'type': 'line', 'yAxisIndex': 1, 'data': agg['occupancy'].tolist()},
    ]
}
result = agg
"""
    res = executor.execute_code(code, sample_df)
    assert res.success is True
    assert res.chart is not None
    assert res.chart.title == "kWh Usage and Occupancy by Zone"
    assert len(res.chart.option["yAxis"]) == 2
    assert len(res.chart.option["series"]) == 2
    assert res.chart.option["series"][0]["type"] == "bar"
    assert res.chart.option["series"][1]["type"] == "line"


def test_code_executor_sanitizes_numpy_and_series(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    code = """
chart_spec = {
    'title': 'Numpy sanitization test',
    'option': {
        'xAxis': {'data': df['zone'].values}, # numpy array
        'series': [{
            'type': 'line',
            'data': df['kwh'], # pandas Series
            'markLine': {'data': [{'yAxis': np.float64(15.0)}]}
        }]
    }
}
"""
    res = executor.execute_code(code, sample_df)
    assert res.success is True
    assert res.chart is not None
    # Verify numpy array and pandas series are converted to native lists and floats
    assert isinstance(res.chart.option["xAxis"]["data"], list)
    assert isinstance(res.chart.option["series"][0]["data"], list)
    assert isinstance(res.chart.option["series"][0]["markLine"]["data"][0]["yAxis"], float)


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


def test_code_executor_sklearn_error_hint(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    code = "import sklearn\nresult = df.head(1)"
    with pytest.raises(CodeExecutionError) as exc_info:
        executor.execute_code(code, sample_df)

    assert "ModuleNotFoundError" in exc_info.value.traceback_str
    assert "Use pure pandas and numpy instead" in exc_info.value.traceback_str


def test_code_executor_suppresses_table_after_plot_unless_asked(sample_df: pd.DataFrame) -> None:
    executor = CodeExecutor()
    code = """
result = df.groupby('zone')['kwh'].mean().reset_index()
chart_spec = {
    'title': 'Usage Chart',
    'option': {
        'xAxis': {'data': result['zone'].tolist()},
        'series': [{'type': 'bar', 'data': result['kwh'].tolist()}]
    }
}
"""
    # 1. Plot-only query suppresses table
    res_plot = executor.execute_code(code, sample_df, user_query="plot kwh by zone")
    assert res_plot.success is True
    assert res_plot.chart is not None
    assert res_plot.table is None

    # 2. Query asking for table keeps table
    res_with_table = executor.execute_code(code, sample_df, user_query="plot kwh by zone and show table")
    assert res_with_table.success is True
    assert res_with_table.chart is not None
    assert res_with_table.table is not None

    # 3. Non-chart query keeps table
    code_no_chart = "result = df.groupby('zone')['kwh'].mean().reset_index()"
    res_table_only = executor.execute_code(code_no_chart, sample_df, user_query="calculate average usage by zone")
    assert res_table_only.success is True
    assert res_table_only.chart is None
    assert res_table_only.table is not None
