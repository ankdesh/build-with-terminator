
import argparse
import os
import re

try:
    import pandas as pd
except ImportError:
    pd = None
    print("Warning: pandas not found. Advanced analysis might be limited.")

def parse_stats(stats_file):
    stats = {}
    if not os.path.exists(stats_file):
        print(f"Stats file {stats_file} not found.")
        return stats
        
    with open(stats_file, 'r') as f:
        for line in f:
            if line.strip() == "" or line.startswith("---"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                stat_name = parts[0]
                stat_value = parts[1]
                try:
                    stats[stat_name] = float(stat_value)
                except ValueError:
                    continue
    return stats

def main(stats_dir):
    # This script assumes a directory structure or just parses a single file for demo
    # In a real sweep, you'd traverse subdirectories.
    
    # Target stats
    target_stats = [
        "system.cpu.ipc",
        "system.cpu.iew.branchMispredicts",
        "system.cpu.iq.fu_busy_0", # Config dependent name
        "system.cpu.dcache.overall_misses"
    ]
    
    stats_file = os.path.join(stats_dir, "stats.txt")
    data = parse_stats(stats_file)
    
    print("Parsed Stats:")
    for stat in target_stats:
        # Fuzzy match or exact match
        for key in data:
            if stat in key:
                print(f"{key}: {data[key]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Gem5 Results")
    parser.add_argument("--stats_dir", type=str, default="m5out", help="Directory containing stats.txt")
    args = parser.parse_args()
    main(args.stats_dir)
