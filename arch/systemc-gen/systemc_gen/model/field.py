from dataclasses import dataclass
from typing import Optional

@dataclass
class FieldModel:
    """Represents a single field inside an IP-XACT register."""
    name: str
    bit_offset: int
    bit_width: int
    access: str  # read-write, read-only, write-only, etc.
    description: Optional[str] = None
