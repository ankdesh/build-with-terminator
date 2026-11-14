"""Unit and integration tests for AgentService diagnostics, confidence badges, and streaming enrichment."""

from unittest.mock import AsyncMock
import pandas as pd
import pytest

from backend.models.chat import ChatMessage, ExecutionResult, TableData, ChartSpec
from backend.models.profile import ColumnSummary, DataProfile, DataQualityReport
from backend.services.agent_service import AgentService, SYSTEM_PROMPT
from backend.services.code_executor import CodeExecutor
from backend.services.jargon_translator import JargonTranslator, COLOR_CORAL_RED, COLOR_MUTED_SLATE


@pytest.fixture
def sample_profile() -> DataProfile:
    return DataProfile(
        session_id="diag-sess-1",
        dataset_name="sales.csv",
        row_count=200,
        column_count=3,
        columns=[
            ColumnSummary(name="region", data_type="object", column_description="Sales region"),
            ColumnSummary(name="sales", data_type="float64", column_description="Sales in thousands", mean_value=50.0),
            ColumnSummary(name="discount", data_type="float64", column_description="Discount percent", mean_value=0.15),
        ],
        preview_rows=[{"region": "North", "sales": 45.0, "discount": 0.1}],
        quality_report=DataQualityReport(flags=[]),
    )


@pytest.mark.asyncio
async def test_agent_service_enrichment_streaming(sample_profile: DataProfile) -> None:
    """Verifies that AgentService.run_analysis_stream enriches ExecutionResult with badges and chips."""
    df = pd.DataFrame({
        "region": ["North", "South", "East", "West"],
        "sales": [40.0, 15.0, 60.0, 55.0],
    })

    # Code outputs stdout containing p-value and a bar chart
    mock_llm_response = {
        "plan": "Analyze regional sales drop",
        "code": (
            "print('Statistical test: p_value = 0.002, sample_size = 150')\n"
            "chart_spec = {\n"
            "    'title': 'Regional Sales Drop (R²=0.88)',\n"
            "    'description': 'Culprit segment identified (p < 0.01)',\n"
            "    'option': {\n"
            "        'series': [{'type': 'bar', 'data': [{'value': 40}, {'value': 15}, {'value': 60}, {'value': 55}]}]\n"
            "    }\n"
            "}\n"
        ),
        "explanation": "Identified significant dip in South region."
    }

    agent = AgentService(code_executor=CodeExecutor())
    mock_llm = AsyncMock(return_value=mock_llm_response)
    agent._call_llm = mock_llm  # type: ignore[assignment]
    agent._synthesize_explanation = AsyncMock(return_value="Plain English: Sales dropped in South region.")  # type: ignore[assignment]

    events = []
    async for event in agent.run_analysis_stream(
        session_id="diag-sess-1",
        user_query="Why did sales drop in South?",
        df=df,
        profile=sample_profile,
        chat_history=[],
    ):
        events.append(event)

    event_types = [e["event"] for e in events]
    assert "plan" in event_types
    assert "code" in event_types
    assert "execution_result" in event_types
    assert "done" in event_types

    exec_event = next(e for e in events if e["event"] == "execution_result")
    data = exec_event["data"]

    # Verify ConfidenceBadges
    assert "confidence_badges" in data
    assert len(data["confidence_badges"]) >= 1
    top_badge = data["confidence_badges"][0]
    assert top_badge["level"] == "high"
    assert top_badge["icon"] == "🟢"
    assert "High Confidence Finding" in top_badge["title"]

    # Verify FollowUpChips
    assert "follow_up_chips" in data
    assert len(data["follow_up_chips"]) >= 3
    chip_labels = [c["label"] for c in data["follow_up_chips"]]
    assert "[🔍 Show me which customer group caused this]" in chip_labels
    assert "[🎛️ Simulate how to recover this drop]" in chip_labels
    assert "[🎯 3 recipes to fix top red bar]" in chip_labels

    # Verify 3-Layer Visual Hierarchy on chart option
    assert data["chart"] is not None
    chart_opt = data["chart"]["option"]
    assert "markLine" in chart_opt["series"][0]
    # Sanitized Layer 3 title
    assert "R²=0.88" not in chart_opt["title"]["text"]
    assert "88% variance explained" in chart_opt["title"]["text"]

    # Verify step logs mention badge and chips
    log_messages = [e["data"] for e in events if e["event"] == "log"]
    assert any("Assigned confidence badge" in m for m in log_messages)
    assert any("contextual follow-up action chips" in m for m in log_messages)


@pytest.mark.asyncio
async def test_agent_service_handles_table_only_execution(sample_profile: DataProfile) -> None:
    """Verifies that non-chart execution still generates badges and chips gracefully."""
    df = pd.DataFrame({"sales": [10.0, 20.0, 30.0]})

    mock_llm_response = {
        "plan": "Calculate statistics",
        "code": "result = pd.DataFrame({'mean': [df['sales'].mean()]})\nprint('sample_size = 50')",
        "explanation": "Calculated summary mean."
    }

    agent = AgentService(code_executor=CodeExecutor())
    agent._call_llm = AsyncMock(return_value=mock_llm_response)  # type: ignore[assignment]
    agent._synthesize_explanation = AsyncMock(return_value="The average sales is 20.")  # type: ignore[assignment]

    events = []
    async for event in agent.run_analysis_stream(
        session_id="diag-sess-1",
        user_query="What is the average sales?",
        df=df,
        profile=sample_profile,
        chat_history=[],
    ):
        events.append(event)

    exec_event = next(e for e in events if e["event"] == "execution_result")
    data = exec_event["data"]

    assert data["chart"] is None
    assert len(data["confidence_badges"]) >= 1
    assert len(data["follow_up_chips"]) >= 1


@pytest.mark.asyncio
async def test_agent_service_custom_translator_injection() -> None:
    """Verifies that AgentService accepts an injected JargonTranslator instance."""
    custom_translator = JargonTranslator()
    agent = AgentService(code_executor=CodeExecutor(), jargon_translator=custom_translator)
    assert agent.jargon_translator is custom_translator


def test_zero_plotting_binaries_in_prompt_and_imports() -> None:
    """Verifies architectural guarantee: zero matplotlib/seaborn/plotly."""
    # Check SYSTEM_PROMPT
    assert "matplotlib" in SYSTEM_PROMPT.lower()
    assert "seaborn" in SYSTEM_PROMPT.lower()
    assert "plotly" in SYSTEM_PROMPT.lower()
    assert "do not import `matplotlib`, `seaborn`, or `plotly`" in SYSTEM_PROMPT.lower()

    # Check that modules do not import forbidden binaries
    import backend.services.agent_service as agent_mod
    import backend.services.jargon_translator as translator_mod

    for mod in [agent_mod, translator_mod]:
        mod_dict = mod.__dict__
        assert "matplotlib" not in mod_dict
        assert "plt" not in mod_dict
        assert "seaborn" not in mod_dict
        assert "sns" not in mod_dict
        assert "plotly" not in mod_dict
