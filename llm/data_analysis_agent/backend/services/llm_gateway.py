"""The single entry point for all model requests in the builder."""

import logging
import re
from typing import Any

from openai import APIError, AsyncOpenAI

from backend.exceptions import LLMConfigurationError, LLMServiceError
from config import AppConfig, config

logger = logging.getLogger(__name__)


def redact_credentials(text: str, secret: str = "") -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
    text = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [redacted]", text)
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

    def __init__(self, client: Any = None, settings: AppConfig = config) -> None:
        self._client = client
        self.settings = settings
        self._omit_temperature = False

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

    async def complete(self, messages: list[dict[str, Any]],
                       response_format: dict[str, Any] | None = None) -> str:
        options: dict[str, Any] = {
            "model": self.settings.openai_model_name,
            "messages": messages,
        }
        if self.settings.llm_temperature is not None and not self._omit_temperature:
            options["temperature"] = self.settings.llm_temperature
        if response_format is not None:
            options["response_format"] = response_format
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
            raise LLMServiceError(
                status_code=getattr(exc, "status_code", None) or 503,
                response_text=self._error_details(exc),
            ) from exc
        if not response.choices:
            raise LLMServiceError(502, "The model returned no response")
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise LLMServiceError(422, "The model declined this request")
        return str(message.content or "")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


llm = LLMGateway()
