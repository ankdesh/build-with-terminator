
import argparse
import m5
from m5.objects import *
from common import create_riscv_system

def run_study_4(issue_width, num_rob_entries, workload):
    print(f"Running Study 4 with Power Model - Width: {issue_width}, ROB: {num_rob_entries}")

    system = create_riscv_system(CPUTypes.O3)

    system.cpu.numROBEntries = num_rob_entries
    system.cpu.numIQEntries = num_rob_entries
    system.cpu.fetchWidth = issue_width
    system.cpu.decodeWidth = issue_width
    system.cpu.renameWidth = issue_width
    system.cpu.issueWidth = issue_width
    system.cpu.dispatchWidth = issue_width
    system.cpu.wbWidth = issue_width
    system.cpu.commitWidth = issue_width

    # Attach Power Model
    # Example MathExprPowerModel
    # Note: Power modeling in Gem5 often deals with stat names.
    
    system.cpu.power_model = [MathExprPowerModel()]
    system.cpu.power_model[0].dyn = "voltage * (2 * ipc + 0.5 * dcache.overall_misses / sim_seconds)"
    system.cpu.power_model[0].st = "voltage * 0.1" # Static leakage
    
    # We need a voltage domain for this to calculate 'voltage' in the expression?
    # Or MathExpr uses stats. 
    # Gem5 voltage is usually implicit in VoltageDomain. 
    
    # Workload
    process = Process()
    process.cmd = [workload]
    system.cpu.workload = process
    system.cpu.createThreads()

    root = Root(full_system=False, system=system)
    m5.instantiate()

    print("Starting simulation...")
    exit_event = m5.simulate()
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Study 4: Power Model")
    parser.add_argument("--issue_width", type=int, required=True, help="Pipeline Issue Width")
    parser.add_argument("--num_rob_entries", type=int, required=True, help="Number of ROB Entries")
    parser.add_argument("--workload", type=str, required=True, help="Path to workload binary")

    args = parser.parse_args()
    run_study_4(args.issue_width, args.num_rob_entries, args.workload)
