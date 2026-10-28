"""Conservative marker matching in a common physical coordinate frame."""
from .parser import DRCReportData
from .marker_geometry import BoxMarker, EdgeMarker, EdgePairMarker, PolygonMarker


def canonical_geometry(geometry):
    marker = geometry.marker
    def edge(value):
        return tuple(sorted(((value.p1.x, value.p1.y), (value.p2.x, value.p2.y))))
    if isinstance(marker, BoxMarker):
        return ("box", marker.bbox)
    if isinstance(marker, EdgeMarker):
        return ("edge", edge(marker))
    if isinstance(marker, EdgePairMarker):
        return ("edge_pair", tuple(sorted((edge(marker.edge1), edge(marker.edge2)))))
    if isinstance(marker, PolygonMarker):
        points = [(p.x, p.y) for p in marker.points]
        if points and points[0] == points[-1]:
            points.pop()
        rotations = [tuple(seq[i:]+seq[:i]) for seq in (points, list(reversed(points))) for i in range(len(seq))]
        return ("polygon", min(rotations) if rotations else (), geometry.representation if "/" in geometry.representation else "")
    return (geometry.kind, geometry.representation)


def marker_records(report: DRCReportData) -> list[dict]:
    records = []
    for category in report.categories:
        for item in category.violations:
            records.append({"rule": category.name, "cell": item.cell_name,
                            "geometry": sorted((canonical_geometry(g) for g in item.geometries), key=str),
                            "boxes": sorted(g.bbox_um for g in item.geometries if g.bbox_um is not None)})
    return sorted(records, key=lambda r: (r["rule"], r["cell"], str(r["geometry"])))


def compare_markers(before: DRCReportData, after: DRCReportData, grid_um: float) -> dict:
    """Exact identity first, then mutual unique matches within one grid step.

    Reports from different checker frames must not be compared. The caller enforces
    identical deck, profile, top cell and parameters. Unknown geometry is ambiguous.
    """
    left, right = marker_records(before), marker_records(after)
    remaining = set(range(len(right)))
    pending = []
    persisted = 0
    for record in left:
        matches = [j for j in sorted(remaining) if right[j] == record and record["boxes"]]
        if matches:
            remaining.remove(matches[0]); persisted += 1
        else:
            pending.append(record)

    def close(a, b):
        return (a["rule"] == b["rule"] and a["cell"] == b["cell"]
                and len(a["boxes"]) == len(b["boxes"]) and bool(a["boxes"])
                and all(abs(x-y) <= grid_um + 1e-12
                        for box_a, box_b in zip(a["boxes"], b["boxes"])
                        for x, y in zip(box_a, box_b)))

    links = {i: [j for j in sorted(remaining) if close(a, right[j])] for i, a in enumerate(pending)}
    matched_left, matched_right = set(), set()
    ambiguous_left, ambiguous_right = set(), set()
    for i, js in links.items():
        if len(js) == 1 and sum(js[0] in other for other in links.values()) == 1:
            matched_left.add(i); matched_right.add(js[0]); persisted += 1
        elif js:
            ambiguous_left.add(i); ambiguous_right.update(js)
        elif not pending[i]["boxes"]:
            ambiguous_left.add(i)
    ambiguous_right.update(j for j in remaining if not right[j]["boxes"])
    return {"persisted": persisted,
            "resolved": len(pending) - len(matched_left | ambiguous_left),
            "introduced": len(remaining - matched_right - ambiguous_right),
            "ambiguous": len(ambiguous_left) + len(ambiguous_right),
            "tolerance_um": grid_um, "frame": "checker_cell", "method": "exact_then_mutual_unique_bbox"}
