import subprocess
import sys
import os
import argparse
import klayout.rdb as rdb
import klayout.db as db

def run_drc_textual(input_gds, drc_script):
    output_lyrdb = "temp_drc_report.lyrdb"
    output_gds = "temp_drc_target.gds"
    print(f"Running DRC analysis on {input_gds} using {drc_script}...")
    
    cmd = [
        "klayout",
        "-b",
        "-r", drc_script,
        "-rd", f"input={input_gds}",
        "-rd", f"report={output_lyrdb}",
        # Fallback for some test scripts that use different variable names
        "-rd", f"drc_test_source={input_gds}",
        "-rd", f"drc_test_target={output_gds}",
        "-rd", "drc_test_deep=false"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("DRC Engine failed or had warnings:")
        print(result.stderr)
    else:
        print("DRC Engine finished successfully. Parsing output...\n")
        
    print("=== DRC Violations Details ===")
    total_errors = 0
    found_output = False
    
    # 1. Check for Report Database (.lyrdb)
    if os.path.exists(output_lyrdb):
        found_output = True
        print("--- Found Report Database (.lyrdb) ---")
        report = rdb.ReportDatabase()
        try:
            report.load(output_lyrdb)
            
            for category in report.each_category():
                items = [item for item in report.each_item() if item.category_id() == category.rdb_id()]
                count = len(items)
                if count > 0:
                    print(f"\nRule: {category.name()} - {category.description}")
                    print(f"  -> {count} violation(s) found:")
                    for idx, item in enumerate(items, 1):
                        print(f"    Violation {idx}:")
                        for val in item.each_value():
                            if val.is_polygon(): print(f"      Polygon: {val.polygon().to_s()}")
                            elif val.is_box(): print(f"      Box: {val.box().to_s()}")
                            elif val.is_edge(): print(f"      Edge: {val.edge().to_s()}")
                            elif val.is_edge_pair(): print(f"      Edge pair: {val.edge_pair().to_s()}")
                            elif val.is_path(): print(f"      Path: {val.path().to_s()}")
                            elif val.string: print(f"      Text: {val.string}")
                    total_errors += count
        except RuntimeError as e:
            print(f"  Failed to load report database: {e}")
            found_output = False # Treat as not found so we can rely on layout if available
        
        try:
            os.remove(output_lyrdb)
        except OSError:
            pass

    # 2. Check for Layout output (.gds) - common in KLayout test suite
    if os.path.exists(output_gds):
        found_output = True
        print("\n--- Found Layout Output (.gds) ---")
        layout = db.Layout()
        layout.read(output_gds)
        
        for layer_index in layout.layer_indexes():
            layer_info = layout.get_info(layer_index)
            
            layer_errors = 0
            layer_text = []
            
            for cell in layout.each_cell():
                shapes = cell.shapes(layer_index)
                for shape in shapes.each():
                    layer_errors += 1
                    if shape.is_polygon(): layer_text.append(f"Polygon: {shape.polygon.to_s()}")
                    elif shape.is_box(): layer_text.append(f"Box: {shape.box.to_s()}")
                    elif shape.is_path(): layer_text.append(f"Path: {shape.path.to_s()}")
                    elif shape.is_edge(): layer_text.append(f"Edge: {shape.edge.to_s()}")
                    elif shape.is_text(): layer_text.append(f"Text: {shape.text.string}")
                    else: layer_text.append(f"Shape: {shape.to_s()}")
            
            if layer_errors > 0:
                print(f"\nLayer: {layer_info.layer}/{layer_info.datatype}")
                print(f"  -> {layer_errors} violation(s) found:")
                for i, txt in enumerate(layer_text, 1):
                    print(f"    Violation {i}:\n      {txt}")
                total_errors += layer_errors
        
        try:
            os.remove(output_gds)
        except OSError:
            pass
            
    if not found_output:
        print("Error: No DRC report database (.lyrdb) or layout output (.gds) was generated.")
        
    if total_errors == 0 and found_output:
        print("\nNo DRC violations found.")
        
    print(f"\n==============================")
    print(f"Total Violations: {total_errors}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run KLayout DRC and print textual violations.")
    parser.add_argument("drc_script", help="DRC script to use")
    parser.add_argument("in_gds", help="Input GDS file")
    
    args = parser.parse_args()
    print(f"Input GDS: {args.in_gds}, DRC Script: {args.drc_script}")
    run_drc_textual(args.in_gds, args.drc_script)
