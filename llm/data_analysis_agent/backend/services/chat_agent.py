"""Intent selection is separate from calculations and saved authoring."""
from typing import Any
from backend.services.agent_calls import structured
from backend.services.agent_contracts import Route
from backend.services.agent_prompts import ROUTER

ChatReply = Route
CHAT_PROMPT = ROUTER


async def reply(gateway: Any, context: dict) -> Route:
    result = await structured(gateway,ROUTER,context,Route,'route_request',4096)
    if context.get('answer_only') and result.kind not in {'answer','clarification'}:
        raise ValueError('answer_only requires an answer or clarification without proposed actions')
    return result
