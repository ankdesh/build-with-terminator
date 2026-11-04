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


def bad_request(param, code, message):
    import httpx
    from openai import BadRequestError
    return BadRequestError('Request rejected', response=httpx.Response(400,
        request=httpx.Request('POST', 'http://localhost/v1/chat/completions')),
        body={'error': {'param': param, 'code': code, 'message': message}})


def completion():
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}', refusal=None))])


def test_null_temperature_config_uses_model_default(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'openai_model_name': 'gpt-6-luna', 'llm_temperature': None}))
    assert AppConfig.load(path).llm_temperature is None


@pytest.mark.parametrize('value', [-.1, 2.1, float('nan'), float('inf')])
def test_invalid_temperature_config_is_rejected(tmp_path, value):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'llm_temperature': value}))
    with pytest.raises(ValueError, match='temperature'):
        AppConfig.load(path)


@pytest.mark.asyncio
async def test_gateway_omits_null_temperature_and_keeps_structured_output():
    client = AsyncMock()
    client.chat.completions.create.return_value = completion()
    gateway = llm_gateway.LLMGateway(client, replace(config, llm_temperature=None))
    schema = {'type': 'json_schema', 'json_schema': {'name': 'test'}}
    await gateway.complete([{'role': 'user', 'content': 'Return JSON'}], schema)
    kwargs = client.chat.completions.create.await_args.kwargs
    assert 'temperature' not in kwargs
    assert kwargs['response_format'] == schema
    assert kwargs['model'] == config.openai_model_name


@pytest.mark.parametrize('code', ['unsupported_value', 'unsupported_parameter'])
@pytest.mark.asyncio
async def test_gateway_retries_explicit_temperature_rejection_once_and_remembers(code):
    client = AsyncMock()
    client.chat.completions.create.side_effect = [bad_request('temperature', code, 'Only the default is supported'), completion(), completion()]
    gateway = llm_gateway.LLMGateway(client, replace(config, llm_temperature=.1))
    schema = {'type': 'json_object'}
    messages = [{'role': 'user', 'content': 'Return JSON'}]
    assert await gateway.complete(messages, schema) == '{"ok":true}'
    await gateway.complete(messages, schema)
    calls = client.chat.completions.create.await_args_list
    assert len(calls) == 3
    assert calls[0].kwargs['temperature'] == .1
    for call in calls[1:]:
        assert 'temperature' not in call.kwargs
        assert call.kwargs['model'] == config.openai_model_name
        assert call.kwargs['messages'] == messages
        assert call.kwargs['response_format'] == schema


@pytest.mark.asyncio
async def test_gateway_does_not_drop_schema_or_retry_other_bad_requests():
    client = AsyncMock()
    client.chat.completions.create.side_effect = bad_request('response_format', 'invalid_json_schema', 'Schema is invalid')
    gateway = llm_gateway.LLMGateway(client, replace(config, llm_temperature=.1))
    with pytest.raises(LLMServiceError, match='response_format.*invalid_json_schema'):
        await gateway.complete([], {'type': 'json_schema'})
    assert client.chat.completions.create.await_count == 1


@pytest.mark.asyncio
async def test_failed_compatibility_retry_reports_the_second_error_without_further_retry():
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        bad_request('temperature', 'unsupported_value', 'Only the default is supported'),
        bad_request('model', 'model_not_found', 'Model unavailable'),
    ]
    gateway = llm_gateway.LLMGateway(client, replace(config, llm_temperature=.1))
    with pytest.raises(LLMServiceError, match='Model unavailable'):
        await gateway.complete([])
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_provider_diagnostics_redact_credentials_and_ignore_request_echo():
    client = AsyncMock()
    error = bad_request('model', 'invalid_request_error', 'Invalid model. key=my-test-secret Bearer another-secret sk-provider-secret')
    error.body['request'] = {'messages': 'private request text'}
    client.chat.completions.create.side_effect = error
    gateway = llm_gateway.LLMGateway(client, replace(config, openai_api_key='my-test-secret', llm_temperature=None))
    with pytest.raises(LLMServiceError) as caught:
        await gateway.complete([])
    details = str(caught.value)
    assert 'Invalid model' in details and 'invalid_request_error' in details
    for secret in ['my-test-secret', 'another-secret', 'sk-provider-secret', 'private request text']:
        assert secret not in details
