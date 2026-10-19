"""GDS layout context processor.

Extracts local geometric bounding-box windows around violation coordinates with a configurable halo,
formatting the local layout polygon geometry and layer information into structured text for LLMs.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Optional

import klayout.db as db

from .config import (
    ASAP7_DBU_UM,
    DEFAULT_WINDOW_HALO_UM,
    DRCConfigurationError,
    DRCParserError,
)
from .parser import DRCReportData, ViolationItem


@dataclass(frozen=True)
class PolygonGeometry:
    """Representation of an extracted layout polygon in micrometers."""
    layer: int
    datatype: int
    points_um: list[tuple[float, float]]
    bbox_um: tuple[float, float, float, float]
    shape_type: str = "polygon"


@dataclass(frozen=True)
class ViolationNeighborhoodWindow:
    """A localized inspection window containing surrounding layout geometry around a violation."""
    violation_index: int
    rule_name: str
    cell_name: str
    marker_bbox_um: tuple[float, float, float, float]
    window_bbox_um: tuple[float, float, float, float]
    polygons: list[PolygonGeometry] = field(default_factory=list)


class GDSContextProcessor:
    """Inspects GDS layout geometry around violation coordinates and extracts structured sections."""

    def __init__(self, gds_path: Path | str, halo_um: float = DEFAULT_WINDOW_HALO_UM):
        self.gds_path = Path(gds_path).resolve()
        if not self.gds_path.exists():
            raise DRCConfigurationError(f"GDS file not found: {self.gds_path}")
        self.halo_um = halo_um

    def extract_windows_for_report(
        self,
        report_data: DRCReportData,
        max_windows_per_rule: int = 3,
    ) -> list[ViolationNeighborhoodWindow]:
        """Extract geometric neighborhood windows around violation coordinates.

        Args:
            report_data: Parsed DRC report data.
            max_windows_per_rule: Maximum number of violation windows per rule to avoid context explosion.

        Returns:
            List of ViolationNeighborhoodWindow objects containing local shapes.
        """
        try:
            layout = db.Layout()
            layout.read(str(self.gds_path))
        except Exception as e:
            raise DRCParserError(f"Failed to read GDS layout '{self.gds_path}': {e}") from e

        top_cell = layout.top_cell()
        if top_cell is None:
            raise DRCParserError(f"GDS layout '{self.gds_path}' does not have a top cell.")

        dbu = layout.dbu if layout.dbu > 0 else ASAP7_DBU_UM
        windows: list[ViolationNeighborhoodWindow] = []

        rule_counts: dict[str, int] = {}
        for cat in report_data.categories:
            for item in cat.violations:
                current_count = rule_counts.get(cat.name, 0)
                if current_count >= max_windows_per_rule:
                    continue
                rule_counts[cat.name] = current_count + 1

                window = self._extract_single_window(layout, top_cell, item, cat.name, dbu)
                if window:
                    windows.append(window)

        return windows

    def format_as_text(
        self,
        report_data: DRCReportData,
        max_windows_per_rule: int = 3,
    ) -> str:
        """Format the extracted layout windows into a structured text prompt."""
        windows = self.extract_windows_for_report(report_data, max_windows_per_rule)

        lines = [
            "=== GDS Layout Context (Violation Neighborhood Windows) ===",
            f"Layout File: {self.gds_path.name}",
            f"Window Halo Margin: {self.halo_um * 1000:.1f} nm ({self.halo_um:.4f} um)",
            f"Total Neighborhood Windows Extracted: {len(windows)}",
            "",
        ]

        for win in windows:
            lines.append(
                f"--- Window {win.violation_index}: Rule {win.rule_name} (Cell: {win.cell_name}) ---"
            )
            lines.append(
                f"Violation Marker Box (um): [{win.marker_bbox_um[0]:.4f}, {win.marker_bbox_um[1]:.4f}] to [{win.marker_bbox_um[2]:.4f}, {win.marker_bbox_um[3]:.4f}]"
            )
            lines.append(
                f"Inspection Window (um):    [{win.window_bbox_um[0]:.4f}, {win.window_bbox_um[1]:.4f}] to [{win.window_bbox_um[2]:.4f}, {win.window_bbox_um[3]:.4f}]"
            )
            lines.append(f"Intersecting Shapes Count: {len(win.polygons)}")

            if not win.polygons:
                lines.append("  (No intersecting shapes found on active layers within halo)")
            else:
                for idx, poly in enumerate(win.polygons, start=1):
                    lines.append(
                        f"  Shape {idx}: Layer {poly.layer}/{poly.datatype} ({poly.shape_type})"
                    )
                    lines.append(
                        f"    BBox (um): [{poly.bbox_um[0]:.4f}, {poly.bbox_um[1]:.4f}] to [{poly.bbox_um[2]:.4f}, {poly.bbox_um[3]:.4f}]"
                    )
                    pts_str = ", ".join(f"({x:.4f}, {y:.4f})" for x, y in poly.points_um[:8])
                    if len(poly.points_um) > 8:
                        pts_str += f"... ({len(poly.points_um)} vertices total)"
                    lines.append(f"    Vertices (um): [{pts_str}]")

            lines.append("")

        return "\n".join(lines).strip()

    def _extract_single_window(
        self,
        layout: db.Layout,
        cell: db.Cell,
        item: ViolationItem,
        rule_name: str,
        dbu: float,
    ) -> Optional[ViolationNeighborhoodWindow]:
        """Compute window bounding box and gather intersecting shapes."""
        points: list[tuple[float, float]] = []
        for geom in item.geometries:
            numbers = [float(n) for n in re.findall(r"[-+]?\d+(?:\.\d+)?", geom.representation)]
            for i in range(0, len(numbers) - 1, 2):
                points.append((numbers[i], numbers[i + 1]))

        if not points:
            return None

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        marker_bbox = (min_x, min_y, max_x, max_y)
        win_min_x = min_x - self.halo_um
        win_min_y = min_y - self.halo_um
        win_max_x = max_x + self.halo_um
        win_max_y = max_y + self.halo_um
        window_bbox = (win_min_x, win_min_y, win_max_x, win_max_y)

        # Build search box in integer DBU
        box_dbu = db.Box(
            int(round(win_min_x / dbu)),
            int(round(win_min_y / dbu)),
            int(round(win_max_x / dbu)),
            int(round(win_max_y / dbu)),
        )

        extracted_polys: list[PolygonGeometry] = []

        # Iterate through all layout layers
        for layer_info in layout.layer_infos():
            layer_idx = layout.layer(layer_info)
            shapes = cell.shapes(layer_idx)

            for shape in shapes.each_overlapping(box_dbu):
                if shape.is_box():
                    b = shape.box
                    pts = [
                        (b.left * dbu, b.bottom * dbu),
                        (b.right * dbu, b.bottom * dbu),
                        (b.right * dbu, b.top * dbu),
                        (b.left * dbu, b.top * dbu),
                    ]
                    poly_bbox = (b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)
                    extracted_polys.append(
                        PolygonGeometry(
                            layer=layer_info.layer,
                            datatype=layer_info.datatype,
                            points_um=pts,
                            bbox_um=poly_bbox,
                            shape_type="box",
                        )
                    )
                elif shape.is_polygon():
                    p = shape.polygon
                    pts = [(pt.x * dbu, pt.y * dbu) for pt in p.each_point_hull()]
                    b = p.bbox()
                    poly_bbox = (b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)
                    extracted_polys.append(
                        PolygonGeometry(
                            layer=layer_info.layer,
                            datatype=layer_info.datatype,
                            points_um=pts,
                            bbox_um=poly_bbox,
                            shape_type="polygon",
                        )
                    )

        return ViolationNeighborhoodWindow(
            violation_index=item.item_id,
            rule_name=rule_name,
            cell_name=item.cell_name or cell.name,
            marker_bbox_um=marker_bbox,
            window_bbox_um=window_bbox,
            polygons=extracted_polys,
        )
