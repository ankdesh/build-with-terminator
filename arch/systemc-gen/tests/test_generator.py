import os
import pytest
import shutil
import tempfile
from systemc_gen.parser import IPXACTParser
from systemc_gen.generator import SystemCGenerator
from systemc_gen.model.component import ComponentModel
from systemc_gen.model.register import RegisterModel
from systemc_gen.model.field import FieldModel

# Paths
TESTS_DIR = os.path.dirname(__file__)
SAMPLE_IPXACT_PATH = os.path.join(TESTS_DIR, "data", "sample_ipxact.xml")

def test_parser():
    """Verify that IPXACTParser correctly parses the sample IP-XACT file."""
    assert os.path.exists(SAMPLE_IPXACT_PATH), f"Sample file not found at {SAMPLE_IPXACT_PATH}"
    
    parser = IPXACTParser(SAMPLE_IPXACT_PATH)
    component = parser.parse()
    
    # Assert basic details
    assert component.name == "timer_block"
    assert component.vendor == "acme"
    assert component.library == "ip"
    assert component.version == "1.0"
    
    # Assert bus interfaces
    assert len(component.bus_interfaces) == 2
    bus_map = {bi.name: bi for bi in component.bus_interfaces}
    
    assert "s_apb" in bus_map
    assert bus_map["s_apb"].interface_type == "target"
    assert bus_map["s_apb"].protocol_type == "APB"
    
    assert "m_axi" in bus_map
    assert bus_map["m_axi"].interface_type == "initiator"
    assert bus_map["m_axi"].protocol_type == "AXI4"
    
    # Assert ports
    assert len(component.ports) == 4
    port_map = {p.name: p for p in component.ports}
    
    assert "clk" in port_map
    assert port_map["clk"].direction == "in"
    assert port_map["clk"].width == 1
    
    assert "cfg_data" in port_map
    assert port_map["cfg_data"].direction == "in"
    assert port_map["cfg_data"].width == 8
    
    # Assert registers and fields
    assert len(component.registers) == 2
    reg_map = {r.name: r for r in component.registers}
    
    assert "CONTROL" in reg_map
    control_reg = reg_map["CONTROL"]
    assert control_reg.address_offset == 0x00
    assert control_reg.size == 32
    assert control_reg.access == "read-write"
    assert len(control_reg.fields) == 2
    
    field_map = {f.name: f for f in control_reg.fields}
    assert "ENABLE" in field_map
    assert field_map["ENABLE"].bit_offset == 0
    assert field_map["ENABLE"].bit_width == 1
    
    assert "MODE" in field_map
    assert field_map["MODE"].bit_offset == 1
    assert field_map["MODE"].bit_width == 3

def test_generator_successful_run():
    """Verify that SystemCGenerator correctly generates all scaffolding files."""
    parser = IPXACTParser(SAMPLE_IPXACT_PATH)
    component = parser.parse()
    
    # Create temporary directory for generation output
    temp_out_dir = tempfile.mkdtemp()
    try:
        generator = SystemCGenerator(temp_out_dir)
        block_dir = generator.generate(component)
        
        # Verify output directory name
        assert os.path.basename(block_dir) == "timer_block"
        
        # Check files exist
        expected_files = [
            "timer_block.h",
            "timer_block_regs.h",
            "timer_block.cpp",
            "timer_block_tb.cpp",
            "CMakeLists.txt"
        ]
        
        for f in expected_files:
            file_path = os.path.join(block_dir, f)
            assert os.path.exists(file_path), f"Expected file {f} was not generated"
            
        # Inspect contents of timer_block.h
        with open(os.path.join(block_dir, "timer_block.h"), "r") as f:
            h_content = f.read()
            assert "class timer_block" in h_content
            assert "tlm_utils::simple_target_socket<timer_block> s_apb;" in h_content
            assert "tlm_utils::simple_initiator_socket<timer_block> m_axi;" in h_content
            assert "sc_core::sc_in<bool> clk;" in h_content
            assert "sc_core::sc_in<sc_dt::sc_bv<8>> cfg_data;" in h_content
            assert "timer_block_regs_t regs;" in h_content
            
        # Inspect contents of timer_block_regs.h
        with open(os.path.join(block_dir, "timer_block_regs.h"), "r") as f:
            regs_content = f.read()
            assert "struct CONTROL_t" in regs_content
            assert "uint32_t ENABLE : 1;" in regs_content
            assert "uint32_t MODE : 3;" in regs_content
            assert "struct timer_block_regs_t" in regs_content
            
        # Inspect contents of timer_block.cpp
        with open(os.path.join(block_dir, "timer_block.cpp"), "r") as f:
            cpp_content = f.read()
            assert "timer_block::timer_block(sc_core::sc_module_name nm)" in cpp_content
            assert "s_apb.register_b_transport" in cpp_content
            assert "case 0x00:" in cpp_content
            assert "case 0x04:" in cpp_content
            assert "std::memcpy(ptr, &regs.CONTROL.value, len);" in cpp_content
            
    finally:
        shutil.rmtree(temp_out_dir)

def test_generator_overlapping_fields_validation():
    """Verify that the generator raises a ValueError if register fields overlap."""
    component = ComponentModel(
        name="test_device",
        registers=[
            RegisterModel(
                name="REG_ERR",
                address_offset=0x00,
                size=32,
                access="read-write",
                fields=[
                    FieldModel(name="F1", bit_offset=0, bit_width=4, access="read-write"),
                    FieldModel(name="F2", bit_offset=2, bit_width=2, access="read-write"),  # Overlaps F1
                ]
            )
        ]
    )
    
    temp_out_dir = tempfile.mkdtemp()
    try:
        generator = SystemCGenerator(temp_out_dir)
        with pytest.raises(ValueError) as excinfo:
            generator.generate(component)
        assert "Overlapping register fields detected" in str(excinfo.value)
    finally:
        shutil.rmtree(temp_out_dir)

def test_generator_fields_overflow_validation():
    """Verify that the generator raises a ValueError if fields exceed register size."""
    component = ComponentModel(
        name="test_device",
        registers=[
            RegisterModel(
                name="REG_ERR",
                address_offset=0x00,
                size=8,
                access="read-write",
                fields=[
                    FieldModel(name="F1", bit_offset=0, bit_width=10, access="read-write"),  # Exceeds size of 8
                ]
            )
        ]
    )
    
    temp_out_dir = tempfile.mkdtemp()
    try:
        generator = SystemCGenerator(temp_out_dir)
        with pytest.raises(ValueError) as excinfo:
            generator.generate(component)
        assert "exceed register size of 8 bits" in str(excinfo.value)
    finally:
        shutil.rmtree(temp_out_dir)
