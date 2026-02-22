import klayout.db as db
import sys

def read_sample_gds(filename="sample.gds"):
    # Create an empty layout
    layout = db.Layout()

    try:
        # Load the GDS file into the layout
        layout.read(filename)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        sys.exit(1)

    print(f"--- Information for '{filename}' ---")
    print(f"Database Unit (DBU): {layout.dbu} um")

    # Iterate over all cells (including uncalled ones)
    for cell in layout.each_cell():
        print(f"\nCell Name: {cell.name}")

        # Number of shapes in total per cell
        print(f"  Total Layers in Cell:")

        # Iterate over all defined layers
        for layer_index in layout.layer_indexes():
            shapes = cell.shapes(layer_index)
            if not shapes.is_empty():
                layer_info = layout.get_info(layer_index)
                print(f"    - Layer {layer_info.layer}, Datatype {layer_info.datatype}: {shapes.size()} shape(s)")
                
                # Check for specific shapes
                for shape in shapes.each():
                    if shape.is_box():
                        # Coordinates are returned in DBU. Converting to user units (um).
                        box = shape.box
                        width = box.width() * layout.dbu
                        height = box.height() * layout.dbu
                        print(f"      Found Box (Width: {width:.2f} um, Height: {height:.2f} um)")
                    elif shape.is_polygon():
                        print(f"      Found Polygon with {shape.polygon.num_points()} point(s)")
                    elif shape.is_text():
                        print(f"      Found Text: '{shape.text_string}'")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        read_sample_gds(sys.argv[1])
    else:
        read_sample_gds()
