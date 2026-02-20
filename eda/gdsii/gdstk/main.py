import gdstk
import os
import glob

def main():
    print("Hello from gdstk!")
    
    # Find a gds or gds2 file in the examples directory
    gds_files = glob.glob('../gds_samples/*.gds') + glob.glob('../gds_samples/*.gds2')
    if not gds_files:
        print("No .gds or .gds2 files found in examples directory.")
        return
        
    for file_path in gds_files:
        print(f"Loading {file_path}")
        
        # Read the GDSII file
        lib = gdstk.read_gds(file_path)
        
        print(f"Library name: {lib.name}")
        print(f"Number of cells: {len(lib.cells)}")
    
        for i, cell in enumerate(lib.cells[:5]):
            print(f"Cell {i+1}: {cell.name} - Polygons: {len(cell.polygons)}, Paths: {len(cell.paths)}, Labels: {len(cell.labels)}")
        
        if len(lib.cells) > 5:
            print(f"... and {len(lib.cells) - 5} more cells")

if __name__ == "__main__":
    main()
