"""Unit tests for AgentService orchestration and retry logic."""

from unittest.mock import AsyncMock
import pandas as pd
import pytest

from backend.models.chat import ChatMessage
from backend.models.profile import ColumnSummary, DataProfile, DataQualityReport
from backend.services.agent_service import AgentService
from backend.services.code_executor import CodeExecutor


@pytest.fixture
def mock_profile() -> DataProfile:
    return DataProfile(
        session_id="sess-123",
        dataset_name="metrics.csv",
        row_count=100,
        column_count=2,
        columns=[
            ColumnSummary(name="zone", data_type="object", column_description="Building zone"),
            ColumnSummary(name="kwh", data_type="float64", column_description="Kilowatt hours", mean_value=15.0),
        ],
        preview_rows=[{"zone": "A", "kwh": 12.0}],
        quality_report=DataQualityReport(flags=[]),
    )


@pytest.mark.asyncio
async def test_agent_retry_and_self_correction(mock_profile: DataProfile) -> None:
    df = pd.DataFrame({"zone": ["A", "B"], "kwh": [10.0, 20.0]})

    # First call returns bad code with wrong column name 'kw_usage';
    # Second call returns corrected code with 'kwh'.
    bad_response = {
        "plan": "Calculate mean usage",
        "code": "result = df['kw_usage'].mean()",
        "explanation": "Calculated mean usage."
    }
    good_response = {
        "plan": "Calculate mean usage correctly",
        "code": "result = df[['zone', 'kwh']].copy()\nexplanation = 'The average usage is 15 kWh.'",
        "explanation": "The average usage is 15 kWh."
    }

    agent = AgentService(code_executor=CodeExecutor())
    # Mock LLM call to simulate retry recovery
    mock_llm = AsyncMock(side_effect=[bad_response, good_response])
    agent._call_llm = mock_llm  # type: ignore[assignment]

    events = []
    async for event in agent.run_analysis_stream(
        session_id="sess-123",
        user_query="What is the average usage?",
        df=df,
        profile=mock_profile,
        chat_history=[],
    ):
        events.append(event)

    event_types = [e["event"] for e in events]

    assert "plan" in event_types
    assert "code" in event_types
    assert "log" in event_types
    assert "execution_result" in event_types
    assert "done" in event_types
    assert mock_llm.call_count == 2

    # Check execution result has retries_attempted == 1 and step_logs populated
    exec_result_event = next(e for e in events if e["event"] == "execution_result")
    assert exec_result_event["data"]["retries_attempted"] == 1
    assert exec_result_event["data"]["success"] is True
    assert isinstance(exec_result_event["data"]["step_logs"], list)
    assert len(exec_result_event["data"]["step_logs"]) > 0


@pytest.mark.asyncio
async def test_synthesize_explanation() -> None:
    """Verify that _synthesize_explanation formats execution outputs with LLM."""
    agent = AgentService(code_executor=CodeExecutor())
    mock_call_text = AsyncMock(return_value="The building consumed an average of 42 kWh.")
    agent._call_external_text = mock_call_text  # type: ignore[assignment]

    from backend.models.chat import ExecutionResult, TableData
    exec_result = ExecutionResult(
        success=True,
        plan="Compute mean",
        explanation="Initial explanation",
        code="result = 42",
        stdout="Mean: 42",
        table=TableData(columns=["val"], rows=[{"val": 42}], total_rows=1),
        execution_time_ms=10.0,
        retries_attempted=0,
    )

    synthesized = await agent._synthesize_explanation(
        user_query="What is the average?",
        exec_result=exec_result,
        initial_explanation="Initial explanation",
    )

    assert synthesized == "The building consumed an average of 42 kWh."
    mock_call_text.assert_awaited_once()

