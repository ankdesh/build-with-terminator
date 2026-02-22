import klayout.db as db

def create_sample_gds(filename="sample.gds"):
    # Create a new layout
    layout = db.Layout()

    # Default database unit is 1 nm (0.001 um)
    layout.dbu = 0.001

    # Create a top cell
    top = layout.create_cell("TOP")

    # Define some layers (layer number, datatype number)
    layer1 = layout.layer(1, 0)
    layer2 = layout.layer(2, 0)

    # 1. Add a simple box (rectangle)
    # Coordinates are in database units (dbu), so 10000 = 10 um
    box = db.Box(0, 0, 10000, 5000)
    top.shapes(layer1).insert(box)

    # 2. Add a polygon
    # Points are (x, y) coordinates in dbu
    points = [db.Point(0, 10000), db.Point(5000, 15000), db.Point(10000, 10000)]
    polygon = db.Polygon(points)
    top.shapes(layer2).insert(polygon)

    # 3. Add text
    text = db.Text("Hello KLayout", db.Trans(0, -2000))
    top.shapes(layer1).insert(text)

    # Save the layout to a file
    layout.write(filename)
    print(f"Successfully created '{filename}' with sample shapes.")

if __name__ == "__main__":
    create_sample_gds()
