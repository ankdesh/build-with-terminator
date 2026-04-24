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
    in_gds = sys.argv[1] if len(sys.argv) > 1 else "asap7_test.gds"
    out_db = sys.argv[2] if len(sys.argv) > 2 else "drc_violations.lyrdb"
    run_drc(in_gds, out_db)
