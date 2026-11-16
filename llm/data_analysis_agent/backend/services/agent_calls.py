"""Bounded structured job calls with per-request accounting."""
import asyncio
import json
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, TypeVar
from pydantic import BaseModel
from backend.services.llm_gateway import LLMGateway, ModelRequest
from backend.services.model_output import parse_model_object
from config import config

T = TypeVar('T', bound=BaseModel)


@dataclass
class CallBudget:
    count: int = 0
    deadline: float = 0
    cancelled: Callable[[], bool] = lambda: False
    observe: Callable[[dict], None] = lambda _: None


budget: ContextVar[CallBudget | None] = ContextVar('agent_call_budget', default=None)


async def model_text(gateway: Any, prompt: str, context: dict, job: str,
                     schema: dict | None = None, max_tokens: int = 4096) -> str:
    state = budget.get()
    if state:
        if state.cancelled(): raise ValueError('Chat cancelled')
        if state.count >= config.agent_max_steps: raise ValueError('The request reached its model-step limit. Narrow the request and retry.')
        if time.monotonic() >= state.deadline: raise ValueError('The request reached its active-work deadline.')
        state.count += 1
    serialized = json.dumps(context, default=str)
    if len(serialized)>config.agent_context_limit_chars:
        raise ValueError('The request context is too large. Select one stage or narrow the request before retrying.')
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': serialized}]
    # Compatible text endpoints still receive the same small contract.
    if schema and (not isinstance(gateway, LLMGateway) or gateway.provider == 'openai'):
        messages[0]['content'] += '\nResult contract: '+json.dumps(schema)
    start = time.monotonic()
    if isinstance(gateway, LLMGateway):
        response = await asyncio.wait_for(gateway.generate(ModelRequest(messages, schema=schema, job=job, max_tokens=max_tokens)),
            timeout=max(.01, state.deadline-time.monotonic()) if state else config.llm_timeout_seconds)
        text = response.text
        trace = {'job': job, 'provider': response.provider, 'model': response.model, 'usage': response.usage,
            'stop_reason': response.stop_reason, 'request_id': response.request_id, 'duration_ms': response.duration_ms}
    else:
        text = await gateway.complete(messages)
        trace = {'job': job, 'duration_ms': (time.monotonic()-start)*1000}
    if state:
        if state.cancelled(): raise ValueError('Chat cancelled')
        state.observe(trace)
    return text


async def structured(gateway: Any, prompt: str, context: dict, contract: type[T], job: str,
                     max_tokens: int = 4096) -> T:
    error = ''
    rejected = ''
    for _ in range(2):
        text = await model_text(gateway, prompt, {**context, 'response_error': error,
            'rejected_response': rejected}, job, contract.model_json_schema(), max_tokens)
        try:
            return contract.model_validate(parse_model_object(text))
        except ValueError as exc:
            error, rejected = str(exc)[:4000], text[:16000]
    raise ValueError('Invalid '+job+' response: '+error)
