from dataclasses import dataclass, field
from typing import List, Optional
from systemc_gen.model.field import FieldModel

@dataclass
class RegisterModel:
    """Represents an IP-XACT register containing fields."""
    name: str
    address_offset: int
    size: int  # in bits (usually 32 or 64)
    access: str
    fields: List[FieldModel] = field(default_factory=list)
    description: Optional[str] = None
