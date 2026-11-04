"""The single entry point for all model requests in the builder."""

from typing import Any

from openai import APIError, AsyncOpenAI

from backend.exceptions import LLMConfigurationError, LLMServiceError
from config import AppConfig, config


class LLMGateway:
    """Share endpoint, credentials, request settings, and error handling."""

    def __init__(self, client: Any = None, settings: AppConfig = config) -> None:
        self._client = client
        self.settings = settings

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
            "temperature": self.settings.llm_temperature,
            "messages": messages,
        }
        if response_format is not None:
            options["response_format"] = response_format
        try:
            response = await self._get_client().chat.completions.create(**options)
        except APIError as exc:
            raise LLMServiceError(
                status_code=getattr(exc, "status_code", None) or 503,
                response_text="Check the endpoint, model, and output settings in config.json and OPENAI_API_KEY in the environment.",
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
