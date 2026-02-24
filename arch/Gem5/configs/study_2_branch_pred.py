
import argparse
import m5
from m5.objects import *
from common import create_riscv_system

def set_pipeline_depth(cpu, depth_factor):
    """
    Simulates deeper pipeline by increasing stage latencies.
    Base latency is usually 1 cycle.
    """
    # This is a simplification. Real pipeline depth increase involves splitting stages.
    # Increasing latency models the penalty.
    base_latency = 1
    latency = base_latency + depth_factor
    
    cpu.fetchLatency = latency
    cpu.decodeLatency = latency
    cpu.renameLatency = latency
    # Dispatch/Issue/WB/Commit usually have latencies too
    # We will apply a factor to critical front-end stages 
    
def run_study_2(bp_type, depth_factor, workload):
    print(f"Running Study 2 with BP: {bp_type}, Depth Factor: {depth_factor}")

    system = create_riscv_system(CPUTypes.O3)

    # Set Branch Predictor
    if bp_type == "TournamentBP":
        system.cpu.branchPred = TournamentBP()
    elif bp_type == "BiModeBP":
        system.cpu.branchPred = BiModeBP()
    elif bp_type == "TAGE":
        system.cpu.branchPred = LTAGE() # Gem5 often has LTAGE or TAGE
    elif bp_type == "TAGE_SC_L":
        # TAGE-SC-L might not be standard in all Gem5 versions or named differently.
        # Checking if available, else fallback or use MultiperspectivePerceptronTAGE
        try:
             system.cpu.branchPred = TAGE_SC_L() 
        except NameError:
             print("TAGE_SC_L not found, using LTAGE as proxy")
             system.cpu.branchPred = LTAGE()
    else:
        print(f"Unknown BP type {bp_type}, using default")

    # Set Pipeline Depth (Latency)
    set_pipeline_depth(system.cpu, depth_factor)
    
    # Set workload
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
    parser = argparse.ArgumentParser(description="Study 2: Branch Predictor")
    parser.add_argument("--bp_type", type=str, required=True, choices=["TournamentBP", "BiModeBP", "TAGE", "TAGE_SC_L"], help="Branch Predictor Type")
    parser.add_argument("--depth_factor", type=int, default=0, help="Added latency to simulate pipeline depth")
    parser.add_argument("--workload", type=str, required=True, help="Path to workload binary")

    args = parser.parse_args()
    run_study_2(args.bp_type, args.depth_factor, args.workload)
