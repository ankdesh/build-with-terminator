"""Unit and integration tests for DRC deck extraction and rule catalog (PR B-2)."""

from pathlib import Path
import pytest

from klayout_drc.config import DEFAULT_RULES_DIR
from klayout_drc.deck_extractor import DRCDeckExtractor
from klayout_drc.rule_catalog import DRCRuleCatalog


def test_drc_deck_extractor_xml_macro():
    """Verify that DRCDeckExtractor extracts Ruby script and decodes XML entities."""
    extractor = DRCDeckExtractor()
    deck_path = DEFAULT_RULES_DIR / "asap7.lydrc"
    extracted = extractor.extract(deck_path)

    assert extracted.is_xml_macro is True
    assert extracted.text_start_line > 1
    assert len(extracted.script_lines) > 100

    # Ensure XML entities like &gt; and &lt; are decoded in script_text
    assert "&gt;" not in extracted.script_text
    assert "&lt;" not in extracted.script_text
    assert "&amp;" not in extracted.script_text
    assert "> 36" in extracted.script_text or ">= 36" in extracted.script_text or "> 36 nm" in extracted.script_text


def test_drc_deck_extractor_plain_script():
    """Verify that DRCDeckExtractor handles plain DRC scripts like asap7_mini.drc."""
    extractor = DRCDeckExtractor()
    deck_path = DEFAULT_RULES_DIR / "asap7_mini.drc"
    extracted = extractor.extract(deck_path)

    assert extracted.is_xml_macro is False
    assert extracted.text_start_line == 1
    assert "M1_W" in extracted.script_text


def test_rule_catalog_lookups_and_anomalies():
    """Verify DRCRuleCatalog lookups, constraint values, and upstream anomaly handling."""
    catalog = DRCRuleCatalog()

    # Standard rule lookups
    m1_w = catalog.get_rule_by_category("M1.W.1")
    assert m1_w is not None
    assert m1_w.rule_id == "M1.W.1"
    assert m1_w.constraints[0].value_um == 0.018
    assert "M1" in m1_w.target_layers

    m1_a = catalog.get_rule_by_category("M1.A.1")
    assert m1_a is not None
    assert m1_a.constraints[0].value_um == 0.000504

    # Upstream anomaly 1: M1.S.2 blank output category in public deck
    m1_s2 = catalog.get_rule_by_category("  ")
    assert m1_s2 is not None
    assert m1_s2.rule_id == "M1.S.2"
    assert m1_s2.upstream_anomaly is not None
    assert m1_s2.constraints[0].value_um == 0.025

    # Upstream anomaly 2: V1.M1.EN.1 reused category across two constraint checks
    v1_enc = catalog.get_rule_by_category("V1.M1.EN.1")
    assert v1_enc is not None
    assert len(v1_enc.constraints) == 2
    assert v1_enc.upstream_anomaly is not None


def test_rule_catalog_bind_deck_provenance():
    """Verify binding source lines and snippets from the actual deck."""
    catalog = DRCRuleCatalog()
    deck_path = DEFAULT_RULES_DIR / "asap7.lydrc"
    catalog.bind_deck_provenance(deck_path)

    m1_w = catalog.get_rule_by_category("M1.W.1")
    assert m1_w is not None
    assert m1_w.source_deck == "asap7.lydrc"
    assert m1_w.source_line_start > 0
    assert 'm1.width(18.nm).output("M1.W.1"' in m1_w.raw_source_snippet
