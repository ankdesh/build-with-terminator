import xml.etree.ElementTree as ET
from typing import Optional, List
import logging

from systemc_gen.model.field import FieldModel
from systemc_gen.model.register import RegisterModel
from systemc_gen.model.port import PortModel
from systemc_gen.model.bus_interface import BusInterfaceModel
from systemc_gen.model.component import ComponentModel

logger = logging.getLogger(__name__)

class IPXACTParser:
    """Parses IEEE 1685 IP-XACT XML specifications into ComponentModel IR structures."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def _parse_int(self, value_str: Optional[str]) -> int:
        """Parses integer values that may be in hex (0x...) or decimal format."""
        if not value_str:
            return 0
        val = value_str.strip()
        try:
            if val.lower().startswith("0x"):
                return int(val, 16)
            return int(val)
        except ValueError:
            logger.warning(f"Could not parse integer from string: '{value_str}', defaulting to 0.")
            return 0

    def parse(self) -> ComponentModel:
        """Parses the IP-XACT file and returns a ComponentModel."""
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        # Extract basic component details
        name_elem = root.find("./{*}name")
        component_name = name_elem.text.strip() if name_elem is not None and name_elem.text else "unknown_component"

        vendor_elem = root.find("./{*}vendor")
        vendor = vendor_elem.text.strip() if vendor_elem is not None and vendor_elem.text else None

        library_elem = root.find("./{*}library")
        library = library_elem.text.strip() if library_elem is not None and library_elem.text else None

        version_elem = root.find("./{*}version")
        version = version_elem.text.strip() if version_elem is not None and version_elem.text else None

        desc_elem = root.find("./{*}description")
        description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

        # Parse bus interfaces (mapping to TLM sockets)
        bus_interfaces = self._parse_bus_interfaces(root)

        # Parse ports/pins
        ports = self._parse_ports(root)

        # Parse registers & memory map
        registers = self._parse_registers(root)

        return ComponentModel(
            name=component_name,
            vendor=vendor,
            library=library,
            version=version,
            bus_interfaces=bus_interfaces,
            ports=ports,
            registers=registers,
            description=description,
        )

    def _parse_bus_interfaces(self, root: ET.Element) -> List[BusInterfaceModel]:
        """Extracts bus interfaces from the component."""
        interfaces: List[BusInterfaceModel] = []
        bus_interfaces_elem = root.find(".//{*}busInterfaces")
        if bus_interfaces_elem is None:
            return interfaces

        for bi_elem in bus_interfaces_elem.findall("./{*}busInterface"):
            name_elem = bi_elem.find("./{*}name")
            if name_elem is None or not name_elem.text:
                continue
            name = name_elem.text.strip()

            # Determine target (slave) vs initiator (master)
            interface_type = "target"
            if bi_elem.find("./{*}master") is not None:
                interface_type = "initiator"
            elif bi_elem.find("./{*}slave") is not None:
                interface_type = "target"

            # Parse protocol type from busType (e.g. AXI4, APB)
            protocol_type = None
            bus_type_elem = bi_elem.find("./{*}busType")
            if bus_type_elem is not None:
                # Find attribute named 'name' ignoring namespace
                proto_name = None
                for attr_key, attr_val in bus_type_elem.attrib.items():
                    if attr_key == "name" or attr_key.endswith("}name"):
                        proto_name = attr_val
                        break
                if not proto_name and bus_type_elem.text:
                    proto_name = bus_type_elem.text.strip()
                protocol_type = proto_name

            desc_elem = bi_elem.find("./{*}description")
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

            interfaces.append(
                BusInterfaceModel(
                    name=name,
                    interface_type=interface_type,
                    protocol_type=protocol_type,
                    description=desc,
                )
            )
        return interfaces

    def _parse_ports(self, root: ET.Element) -> List[PortModel]:
        """Extracts ports/pins from the component."""
        ports: List[PortModel] = []
        model_ports_elem = root.find(".//{*}ports")
        if model_ports_elem is None:
            return ports

        for port_elem in model_ports_elem.findall("./{*}port"):
            name_elem = port_elem.find("./{*}name")
            if name_elem is None or not name_elem.text:
                continue
            name = name_elem.text.strip()

            # Direction
            dir_elem = port_elem.find(".//{*}direction")
            direction = dir_elem.text.strip() if dir_elem is not None and dir_elem.text else "in"

            # Width (check vector elements like left/right)
            width = 1
            vector_elem = port_elem.find(".//{*}vector")
            if vector_elem is not None:
                left_elem = vector_elem.find("./{*}left")
                right_elem = vector_elem.find("./{*}right")
                if left_elem is not None and right_elem is not None:
                    try:
                        left_val = self._parse_int(left_elem.text)
                        right_val = self._parse_int(right_elem.text)
                        width = abs(left_val - right_val) + 1
                    except Exception:
                        width = 1

            desc_elem = port_elem.find("./{*}description")
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

            ports.append(
                PortModel(
                    name=name,
                    direction=direction,
                    width=width,
                    description=desc,
                )
            )
        return ports

    def _parse_registers(self, root: ET.Element) -> List[RegisterModel]:
        """Extracts registers and fields from the memory maps."""
        registers: List[RegisterModel] = []
        memory_maps_elem = root.find(".//{*}memoryMaps")
        if memory_maps_elem is None:
            return registers

        for reg_elem in memory_maps_elem.findall(".//{*}register"):
            name_elem = reg_elem.find("./{*}name")
            if name_elem is None or not name_elem.text:
                continue
            name = name_elem.text.strip()

            addr_offset_elem = reg_elem.find("./{*}addressOffset")
            addr_offset = self._parse_int(addr_offset_elem.text) if addr_offset_elem is not None else 0

            size_elem = reg_elem.find("./{*}size")
            size = self._parse_int(size_elem.text) if size_elem is not None else 32

            access_elem = reg_elem.find("./{*}access")
            access = access_elem.text.strip() if access_elem is not None and access_elem.text else "read-write"

            desc_elem = reg_elem.find("./{*}description")
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

            # Parse fields within this register
            fields: List[FieldModel] = []
            for field_elem in reg_elem.findall(".//{*}field"):
                f_name_elem = field_elem.find("./{*}name")
                if f_name_elem is None or not f_name_elem.text:
                    continue
                f_name = f_name_elem.text.strip()

                bit_offset_elem = field_elem.find("./{*}bitOffset")
                bit_offset = self._parse_int(bit_offset_elem.text) if bit_offset_elem is not None else 0

                bit_width_elem = field_elem.find("./{*}bitWidth")
                bit_width = self._parse_int(bit_width_elem.text) if bit_width_elem is not None else 1

                f_access_elem = field_elem.find("./{*}access")
                f_access = f_access_elem.text.strip() if f_access_elem is not None and f_access_elem.text else access

                f_desc_elem = field_elem.find("./{*}description")
                f_desc = f_desc_elem.text.strip() if f_desc_elem is not None and f_desc_elem.text else None

                fields.append(
                    FieldModel(
                        name=f_name,
                        bit_offset=bit_offset,
                        bit_width=bit_width,
                        access=f_access,
                        description=f_desc,
                    )
                )

            registers.append(
                RegisterModel(
                    name=name,
                    address_offset=addr_offset,
                    size=size,
                    access=access,
                    fields=fields,
                    description=desc,
                )
            )

        # Sort registers by address offset for clean code generation
        registers.sort(key=lambda r: r.address_offset)
        return registers
