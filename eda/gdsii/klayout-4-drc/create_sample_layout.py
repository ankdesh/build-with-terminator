import klayout.db as db
import os

def create_sample_layout(filename="asap7_test.gds"):
    layout = db.Layout()
    layout.dbu = 0.001  # 1nm database units

    # Layer mapping
    l_m1 = layout.layer(18, 0)
    l_v1 = layout.layer(19, 0)

    top = layout.create_cell("TOP")

    # 1. Width Violation (M1 width < 18nm)
    # We will create a wire of 10nm width
    # Box(left, bottom, right, top) in DBU
    # Let's create it at (x=0, y=0) to (x=10, y=100) -> 10nm width
    top.shapes(l_m1).insert(db.Box(0, 0, 10, 100))

    # 2. Spacing Violation (M1 spacing < 18nm)
    # We will create two 20nm wide wires separated by 10nm
    top.shapes(l_m1).insert(db.Box(100, 0, 120, 100))
    top.shapes(l_m1).insert(db.Box(130, 0, 150, 100)) # Gap is 10nm

    # 3. Enclosure Violation (V1 not enclosed by M1 by at least 9nm)
    # V1 is typically 18x18nm.
    # We will make V1 18x18, and M1 exactly 18x18 (0nm enclosure)
    top.shapes(l_v1).insert(db.Box(200, 0, 218, 18))
    top.shapes(l_m1).insert(db.Box(200, 0, 218, 18))

    # Let's add a perfectly valid structure for reference
    # M1 20nm width, proper spacing, proper enclosure
    top.shapes(l_m1).insert(db.Box(300, 0, 320, 100))
    top.shapes(l_v1).insert(db.Box(301, 10, 319, 28)) # Enclosure > 9nm (Oh wait, 1nm left/right. We need 9nm. So M1 needs to be larger)
    
    # Valid enclosure: V1 = 18x18, M1 needs to be at least 18 + 2*9 = 36x36
    top.shapes(l_m1).insert(db.Box(400, 0, 436, 100))
    top.shapes(l_v1).insert(db.Box(409, 10, 427, 28)) # exactly 9nm enclosed

    layout.write(filename)
    print(f"Sample layout '{filename}' generated.")

if __name__ == "__main__":
    create_sample_layout()
