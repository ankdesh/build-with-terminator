import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from cli import handle_analysis, handle_execute, parse_yaml_workflow


def test_parse_yaml_workflow_valid():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump([{"action": "scan", "executor": "scanner"}], f)
        temp_path = f.name

    try:
        result = parse_yaml_workflow(temp_path)
        assert len(result) == 1
        assert result[0]["action"] == "scan"
    finally:
        os.unlink(temp_path)


def test_parse_yaml_workflow_invalid_format():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump({"not": "a list"}, f)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="must be a YAML list"):
            parse_yaml_workflow(temp_path)
    finally:
        os.unlink(temp_path)


def test_parse_yaml_workflow_missing_keys():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump([{"action": "scan"}], f)  # missing executor
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="missing required key: 'executor'"):
            parse_yaml_workflow(temp_path)
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
@patch("cli.Orchestrator")
async def test_handle_execute(mock_orchestrator_class):
    mock_orchestrator = AsyncMock()
    mock_orchestrator.context = {}
    mock_orchestrator_class.return_value = mock_orchestrator

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump([{"action": "test", "executor": "tester"}], f)
        temp_path = f.name

    try:
        args = MagicMock()
        args.workflow = temp_path
        args.log = "dummy.log"

        await handle_execute(args)

        mock_orchestrator_class.assert_called_once_with("dummy.log")
        mock_orchestrator.start.assert_awaited_once()
        mock_orchestrator.send_instruction.assert_awaited_once_with({"action": "test", "executor": "tester"})
        mock_orchestrator.stop.assert_awaited_once()
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
@patch("cli.AnalysisAgent")
async def test_handle_analysis(mock_agent_class):
    mock_agent = AsyncMock()
    mock_agent_class.return_value = mock_agent

    args = MagicMock()
    args.request = "find errors"
    args.log = "dummy.log"
    args.output = "my_trace.yaml"

    await handle_analysis(args)

    mock_agent_class.assert_called_once_with(log_path="dummy.log", query="find errors", output_path="my_trace.yaml")
    mock_agent.run.assert_awaited_once()


@pytest.mark.asyncio
@patch("cli.Orchestrator")
async def test_handle_execute_with_result(mock_orchestrator_class, capsys):
    mock_orchestrator = AsyncMock()
    mock_orchestrator.context = {"RESULT": "Successfully parsed 120 errors."}
    mock_orchestrator_class.return_value = mock_orchestrator

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump([{"action": "test", "executor": "tester"}], f)
        temp_path = f.name

    try:
        args = MagicMock()
        args.workflow = temp_path
        args.log = "dummy.log"

        await handle_execute(args)

        captured = capsys.readouterr()
        assert "Final Answer: Successfully parsed 120 errors." in captured.out
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
@patch("cli.Orchestrator")
async def test_handle_execute_without_result(mock_orchestrator_class, capsys):
    mock_orchestrator = AsyncMock()
    mock_orchestrator.context = {"some_key": "some_value", "another_key": 42}
    mock_orchestrator_class.return_value = mock_orchestrator

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        yaml.dump([{"action": "test", "executor": "tester"}], f)
        temp_path = f.name

    try:
        args = MagicMock()
        args.workflow = temp_path
        args.log = "dummy.log"

        await handle_execute(args)

        captured = capsys.readouterr()
        assert "Execution Context Summary:" in captured.out
        assert "- another_key" in captured.out
        assert "- some_key" in captured.out
    finally:
        os.unlink(temp_path)

