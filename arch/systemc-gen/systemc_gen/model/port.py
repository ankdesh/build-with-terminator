from dataclasses import dataclass
from typing import Optional

@dataclass
class PortModel:
    """Represents a discrete port/pin on the IP block (e.g. clock, reset, interrupt)."""
    name: str
    direction: str  # in / out
    width: int
    description: Optional[str] = None
