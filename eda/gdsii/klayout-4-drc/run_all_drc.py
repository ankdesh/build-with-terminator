import os
import subprocess
import glob
import sys

def run_all_tests(target_dir, output_report):
    target_dir = os.path.expanduser(target_dir)
    drc_files = glob.glob(os.path.join(target_dir, "*.drc"))
    
    if not drc_files:
        print(f"No .drc files found in {target_dir}")
        return

    # Use the python executable from the local virtual environment
    # if it exists, otherwise fallback to sys.executable
    python_exe = sys.executable
    if os.path.exists(".venv/bin/python"):
        python_exe = ".venv/bin/python"

    with open(output_report, "w") as out_f:
        for drc_file in sorted(drc_files):
            base_name = os.path.splitext(drc_file)[0]
            gds_file = base_name + ".gds"
            
            if not os.path.exists(gds_file):
                continue
                
            header = f"===========================================================\n"
            header += f"Running pair: {os.path.basename(drc_file)} and {os.path.basename(gds_file)}\n"
            header += f"===========================================================\n"
            out_f.write(header)
            print(f"Processing {os.path.basename(drc_file)} with {os.path.basename(gds_file)}...")
            
            cmd = [
                python_exe, "run_drc_textual.py",
                drc_file, gds_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            out_f.write(result.stdout)
            if result.stderr:
                out_f.write("\n--- STDERR ---\n")
                out_f.write(result.stderr)
            out_f.write("\n\n")

if __name__ == "__main__":
    target_dir = "~/explore/eda/klayout/klayout/testdata/drc"
    output_report = "unified_drc_report.txt"
    print(f"Starting batch DRC processing for directory: {target_dir}")
    run_all_tests(target_dir, output_report)
    print(f"Done! Unified report saved to {output_report}")
