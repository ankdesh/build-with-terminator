from dataclasses import dataclass
from typing import Optional

@dataclass
class BusInterfaceModel:
    """Represents an IP-XACT bus interface mapping to a TLM socket."""
    name: str
    interface_type: str  # target / initiator (maps to slave / master)
    protocol_type: Optional[str] = None  # e.g., AXI4, APB, AHB
    description: Optional[str] = None
