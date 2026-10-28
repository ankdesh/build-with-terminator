#!/usr/bin/env python3
"""Check the final GDS hierarchy, routing layers, and physical scale against DEF."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

import klayout.db as kdb


def inspect(gds, def_file):
    layout = kdb.Layout()
    layout.read(str(gds))
    tops = list(layout.top_cells())
    if len(tops) != 1 or tops[0].name != "picorv32":
        raise ValueError("Expected exactly one GDS top cell named picorv32")
    top = tops[0]
    text = def_file.read_text()
    units = int(re.search(r"UNITS DISTANCE MICRONS\s+(\d+)\s*;", text).group(1))
    points = re.search(r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*"
                       r"\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*;", text)
    die = [int(v) / units for v in points.groups()]
    bbox = top.dbbox()
    bbox_um = [bbox.left, bbox.bottom, bbox.right, bbox.top]
    if max(abs(a - b) for a, b in zip(die, bbox_um)) > max(layout.dbu, 0.001):
        raise ValueError(f"GDS/DEF physical scale or bounds differ: {bbox_um} versus {die}")
    cells = list(layout.each_cell())
    empty = [cell.name for cell in cells if cell.is_empty()]
    if empty:
        raise ValueError("GDS has empty cells: " + ", ".join(empty))
    layers = []
    for index in layout.layer_indices():
        info = layout.get_info(index)
        stored = sum(cell.shapes(index).size() for cell in cells)
        if stored:
            layers.append({"layer": info.layer, "datatype": info.datatype,
                           "stored_shapes": stored, "top_shapes": top.shapes(index).size()})
    # Signal routes are drawn in the top cell by ORFS stream-out.
    routed_layers = {row["layer"] for row in layers if row["datatype"] == 0 and row["top_shapes"]}
    if not {20, 30, 40}.issubset(routed_layers):
        raise ValueError("Expected routed top-level M2, M3, and M4 shapes")
    children = collections.Counter()
    for instance in top.each_inst():
        children[instance.cell.name] += max(1, instance.na) * max(1, instance.nb)
    with gds.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"status": "passed", "gds": str(gds), "gds_sha256": digest,
            "klayout_python_version": kdb.__version__, "dbu_um": layout.dbu,
            "top_cell": top.name, "cell_count": len(cells), "empty_cells": empty,
            "gds_bbox_um": bbox_um, "def_die_um": die,
            "direct_instance_count": sum(children.values()),
            "direct_instances_by_master": dict(sorted(children.items())), "layers": layers,
            "scope": "Structure, routed geometry presence, and GDS/DEF scale. Not LVS or signoff DRC."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gds", type=Path, required=True)
    parser.add_argument("--def", dest="def_file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.gds.resolve(), args.def_file.resolve())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "top_cell", "dbu_um", "gds_bbox_um", "cell_count", "direct_instance_count")}, indent=2))


if __name__ == "__main__":
    main()
