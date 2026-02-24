
import m5
from m5.objects import *
from gem5.utils.requires import requires
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.cpu_types import CPUTypes
from gem5.isas import ISA
from gem5.resources.resource import Resource

def create_riscv_system(cpu_type=CPUTypes.O3):
    """
    Creates a basic RISC-V system.
    """
    # Setup the system
    system = System()

    # Set the clock frequency
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '1GHz'
    system.clk_domain.voltage_domain = VoltageDomain()

    # Set up the memory mode
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]

    # Create the CPU
    if cpu_type == CPUTypes.O3:
        system.cpu = RiscvO3CPU()
    elif cpu_type == CPUTypes.TIMING:
        system.cpu = RiscvTimingSimpleCPU()
    elif cpu_type == CPUTypes.ATOMIC:
        system.cpu = RiscvAtomicSimpleCPU()
    else:
        raise ValueError(f"Unsupported CPU type: {cpu_type}")

    # Create the memory bus
    system.membus = SystemXBar()

    # Connect the CPU to the membus
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports

    # Create the memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    # Create the system port
    system.system_port = system.membus.cpu_side_ports

    # Create the interrupt controller
    # RISC-V setup usually requires this
    # system.cpu.createInterruptController() # RiscvO3CPU might invoke this internally or need explicit call depending on version.
    # For simplicity in this common setup, we'll assume basic block.

    return system
