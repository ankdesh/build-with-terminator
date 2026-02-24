
import argparse
import m5
from m5.objects import *
from common import create_riscv_system

def run_study_1(issue_width, num_rob_entries, workload):
    print(f"Running Study 1 with Issue Width: {issue_width}, ROB Entries: {num_rob_entries}")

    # Create the system
    system = create_riscv_system(CPUTypes.O3)

    # Configure the CPU
    # Scale numIQEntries proportionally to numROBEntries (e.g., 0.5 ratio or similar, 
    # report says "scaled proportionally to prevent artificial reservation station bottlenecks")
    # Let's assume IQ = ROB / 2 for integer and floating point queues, or just equal scaling.
    # Gem5 O3 CPU has separate IQ, LQ, SQ. Usually IQ size is key.
    # We will set IQ entries equal to ROB entries for simplicity to remove it as bottleneck,
    # or follow a specific ratio if known. Report suggests expanding it.
    
    num_iq_entries = num_rob_entries # Simple heuristic: Make it large enough

    system.cpu.numROBEntries = num_rob_entries
    system.cpu.numIQEntries = num_iq_entries
    
    # Set widths
    # Gem5 O3 CPU uses separate widths for stages, but we usually scale them together for "Width"
    system.cpu.fetchWidth = issue_width
    system.cpu.decodeWidth = issue_width
    system.cpu.renameWidth = issue_width
    system.cpu.issueWidth = issue_width
    system.cpu.dispatchWidth = issue_width
    system.cpu.wbWidth = issue_width
    system.cpu.commitWidth = issue_width

    # Set workload
    process = Process()
    process.cmd = [workload]
    system.cpu.workload = process
    system.cpu.createThreads()

    # Root
    root = Root(full_system=False, system=system)
    
    # Instantiate
    m5.instantiate()

    # Run
    print("Starting simulation...")
    exit_event = m5.simulate()
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Study 1: ILP Wall")
    parser.add_argument("--issue_width", type=int, required=True, help="Pipeline Issue Width")
    parser.add_argument("--num_rob_entries", type=int, required=True, help="Number of ROB Entries")
    parser.add_argument("--workload", type=str, required=True, help="Path to workload binary")
    
    args = parser.parse_args()
    
    run_study_1(args.issue_width, args.num_rob_entries, args.workload)
