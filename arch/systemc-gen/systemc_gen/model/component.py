from dataclasses import dataclass, field
from typing import List, Optional
from systemc_gen.model.bus_interface import BusInterfaceModel
from systemc_gen.model.port import PortModel
from systemc_gen.model.register import RegisterModel

@dataclass
class ComponentModel:
    """Represents a full IP block component parsed from IP-XACT."""
    name: str
    vendor: Optional[str] = None
    library: Optional[str] = None
    version: Optional[str] = None
    bus_interfaces: List[BusInterfaceModel] = field(default_factory=list)
    ports: List[PortModel] = field(default_factory=list)
    registers: List[RegisterModel] = field(default_factory=list)
    description: Optional[str] = None
