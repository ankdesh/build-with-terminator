"""Typed geometric representations for KLayout ReportDatabase (RDB) markers.

Provides strongly typed marker geometry models (EdgeMarker, EdgePairMarker,
PolygonMarker, BoxMarker) with physical coordinate conversions and spatial hashing.
"""

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class Point:
    """A 2D coordinate in physical micrometers."""

    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        """Euclidean distance to another point."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def quantize(self, precision: float = 0.0001) -> "Point":
        """Return point with coordinates rounded to given precision."""
        return Point(
            x=round(self.x / precision) * precision,
            y=round(self.y / precision) * precision,
        )


@dataclass(frozen=True)
class EdgeMarker:
    """A directed edge violation marker."""

    p1: Point
    p2: Point

    @property
    def length_um(self) -> float:
        """Physical length in micrometers."""
        return self.p1.distance_to(self.p2)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) bounding box."""
        return (
            min(self.p1.x, self.p2.x),
            min(self.p1.y, self.p2.y),
            max(self.p1.x, self.p2.x),
            max(self.p1.y, self.p2.y),
        )


@dataclass(frozen=True)
class EdgePairMarker:
    """A pair of edges representing a spacing, width, or enclosure violation."""

    edge1: EdgeMarker
    edge2: EdgeMarker

    @property
    def separation_um(self) -> float:
        """Estimated separation distance between the two edges."""
        # Midpoint to midpoint distance as a representative separation
        mid1 = Point((self.edge1.p1.x + self.edge1.p2.x) / 2.0, (self.edge1.p1.y + self.edge1.p2.y) / 2.0)
        mid2 = Point((self.edge2.p1.x + self.edge2.p2.x) / 2.0, (self.edge2.p1.y + self.edge2.p2.y) / 2.0)
        return mid1.distance_to(mid2)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) bounding box covering both edges."""
        b1 = self.edge1.bbox
        b2 = self.edge2.bbox
        return (
            min(b1[0], b2[0]),
            min(b1[1], b2[1]),
            max(b1[2], b2[2]),
            max(b1[3], b2[3]),
        )


@dataclass(frozen=True)
class PolygonMarker:
    """A polygon boundary violation marker."""

    points: tuple[Point, ...]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) bounding box."""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def area_um2(self) -> float:
        """Area computed via surveyor's formula."""
        n = len(self.points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y
        return abs(area) / 2.0


@dataclass(frozen=True)
class BoxMarker:
    """An axis-aligned rectangular violation marker."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) bounding box."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )

    @property
    def width_um(self) -> float:
        return abs(self.x2 - self.x1)

    @property
    def height_um(self) -> float:
        return abs(self.y2 - self.y1)

    @property
    def area_um2(self) -> float:
        return self.width_um * self.height_um


class MarkerGeometry:
    """Factory and parser for converting KLayout RDB item values into typed markers."""

    @staticmethod
    def parse_value_string(raw_val: str, kind: str | None = None) -> EdgePairMarker | EdgeMarker | PolygonMarker | BoxMarker | None:
        """Parse native KLayout RDB string representations into typed markers.

        Handles:
          - edge-pair: (x1,y1;x2,y2)|(x3,y3;x4,y4) or (x1,y1;x2,y2)/(x3,y3;x4,y4)
          - edge: (x1,y1;x2,y2)
          - polygon: ((x1,y1),(x2,y2),...)
          - box: (x1,y1;x2,y2)
        """
        raw = raw_val.strip()

        if kind == "edge_pair" or raw.startswith("edge-pair:") or ("|" in raw and ";" in raw) or ("/" in raw and ";" in raw):
            body = raw
            if body.startswith("edge-pair:"):
                body = body[len("edge-pair:"):].strip()
            delim = "|" if "|" in body else ("/" if "/" in body else None)
            if delim:
                parts = body.split(delim)
                e1 = MarkerGeometry._parse_single_edge(parts[0].strip())
                e2 = MarkerGeometry._parse_single_edge(parts[1].strip())
                if e1 and e2:
                    return EdgePairMarker(edge1=e1, edge2=e2)

        if kind == "edge" or raw.startswith("edge:"):
            body = raw
            if body.startswith("edge:"):
                body = body[len("edge:"):].strip()
            return MarkerGeometry._parse_single_edge(body)

        if kind == "box" or raw.startswith("box:"):
            body = raw
            if body.startswith("box:"):
                body = body[len("box:"):].strip()
            body = body.strip("()")
            parts = body.split(";")
            if len(parts) == 2:
                p1 = MarkerGeometry._parse_point(parts[0])
                p2 = MarkerGeometry._parse_point(parts[1])
                if p1 and p2:
                    return BoxMarker(x1=p1.x, y1=p1.y, x2=p2.x, y2=p2.y)

        if kind == "polygon" or raw.startswith("polygon:"):
            body = raw
            if body.startswith("polygon:"):
                body = body[len("polygon:"):].strip()
            body = body.strip("()")
            pts: list[Point] = []
            tokens = body.replace("),(", ");(").split(";")
            for tok in tokens:
                p = MarkerGeometry._parse_point(tok)
                if p:
                    pts.append(p)
            if len(pts) >= 3:
                return PolygonMarker(points=tuple(pts))

        return None

    @staticmethod
    def _parse_point(token: str) -> Point | None:
        """Parse (x,y) string into Point."""
        cleaned = token.strip().strip("()")
        coords = cleaned.split(",")
        if len(coords) == 2:
            try:
                return Point(x=float(coords[0].strip()), y=float(coords[1].strip()))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_single_edge(token: str) -> EdgeMarker | None:
        """Parse (x1,y1;x2,y2) string into EdgeMarker."""
        cleaned = token.strip().strip("()")
        pts = cleaned.split(";")
        if len(pts) == 2:
            p1 = MarkerGeometry._parse_point(pts[0])
            p2 = MarkerGeometry._parse_point(pts[1])
            if p1 and p2:
                return EdgeMarker(p1=p1, p2=p2)
        return None
