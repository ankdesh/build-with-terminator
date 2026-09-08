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
    assert "execution_result" in event_types
    assert "done" in event_types
    assert mock_llm.call_count == 2

    # Check execution result has retries_attempted == 1
    exec_result_event = next(e for e in events if e["event"] == "execution_result")
    assert exec_result_event["data"]["retries_attempted"] == 1
    assert exec_result_event["data"]["success"] is True
