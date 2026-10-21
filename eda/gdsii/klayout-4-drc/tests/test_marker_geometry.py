"""Unit tests for typed RDB marker geometry models and parsing (PR B-2)."""

import pytest

from klayout_drc.marker_geometry import (
    BoxMarker,
    EdgeMarker,
    EdgePairMarker,
    MarkerGeometry,
    Point,
    PolygonMarker,
)


def test_point_operations():
    """Verify point distance and quantization."""
    p1 = Point(0.0, 0.0)
    p2 = Point(3.0, 4.0)
    assert p1.distance_to(p2) == pytest.approx(5.0)

    p3 = Point(0.000251, 0.000499)
    p3_q = p3.quantize(0.00025)
    assert p3_q.x == pytest.approx(0.00025)
    assert p3_q.y == pytest.approx(0.00050)


def test_edge_pair_marker_parsing():
    """Verify parsing edge-pair string representations."""
    raw = "edge-pair: (0,0;0,0.1)|(0.018,0.1;0.018,0)"
    marker = MarkerGeometry.parse_value_string(raw)

    assert isinstance(marker, EdgePairMarker)
    assert marker.edge1.p1 == Point(0.0, 0.0)
    assert marker.edge1.p2 == Point(0.0, 0.1)
    assert marker.edge2.p1 == Point(0.018, 0.1)
    assert marker.edge2.p2 == Point(0.018, 0.0)

    assert marker.bbox == (0.0, 0.0, 0.018, 0.1)
    assert marker.separation_um == pytest.approx(0.018)


def test_edge_pair_slash_delimiter():
    """Verify parsing edge-pair strings that use '/' delimiter."""
    raw = "edge-pair: (0.218,0.018;0.218,0)/(0.218,0.018;0.218,0)"
    marker = MarkerGeometry.parse_value_string(raw)

    assert isinstance(marker, EdgePairMarker)
    assert marker.edge1.p1 == Point(0.218, 0.018)
    assert marker.edge1.p2 == Point(0.218, 0.0)


def test_box_marker_parsing():
    """Verify parsing box string representations."""
    raw = "box: (0,0;0.018,0.100)"
    marker = MarkerGeometry.parse_value_string(raw)

    assert isinstance(marker, BoxMarker)
    assert marker.x1 == 0.0
    assert marker.y1 == 0.0
    assert marker.x2 == 0.018
    assert marker.y2 == 0.100
    assert marker.width_um == pytest.approx(0.018)
    assert marker.height_um == pytest.approx(0.100)
    assert marker.area_um2 == pytest.approx(0.0018)


def test_polygon_marker_parsing():
    """Verify parsing polygon string representations."""
    raw = "polygon: ((0,0),(0.018,0),(0.018,0.1),(0,0.1))"
    marker = MarkerGeometry.parse_value_string(raw)

    assert isinstance(marker, PolygonMarker)
    assert len(marker.points) == 4
    assert marker.bbox == (0.0, 0.0, 0.018, 0.1)
    assert marker.area_um2 == pytest.approx(0.0018)


def test_parse_with_kind_hint():
    """Verify parsing without prefix when kind is supplied."""
    raw = "(0,0;0,0.1)|(0.018,0.1;0.018,0)"
    marker = MarkerGeometry.parse_value_string(raw, kind="edge_pair")

    assert isinstance(marker, EdgePairMarker)
    assert marker.separation_um == pytest.approx(0.018)
