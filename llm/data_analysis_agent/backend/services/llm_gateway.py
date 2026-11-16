"""The single entry point for all model requests in the builder."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, cast

from openai import APIError, AsyncOpenAI

from backend.exceptions import LLMConfigurationError, LLMServiceError
from config import AppConfig, config

logger = logging.getLogger(__name__)


@dataclass
class ModelRequest:
    messages: list[dict[str, Any]]
    schema: dict[str, Any] | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    job: str = "chat"
    max_tokens: int | None = None


@dataclass
class ModelResponse:
    text: str
    provider: str
    model: str
    stop_reason: str = "end_turn"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    request_id: str | None = None
    duration_ms: float = 0
    content: list[dict[str, Any]] = field(default_factory=list)


class ProviderError(LLMServiceError):
    def __init__(self, kind: str, message: str, status_code: int = 502) -> None:
        super().__init__(status_code, message)
        self.kind = kind


def provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Keep the supported wire shape; Pydantic still enforces all local limits."""
    unsupported = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                   "minLength", "maxLength", "maxItems", "default", "title"}
    def visit(value: Any) -> Any:
        if isinstance(value, list): return [visit(item) for item in value]
        if not isinstance(value, dict): return value
        result: dict[str, Any] = {key: ({name: visit(shape) for name, shape in item.items()} if key in {'properties', '$defs'} else visit(item))
                  for key, item in value.items() if key not in unsupported}
        if result.get("minItems", 0) > 1: result["minItems"] = 1
        if result.get("type") == "object":
            result["additionalProperties"] = False
            result["required"] = list(result.get("properties", {}))
        return result
    return cast(dict[str, Any], visit(schema))


def redact_credentials(text: str, secret: str = "") -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
    text = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [redacted]", text)
    text = re.sub(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[redacted]", text)
    text = re.sub(r'''(?i)((?:aws_secret_access_key|aws_session_token|x-amz-security-token|authorization)["']?\s*[:=]\s*["']?)[^\s,;"'}\]]+''', r"\1[redacted]", text)
    return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted]", text)


def api_error_fields(error: APIError) -> dict[str, Any]:
    """Read provider diagnostics, never the request headers or request body."""
    body = error.body
    if not isinstance(body, dict):
        return {}
    fields = body.get("error", body)
    return fields if isinstance(fields, dict) else {}


class LLMGateway:
    """Share endpoint, credentials, request settings, and error handling."""

    def __init__(self, client: Any = None, settings: AppConfig = config, *, bedrock_client: Any = None) -> None:
        self._client = client
        self._bedrock_client = bedrock_client
        self.provider = "openai" if client is not None else settings.llm_provider
        self.settings = settings
        self._omit_temperature = False
        self.last_response: ModelResponse | None = None

    def _get_bedrock_client(self) -> Any:
        if self._bedrock_client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise LLMConfigurationError("Install the builder dependencies, including boto3") from exc
            session = boto3.Session(profile_name=self.settings.bedrock_profile)
            self._bedrock_client = session.client("bedrock-runtime", region_name=self.settings.bedrock_region,
                config=Config(connect_timeout=10, read_timeout=self.settings.llm_timeout_seconds,
                    retries={"mode": "standard", "total_max_attempts": self.settings.llm_max_retries + 1}))
        return self._bedrock_client

    def _bedrock_options(self, request: ModelRequest) -> dict[str, Any]:
        system = []
        messages = []
        for message in request.messages:
            if message["role"] == "system":
                system.append({"text": str(message["content"])})
            else:
                content = message["content"]
                messages.append({"role": message["role"], "content": content if isinstance(content, list) else [{"text": str(content)}]})
        options: dict[str, Any] = {"modelId": self.settings.bedrock_model_id, "messages": messages,
            "inferenceConfig": {"maxTokens": request.max_tokens or 16384}}
        if system: options["system"] = system
        if self.settings.llm_temperature is not None:
            options["inferenceConfig"]["temperature"] = self.settings.llm_temperature
        if request.schema:
            options["outputConfig"] = {"textFormat": {"type": "json_schema", "structure": {"jsonSchema": {
                "name": re.sub(r"[^a-zA-Z0-9_]", "_", request.job), "schema": json.dumps(provider_schema(request.schema))}}}}
        if request.tools: options["toolConfig"] = {"tools": request.tools}
        return options

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start = time.monotonic()
        if self.provider == "bedrock":
            try:
                response = await asyncio.to_thread(lambda: self._get_bedrock_client().converse(**self._bedrock_options(request)))
            except Exception as exc:
                if isinstance(exc, LLMConfigurationError): raise
                body = getattr(exc, "response", {})
                code = body.get("Error", {}).get("Code", type(exc).__name__)
                kind = ("authentication" if code in {"AccessDeniedException", "UnrecognizedClientException", "ExpiredTokenException", "NoCredentialsError"}
                    else "throttled" if code == "ThrottlingException" else "timeout" if "Timeout" in code
                    else "capability" if code == "ValidationException" else "transport")
                raise ProviderError(kind, redact_credentials(f"Bedrock {code}: {exc}")[:1600]) from exc
            content = response.get("output", {}).get("message", {}).get("content", [])
            result = ModelResponse("".join(block.get("text", "") for block in content), "bedrock",
                self.settings.bedrock_model_id, response.get("stopReason", "end_turn"),
                [block["toolUse"] for block in content if "toolUse" in block], response.get("usage", {}),
                response.get("ResponseMetadata", {}).get("RequestId"), content=content)
        else:
            fmt = {"type": "json_schema", "json_schema": {"name": request.job, "strict": True,
                "schema": provider_schema(request.schema)}} if request.schema and self.settings.openai_agent_protocol == "native" else None
            result = await self._openai_generate(request.messages, fmt, request.max_tokens, request.tools)
        result.duration_ms = (time.monotonic() - start) * 1000
        self.last_response = result
        if result.stop_reason in {"length", "max_tokens", "model_context_window_exceeded"}:
            raise ProviderError("truncated", "The model response reached its token or context limit. Reduce the task or increase its output budget.")
        if result.stop_reason in {"refusal", "content_filtered", "guardrail_intervened", "content_filter"}:
            raise ProviderError("refusal", "The model declined this request", 422)
        return result

    async def complete(self, messages: list[dict[str, Any]], response_format: dict[str, Any] | None = None) -> str:
        if self.provider == "openai":
            result = await self._openai_generate(messages, response_format)
            self.last_response = result
            if result.stop_reason == "length": raise ProviderError("truncated", "The model response was truncated")
            return result.text
        schema = (response_format or {}).get("json_schema", {}).get("schema")
        return (await self.generate(ModelRequest(messages, schema=schema))).text

    async def stream(self, request: ModelRequest) -> AsyncIterator[dict[str, Any]]:
        """Stream text only. Structured jobs wait for a complete validated result."""
        if request.schema or request.tools:
            result = await self.generate(request)
            yield {"event": "response", "response": result}
            return
        if self.provider == "bedrock":
            response = await asyncio.to_thread(self._get_bedrock_client().converse_stream, **self._bedrock_options(request))
            stream = response["stream"]
            def next_event() -> Any:
                return next(stream, None)
            try:
                while (event := await asyncio.to_thread(next_event)) is not None:
                    if "contentBlockDelta" in event:
                        yield {"event": "text_delta", "text": event["contentBlockDelta"].get("delta", {}).get("text", "")}
                    if "messageStop" in event:
                        reason = event["messageStop"]["stopReason"]
                        if reason in {"max_tokens", "model_context_window_exceeded"}: raise ProviderError("truncated", "The model response was truncated")
                        yield {"event": "stop", "stop_reason": reason}
                    if "metadata" in event: yield {"event": "usage", "usage": event["metadata"].get("usage", {})}
                    if any(key.endswith("Exception") for key in event): raise ProviderError("transport", "Bedrock streaming request failed")
            finally:
                stream.close()
        else:
            options: dict[str, Any] = {"model": self.settings.openai_model_name, "messages": request.messages, "stream": True}
            if request.max_tokens: options["max_completion_tokens"] = request.max_tokens
            stream = await self._get_client().chat.completions.create(**options)
            try:
                async for event in stream:
                    for choice in event.choices:
                        if choice.delta.content: yield {"event": "text_delta", "text": choice.delta.content}
                        if choice.finish_reason:
                            if choice.finish_reason == "length": raise ProviderError("truncated", "The model response was truncated")
                            yield {"event": "stop", "stop_reason": choice.finish_reason}
            finally:
                await stream.close()

    def _error_details(self, error: APIError) -> str:
        fields = api_error_fields(error)
        details = []
        for field in ("message", "param", "code"):
            value = fields.get(field)
            if isinstance(value, str) and value:
                details.append(f"{field}: {value}")
        text = "; ".join(details) or "Check the endpoint, model, and output settings in config.json and OPENAI_API_KEY in the environment."
        return redact_credentials(text, self.settings.openai_api_key)[:1600]

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.openai_api_key:
                raise LLMConfigurationError("Set OPENAI_API_KEY before starting the builder")
            self._client = AsyncOpenAI(
                base_url=self.settings.openai_api_base,
                api_key=self.settings.openai_api_key,
                timeout=self.settings.llm_timeout_seconds,
                max_retries=self.settings.llm_max_retries,
            )
        return self._client

    async def _openai_generate(self, messages: list[dict[str, Any]],
                       response_format: dict[str, Any] | None = None, max_tokens: int | None = None,
                       tools: list[dict[str, Any]] | None = None) -> ModelResponse:
        options: dict[str, Any] = {
            "model": self.settings.openai_model_name,
            "messages": messages,
        }
        if self.settings.llm_temperature is not None and not self._omit_temperature:
            options["temperature"] = self.settings.llm_temperature
        if response_format is not None:
            options["response_format"] = response_format
        if max_tokens: options["max_completion_tokens"] = max_tokens
        if tools: options["tools"] = tools
        try:
            try:
                response = await self._get_client().chat.completions.create(**options)
            except APIError as exc:
                fields = api_error_fields(exc)
                # Some reasoning models accept only their default sampling settings.
                # Retry only an explicit rejection of the optional temperature field.
                if (getattr(exc, "status_code", None) != 400 or "temperature" not in options
                        or fields.get("param") != "temperature"
                        or fields.get("code") not in {"unsupported_parameter", "unsupported_value"}):
                    raise
                self._omit_temperature = True
                options.pop("temperature")
                logger.warning("The configured model rejects temperature; using its default. Set llm_temperature to null to omit it explicitly.")
                response = await self._get_client().chat.completions.create(**options)
        except APIError as exc:
            status = getattr(exc,"status_code",None) or 503
            kind = ('authentication' if status in {401,403} else 'throttled' if status==429
                else 'timeout' if 'Timeout' in type(exc).__name__ else 'capability' if status==400 else 'transport')
            raise ProviderError(kind,self._error_details(exc),status) from exc
        if not response.choices:
            raise ProviderError('empty_response', "The model returned no response")
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise ProviderError('refusal', "The model declined this request",422)
        usage = getattr(response, "usage", None)
        return ModelResponse(str(message.content or ""), "openai", self.settings.openai_model_name,
            str(getattr(response.choices[0], "finish_reason", None) or "end_turn"),
            tool_calls=[{"toolUseId": tool.id, "name": tool.function.name, "input": json.loads(tool.function.arguments)}
                        for tool in (getattr(message, "tool_calls", None) or [])],
            usage=usage.model_dump() if usage is not None else {}, request_id=getattr(response, "id", None))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._bedrock_client is not None:
            self._bedrock_client.close()
            self._bedrock_client = None


llm = LLMGateway()
