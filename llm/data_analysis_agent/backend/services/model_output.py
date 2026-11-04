"""Parse model text locally without requiring provider-specific output modes."""

import json
import re
from typing import Any


def parse_model_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('The model response must be a JSON object')
    return value
