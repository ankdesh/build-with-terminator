import subprocess
import sys
import os
import klayout.rdb as rdb

def run_drc(input_gds="asap7_test.gds", output_lyrdb="drc_violations.lyrdb", drc_script="asap7_mini.drc"):
    print(f"Running DRC analysis on {input_gds} using {drc_script}...")
    
    cmd = [
        "klayout",
        "-b",
        "-r", drc_script,
        "-rd", f"input={input_gds}",
        "-rd", f"report={output_lyrdb}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("DRC Engine failed:")
        print(result.stderr)
    else:
        print("DRC Engine finished successfully. Parsing report database...\n")
        
        report = rdb.ReportDatabase()
        report.load(output_lyrdb)
        
        print("=== DRC Violations Summary ===")
        total_errors = 0
        for category in report.each_category():
            count = sum(1 for item in report.each_item() if item.category_id() == category.rdb_id())
            print(f"Rule: {category.name()} - {category.description}")
            print(f"  -> {count} violation(s) found.")
            total_errors += count
            
        print(f"==============================")
        print(f"Total Violations: {total_errors}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run KLayout DRC.")
    parser.add_argument("in_gds", nargs="?", default="asap7_test.gds", help="Input GDS file")
    parser.add_argument("out_db", nargs="?", default="drc_violations.lyrdb", help="Output LYRDB file")
    parser.add_argument("--drc-script", "-s", default="asap7_mini.drc", help="DRC script to use")
    
    args = parser.parse_args()
    print(f"Input GDS: {args.in_gds}, Output DRC Database: {args.out_db}, DRC Script: {args.drc_script}")
    run_drc(args.in_gds, args.out_db, args.drc_script)
