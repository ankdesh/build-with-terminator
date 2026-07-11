import os
import logging
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any

from systemc_gen.model.component import ComponentModel
from systemc_gen.model.register import RegisterModel

logger = logging.getLogger(__name__)

class SystemCGenerator:
    """Generates SystemC/TLM-2.0 block scaffolding from a ComponentModel IR using Jinja2 templates."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        # Load templates from the local templates folder relative to this file
        templates_path = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(templates_path),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def _prepare_registers(self, component: ComponentModel) -> list:
        """Pre-processes register layouts to compute bit-field padding and validate correctness."""
        prepared = []
        for reg in component.registers:
            # Sort fields by bit offset (LSB to MSB)
            sorted_fields = sorted(reg.fields, key=lambda f: f.bit_offset)
            
            bitfields = []
            current_bit = 0
            for f in sorted_fields:
                if f.bit_offset < current_bit:
                    raise ValueError(
                        f"Overlapping register fields detected in register '{reg.name}': "
                        f"field '{f.name}' starts at bit {f.bit_offset} but previous field ended at bit {current_bit}."
                    )
                
                # Check for gap and insert padding/reserved field
                if f.bit_offset > current_bit:
                    pad_width = f.bit_offset - current_bit
                    bitfields.append({
                        "name": None,
                        "width": pad_width,
                        "description": "Reserved/Padding"
                    })
                
                bitfields.append({
                    "name": f.name,
                    "width": f.bit_width,
                    "description": f.description or ""
                })
                current_bit = f.bit_offset + f.bit_width
            
            # Add padding at the end of the register if required
            if current_bit < reg.size:
                pad_width = reg.size - current_bit
                bitfields.append({
                    "name": None,
                    "width": pad_width,
                    "description": "Reserved/Padding"
                })
            elif current_bit > reg.size:
                raise ValueError(
                    f"Register fields in '{reg.name}' exceed register size of {reg.size} bits (total: {current_bit} bits)."
                )

            prepared.append({
                "name": reg.name,
                "address_offset": reg.address_offset,
                "size": reg.size,
                "access": reg.access,
                "description": reg.description,
                "bitfields": bitfields
            })
        return prepared

    def generate(self, component: ComponentModel) -> str:
        """Renders the component templates and writes the C++ scaffolding to output_dir/<component_name>/."""
        block_name = component.name
        block_dir = os.path.join(self.output_dir, block_name)
        os.makedirs(block_dir, exist_ok=True)

        # Pre-process register layout structures for Jinja2 rendering
        prepared_registers = self._prepare_registers(component)

        # Prepare templates context
        context: Dict[str, Any] = {
            "name": block_name,
            "vendor": component.vendor,
            "library": component.library,
            "version": component.version,
            "bus_interfaces": component.bus_interfaces,
            "ports": component.ports,
            "registers": prepared_registers,
            "description": component.description,
        }

        # Render list of files
        files_to_generate = {
            "block.h.jinja": f"{block_name}.h",
            "block_regs.h.jinja": f"{block_name}_regs.h",
            "block.cpp.jinja": f"{block_name}.cpp",
            "block_tb.cpp.jinja": f"{block_name}_tb.cpp",
            "CMakeLists.txt.jinja": "CMakeLists.txt"
        }

        for template_name, dest_filename in files_to_generate.items():
            template = self.env.get_template(template_name)
            content = template.render(context)
            dest_path = os.path.join(block_dir, dest_filename)
            with open(dest_path, "w") as f:
                f.write(content)
            logger.info(f"Generated file: {dest_path}")

        return block_dir
