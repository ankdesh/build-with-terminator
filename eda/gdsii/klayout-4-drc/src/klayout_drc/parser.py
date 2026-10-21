"""Parser for KLayout DRC Report Databases (.lyrdb) and layout targets.

Extracts rule violation categories, individual violation geometries,
coordinates, and multiplicities into strongly-typed data structures.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import klayout.rdb as rdb
import klayout.db as db

from .config import DRCParserError
from .marker_geometry import (
    BoxMarker,
    EdgeMarker,
    EdgePairMarker,
    MarkerGeometry,
    PolygonMarker,
)


@dataclass
class ViolationGeometry:
    """Represents a geometric shape causing a rule violation."""
    kind: str  # 'polygon', 'box', 'edge', 'edge_pair', 'path', 'text', 'shape'
    representation: str
    details: dict[str, Any] = field(default_factory=dict)
    marker: EdgePairMarker | EdgeMarker | PolygonMarker | BoxMarker | None = None

    @property
    def bbox_um(self) -> tuple[float, float, float, float] | None:
        """Bounding box (min_x, min_y, max_x, max_y) in physical micrometers."""
        if self.marker and hasattr(self.marker, "bbox"):
            return self.marker.bbox
        return None


@dataclass
class ViolationItem:
    """An individual DRC violation instance."""
    item_id: int
    category_name: str
    cell_name: str
    geometries: list[ViolationGeometry] = field(default_factory=list)


@dataclass
class RuleCategory:
    """A DRC rule category containing violations."""
    name: str
    description: str
    violations: list[ViolationItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Total number of violations for this rule."""
        return len(self.violations)


@dataclass
class DRCReportData:
    """Structured collection of all violations discovered during DRC."""
    source_path: Path
    categories: list[RuleCategory] = field(default_factory=list)

    @property
    def total_violations(self) -> int:
        """Total count of all violations across all rules."""
        return sum(cat.count for cat in self.categories)

    @property
    def rule_summary(self) -> dict[str, int]:
        """Summary mapping rule category names to violation counts."""
        return {cat.name: cat.count for cat in self.categories}

    def to_dict(self) -> dict[str, Any]:
        """Serialize data to a dictionary suitable for JSON serialization."""
        return {
            "source_path": str(self.source_path),
            "total_violations": self.total_violations,
            "rules": [
                {
                    "name": cat.name,
                    "description": cat.description,
                    "count": cat.count,
                    "violations": [
                        {
                            "item_id": v.item_id,
                            "cell": v.cell_name,
                            "geometries": [
                                {
                                    "kind": g.kind,
                                    "representation": g.representation,
                                    "details": g.details,
                                }
                                for g in v.geometries
                            ],
                        }
                        for v in cat.violations
                    ],
                }
                for cat in self.categories
            ],
        }


class DRCParser:
    """Parses KLayout report databases (.lyrdb) and target GDS files."""

    def parse(self, report_path: Path) -> DRCReportData:
        """Parse the given report file into a structured DRCReportData model.
        
        Args:
            report_path: Path to the .lyrdb file or fallback .target.gds file.
            
        Returns:
            DRCReportData: Strongly-typed structured report data.
            
        Raises:
            DRCParserError: If the report file cannot be read or parsed.
        """
        report_path = report_path.resolve()
        if not report_path.exists():
            raise DRCParserError(f"Report file not found: {report_path}")

        # Check if the file is a ReportDatabase (.lyrdb)
        if report_path.suffix == ".lyrdb" or self._is_lyrdb_content(report_path):
            return self._parse_lyrdb(report_path)

        # Fallback to layout file parsing
        if report_path.suffix in (".gds", ".oas"):
            return self._parse_layout(report_path)

        raise DRCParserError(f"Unsupported report format: {report_path.suffix}")

    def _is_lyrdb_content(self, path: Path) -> bool:
        """Check if file starts with XML report-database header."""
        try:
            with open(path, "rb") as f:
                header = f.read(256)
                return b"<report-database" in header
        except OSError:
            return False

    def _parse_lyrdb(self, lyrdb_path: Path) -> DRCReportData:
        """Parse standard KLayout ReportDatabase."""
        report = rdb.ReportDatabase()
        try:
            report.load(str(lyrdb_path))
        except RuntimeError as exc:
            raise DRCParserError(f"Failed to load KLayout report database: {exc}") from exc

        categories: list[RuleCategory] = []
        for cat in report.each_category():
            cat_name = cat.name().strip("'\"")
            rule_cat = RuleCategory(name=cat_name, description=cat.description or "")
            items = [item for item in report.each_item() if item.category_id() == cat.rdb_id()]
            
            for idx, item in enumerate(items, 1):
                # Retrieve cell name if available
                cell_name = ""
                try:
                    cell_obj = report.cell_by_id(item.cell_id())
                    cell_name = cell_obj.name() if cell_obj else ""
                except Exception:
                    pass

                v_item = ViolationItem(
                    item_id=idx,
                    category_name=cat_name,
                    cell_name=cell_name,
                )

                for val in item.each_value():
                    kind = "shape"
                    rep = val.to_s()
                    if val.is_polygon():
                        kind = "polygon"
                        rep = val.polygon().to_s()
                    elif val.is_box():
                        kind = "box"
                        rep = val.box().to_s()
                    elif val.is_edge():
                        kind = "edge"
                        rep = val.edge().to_s()
                    elif val.is_edge_pair():
                        kind = "edge_pair"
                        rep = val.edge_pair().to_s()
                    elif val.is_path():
                        kind = "path"
                        rep = val.path().to_s()
                    elif val.string:
                        kind = "text"
                        rep = val.string

                    marker = MarkerGeometry.parse_value_string(rep, kind=kind)
                    v_item.geometries.append(
                        ViolationGeometry(kind=kind, representation=rep, marker=marker)
                    )

                rule_cat.violations.append(v_item)

            if rule_cat.count > 0:
                categories.append(rule_cat)

        return DRCReportData(source_path=lyrdb_path, categories=categories)

    def _parse_layout(self, gds_path: Path) -> DRCReportData:
        """Parse fallback layout (.gds) containing error markers."""
        layout = db.Layout()
        try:
            layout.read(str(gds_path))
        except RuntimeError as exc:
            raise DRCParserError(f"Failed to read layout file: {exc}") from exc

        categories: list[RuleCategory] = []
        for layer_index in layout.layer_indexes():
            layer_info = layout.get_info(layer_index)
            cat_name = f"Layer_{layer_info.layer}_{layer_info.datatype}"
            cat_desc = f"Violations on layer {layer_info.layer}/{layer_info.datatype}"
            rule_cat = RuleCategory(name=cat_name, description=cat_desc)

            violation_idx = 1
            for cell in layout.each_cell():
                shapes = cell.shapes(layer_index)
                for shape in shapes.each():
                    v_item = ViolationItem(
                        item_id=violation_idx,
                        category_name=cat_name,
                        cell_name=cell.name,
                    )
                    if shape.is_polygon():
                        v_item.geometries.append(
                            ViolationGeometry(kind="polygon", representation=shape.polygon.to_s())
                        )
                    elif shape.is_box():
                        v_item.geometries.append(
                            ViolationGeometry(kind="box", representation=shape.box.to_s())
                        )
                    elif shape.is_path():
                        v_item.geometries.append(
                            ViolationGeometry(kind="path", representation=shape.path.to_s())
                        )
                    elif shape.is_edge():
                        v_item.geometries.append(
                            ViolationGeometry(kind="edge", representation=shape.edge.to_s())
                        )
                    elif shape.is_text():
                        v_item.geometries.append(
                            ViolationGeometry(kind="text", representation=shape.text.string)
                        )
                    else:
                        v_item.geometries.append(
                            ViolationGeometry(kind="shape", representation=shape.to_s())
                        )
                    rule_cat.violations.append(v_item)
                    violation_idx += 1

            if rule_cat.count > 0:
                categories.append(rule_cat)

        return DRCReportData(source_path=gds_path, categories=categories)
