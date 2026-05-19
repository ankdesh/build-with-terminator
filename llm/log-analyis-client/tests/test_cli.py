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
async def test_handle_analysis(capsys):
    args = MagicMock()
    args.request = "find errors"
    args.log = "dummy.log"

    await handle_analysis(args)

    captured = capsys.readouterr()
    assert "Analysis Mode (Placeholder)" in captured.out
    assert "find errors" in captured.out
