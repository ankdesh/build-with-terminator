import sys
import klayout.db as db

def fix_layout(input_gds: str, output_gds: str):
    layout = db.Layout()
    layout.read(input_gds)
    top_cell = layout.top_cell()
    
    m1_layer = layout.layer(18, 0)
    v1_layer = layout.layer(19, 0)
    
    m1_reg = db.Region(top_cell.shapes(m1_layer))
    v1_reg = db.Region(top_cell.shapes(v1_layer))
    
    # Fix M1 minimum width violations
    # Identify narrow polygons and expand them
    for shape in m1_reg.each():
        if shape.polygon.area() < 72:  # Area check for minimum width
            healed_region = shape.polygon.sized(16)  # Expand by 16 DBU
            m1_reg = m1_reg - shape + healed_region

    # Fix M1 minimum spacing violations
    # Identify adjacent polygons and adjust spacing
    for shape_a in m1_reg.each():
        for shape_b in m1_reg.each():
            if shape_a != shape_b and shape_a.bbox().overlaps(shape_b.bbox()):
                keepout = shape_a.polygon.sized(36)  # 18nm spacing
                m1_reg = m1_reg - keepout

    # Fix V1 minimum enclosure by M1 violations
    for shape in v1_reg.each():
        v1_enclosure_target = shape.polygon.sized(36)  # 9nm enclosure
        m1_reg = m1_reg + v1_enclosure_target

    # Commit changes
    top_cell.shapes(m1_layer).clear()
    top_cell.shapes(m1_layer).insert(m1_reg)
    layout.write(output_gds)

if __name__ == "__main__":
    in_gds = sys.argv[1] if len(sys.argv) > 1 else "input.gds"
    out_gds = sys.argv[2] if len(sys.argv) > 2 else "fixed.gds"
    fix_layout(in_gds, out_gds)