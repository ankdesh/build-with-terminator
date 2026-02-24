
import argparse
import m5
from m5.objects import *
from common import create_riscv_system

def run_study_3(l1d_size, l1d_assoc, mshrs, workload):
    print(f"Running Study 3 with L1D: {l1d_size}, Assoc: {l1d_assoc}, MSHRs: {mshrs}")

    system = create_riscv_system(CPUTypes.O3)

    # Configure L1 Cache
    # In common.py we relied on O3CPU default caches or configured them? 
    # Wait, common.py didn't explicitly create caches attached to CPU ports in the shared snippet 
    # (it connected cpu ports to membus, implying no caches or magic atomic). 
    # For O3, we NEED caches. 
    # Let's fix this by explicitly creating caches here or updating common.py.
    # To keep it self-contained, I will add caches here.
    
    # Create L1 Caches
    system.cpu.icache = Cache(size='32kB', assoc=2, tag_latency=2, data_latency=2, response_latency=2, mshrs=4, tgts_per_mshr=20)
    system.cpu.dcache = Cache(size=l1d_size, assoc=l1d_assoc, tag_latency=2, data_latency=2, response_latency=2, mshrs=mshrs, tgts_per_mshr=20)

    # Connecting caches
    system.cpu.icache.cpu_side = system.cpu.icache_port
    system.cpu.dcache.cpu_side = system.cpu.dcache_port
    
    system.cpu.icache.mem_side = system.membus.cpu_side_ports
    system.cpu.dcache.mem_side = system.membus.cpu_side_ports

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
    parser = argparse.ArgumentParser(description="Study 3: Cache Sensitivity")
    parser.add_argument("--l1d_size", type=str, required=True, help="L1 D-Cache Size (e.g., '32kB')")
    parser.add_argument("--l1d_assoc", type=int, required=True, help="L1 D-Cache Associativity")
    parser.add_argument("--mshrs", type=int, required=True, help="Number of MSHRs")
    parser.add_argument("--workload", type=str, required=True, help="Path to workload binary")

    args = parser.parse_args()
    run_study_3(args.l1d_size, args.l1d_assoc, args.mshrs, args.workload)
