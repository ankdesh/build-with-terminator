"""All agent requests use one configured model gateway and environment key."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.exceptions import LLMConfigurationError, LLMServiceError
from backend.services import llm_gateway
from backend.services.agent_service import AgentService
from backend.services.project_agent import ProjectAgent
from config import AppConfig, config


def test_config_uses_environment_key_and_file_settings(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"openai_api_base": "http://localhost:9000/v1/",
        "openai_model_name": "local-model", "openai_api_key": "ignored-file-secret",
        "llm_timeout_seconds": 12, "llm_max_retries": 2, "llm_temperature": 0}))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://ignored.invalid")
    settings = AppConfig.load(path)
    assert settings.openai_api_base == "http://localhost:9000/v1"
    assert settings.openai_model_name == "local-model"
    assert settings.openai_api_key == "environment-secret"
    assert settings.llm_temperature == 0
    assert "secret" not in repr(settings)
    monkeypatch.delenv("OPENAI_API_KEY")
    assert AppConfig.load(path).openai_api_key == ""


@pytest.mark.asyncio
async def test_gateway_configures_and_reuses_one_client(monkeypatch):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[
        SimpleNamespace(message=SimpleNamespace(content='{"answer":42}', refusal=None))])
    factory = Mock(return_value=client)
    monkeypatch.setattr(llm_gateway, "AsyncOpenAI", factory)
    settings = replace(config, openai_api_key="test-key", openai_api_base="http://localhost:9000/v1",
        openai_model_name="local-model", llm_timeout_seconds=12, llm_max_retries=2, llm_temperature=0)
    gateway = llm_gateway.LLMGateway(settings=settings)
    messages = [{"role": "user", "content": "Calculate"}]
    assert await gateway.complete(messages, {"type": "json_object"}) == '{"answer":42}'
    await gateway.complete(messages)
    factory.assert_called_once_with(base_url=settings.openai_api_base, api_key="test-key", timeout=12, max_retries=2)
    first, second = client.chat.completions.create.await_args_list
    assert first.kwargs == {"model": "local-model", "temperature": 0, "messages": messages,
                            "response_format": {"type": "json_object"}}
    assert "response_format" not in second.kwargs
    await gateway.close()
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_key_fails_before_sdk_creation(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(llm_gateway, "AsyncOpenAI", factory)
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        await llm_gateway.LLMGateway(settings=replace(config, openai_api_key="")).complete([])
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_gateway_reports_refusal_and_api_failure_without_credentials():
    import httpx
    from openai import APIConnectionError
    client = AsyncMock()
    gateway = llm_gateway.LLMGateway(client)
    client.chat.completions.create.return_value = SimpleNamespace(choices=[
        SimpleNamespace(message=SimpleNamespace(content=None, refusal="declined"))])
    with pytest.raises(LLMServiceError, match="declined"):
        await gateway.complete([])
    client.chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", "http://localhost/v1"))
    with pytest.raises(LLMServiceError, match="config.json"):
        await gateway.complete([])


def test_agents_share_the_default_gateway():
    assert AgentService().llm is ProjectAgent().llm is llm_gateway.llm


@pytest.mark.parametrize("content", ["{invalid", "[]"])
def test_invalid_config_fails_instead_of_using_another_endpoint(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="Cannot load configuration"):
        AppConfig.load(path)
