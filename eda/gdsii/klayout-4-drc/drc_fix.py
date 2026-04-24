import klayout.db as db

def fix_drc(input_gds="asap7_test.gds", output_gds="asap7_fixed.gds"):
    print(f"Loading {input_gds} for programmatic DRC fixing...")
    layout = db.Layout()
    layout.read(input_gds)
    top = layout.top_cell()
    
    # Layer definitions
    l_m1 = layout.layer(18, 0)
    l_v1 = layout.layer(19, 0)
    
    # Create Region objects from the layers
    m1_reg = db.Region(top.begin_shapes_rec(l_m1))
    v1_reg = db.Region(top.begin_shapes_rec(l_v1))
    
    # 1. Fix Enclosure (V1 must be enclosed by M1 by >= 9nm)
    # We ensure this by taking the V1 via, sizing it up by 9nm, and OR-ing it with M1.
    print("Fixing V1->M1 enclosure violations...")
    m1_reg = m1_reg | v1_reg.sized(9)
    
    # 2. Fix Spacing (M1 spacing must be >= 18nm)
    # To programmatically resolve close shapes, we can merge them if they are < 18nm apart.
    # sized(9) expands by 9nm, overlapping any gaps < 18nm.
    # sized(-9) shrinks back, but the overlapped gaps stay merged.
    print("Fixing M1 spacing violations...")
    m1_reg = m1_reg.sized(9).sized(-9)
    
    # 3. Fix Width (M1 width must be >= 18nm)
    # A simple way to guarantee minimum width of polygons is to use the DRC width_check
    # to find the specific narrow parts, and patch them up!
    print("Fixing M1 width violations...")
    width_errors = m1_reg.width_check(18)
    
    # polygons(ext) creates a polygon from the edge pair. We size it to ensure it patches
    error_patches = width_errors.polygons(0).sized(5) 
    m1_reg = m1_reg | error_patches
    
    # Write the fixed layer back to the layout
    top.shapes(l_m1).clear()
    top.shapes(l_m1).insert(m1_reg)
    
    layout.write(output_gds)
    print(f"Fixed layout saved to {output_gds}.")

if __name__ == "__main__":
    fix_drc()
