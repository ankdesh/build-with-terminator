"""Audited DRC Rule Catalog mapping category names to source spans and constraints.

Maintains canonical definitions, physical constraints, layer bindings, and handles
upstream deck anomalies (such as blank categories or duplicate category names).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .config import DRCParserError
from .deck_extractor import DRCDeckExtractor, ExtractedDeck


@dataclass(frozen=True)
class RuleConstraint:
    """A geometric constraint enforced by a DRC rule."""

    constraint_type: str  # "min_width", "min_spacing", "min_area", "min_enclosure"
    value_um: float
    condition: str | None = None  # e.g., "parallel_run_length > 36nm"


@dataclass(frozen=True)
class DRCRuleDefinition:
    """Complete specification of a DRC rule with source provenance and semantics."""

    rule_id: str
    category_name: str
    description: str
    target_layers: tuple[str, ...]
    constraints: tuple[RuleConstraint, ...]
    source_deck: str = ""
    source_line_start: int = 0
    source_line_end: int = 0
    raw_source_snippet: str = ""
    is_ambiguous: bool = False
    upstream_anomaly: str | None = None


# Known audited definitions for ASAP7 BEOL rules
ASAP7_AUDITED_RULES: Final[dict[str, DRCRuleDefinition]] = {
    "M1.W.1": DRCRuleDefinition(
        rule_id="M1.W.1",
        category_name="M1.W.1",
        description="M1 minimum width is 18nm",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(constraint_type="min_width", value_um=0.018),
        ),
    ),
    "M2.W.1": DRCRuleDefinition(
        rule_id="M2.W.1",
        category_name="M2.W.1",
        description="M2 minimum width is 18nm",
        target_layers=("M2",),
        constraints=(
            RuleConstraint(constraint_type="min_width", value_um=0.018),
        ),
    ),
    "M1.A.1": DRCRuleDefinition(
        rule_id="M1.A.1",
        category_name="M1.A.1",
        description="M1 minimum area is 504nm2 (0.000504 um2)",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(constraint_type="min_area", value_um=0.000504),
        ),
    ),
    "M2.A.1": DRCRuleDefinition(
        rule_id="M2.A.1",
        category_name="M2.A.1",
        description="M2 minimum area is 504nm2 (0.000504 um2)",
        target_layers=("M2",),
        constraints=(
            RuleConstraint(constraint_type="min_area", value_um=0.000504),
        ),
    ),
    "M1.S.1": DRCRuleDefinition(
        rule_id="M1.S.1",
        category_name="M1.S.1",
        description="M1 minimum spacing between edges when both edges > 36nm is 18nm",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(
                constraint_type="min_spacing",
                value_um=0.018,
                condition="both_edges_gt_36nm",
            ),
        ),
    ),
    "M1.S.2": DRCRuleDefinition(
        rule_id="M1.S.2",
        category_name="  ",  # Deck anomaly: emitted as whitespace
        description="M1 minimum spacing between edges when one edge > 36nm is 25nm",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(
                constraint_type="min_spacing",
                value_um=0.025,
                condition="one_edge_gt_36nm",
            ),
        ),
        upstream_anomaly="Deck outputs blank whitespace category '  ' instead of 'M1.S.2'",
    ),
    "M2.S.1": DRCRuleDefinition(
        rule_id="M2.S.1",
        category_name="M2.S.1",
        description="M2 minimum spacing between edges when both edges > 36nm is 18nm",
        target_layers=("M2",),
        constraints=(
            RuleConstraint(
                constraint_type="min_spacing",
                value_um=0.018,
                condition="both_edges_gt_36nm",
            ),
        ),
    ),
    "V1.M1.EN.1": DRCRuleDefinition(
        rule_id="V1.M1.EN.1",
        category_name="V1.M1.EN.1",
        description="Minimum enclosure of V1 by M1 on at least two opposite sides is 5nm and 2nm",
        target_layers=("M1", "V1"),
        constraints=(
            RuleConstraint(
                constraint_type="min_enclosure",
                value_um=0.002,
                condition="two_connected_sides",
            ),
            RuleConstraint(
                constraint_type="min_enclosure",
                value_um=0.005,
                condition="two_opposite_sides",
            ),
        ),
        upstream_anomaly="Reused category across two distinct enclosure checks in deck",
    ),
    # Legacy mini rules
    "M1_W": DRCRuleDefinition(
        rule_id="M1_W",
        category_name="M1_W",
        description="M1 minimum width is 18nm (legacy mini)",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(constraint_type="min_width", value_um=0.018),
        ),
    ),
    "M1_S": DRCRuleDefinition(
        rule_id="M1_S",
        category_name="M1_S",
        description="M1 minimum spacing is 18nm (legacy mini)",
        target_layers=("M1",),
        constraints=(
            RuleConstraint(constraint_type="min_spacing", value_um=0.018),
        ),
    ),
    "V1_M1_ENC": DRCRuleDefinition(
        rule_id="V1_M1_ENC",
        category_name="V1_M1_ENC",
        description="V1 minimum enclosure by M1 is 9nm (legacy mini)",
        target_layers=("M1", "V1"),
        constraints=(
            RuleConstraint(constraint_type="min_enclosure", value_um=0.009),
        ),
    ),
}


class DRCRuleCatalog:
    """Audited catalog of DRC rules indexing categories, layers, and constraints."""

    def __init__(self) -> None:
        """Initialize catalog with audited rules."""
        self._rules_by_id: dict[str, DRCRuleDefinition] = dict(ASAP7_AUDITED_RULES)
        self._category_to_id: dict[str, str] = {}
        self._rebuild_indices()

    def _rebuild_indices(self) -> None:
        """Rebuild secondary lookup indices."""
        self._category_to_id.clear()
        for rule_id, rule in self._rules_by_id.items():
            self._category_to_id[rule.category_name] = rule_id
            # Also index trimmed category name
            stripped = rule.category_name.strip()
            if stripped and stripped not in self._category_to_id:
                self._category_to_id[stripped] = rule_id

    def register_rule(self, rule: DRCRuleDefinition) -> None:
        """Register or override a rule definition."""
        self._rules_by_id[rule.rule_id] = rule
        self._rebuild_indices()

    def get_rule_by_id(self, rule_id: str) -> DRCRuleDefinition | None:
        """Look up rule definition by canonical rule ID."""
        return self._rules_by_id.get(rule_id)

    def get_rule_by_category(self, category_name: str) -> DRCRuleDefinition | None:
        """Look up rule definition by checker category string.

        Handles whitespace anomalies (e.g. '  ' -> M1.S.2).
        """
        if category_name in self._category_to_id:
            rule_id = self._category_to_id[category_name]
            return self._rules_by_id.get(rule_id)

        # Check if stripped whitespace maps to M1.S.2 anomaly
        if not category_name.strip():
            return self._rules_by_id.get("M1.S.2")

        stripped = category_name.strip()
        if stripped in self._category_to_id:
            rule_id = self._category_to_id[stripped]
            return self._rules_by_id.get(rule_id)

        return None

    def get_rules_for_layer(self, layer_name: str) -> list[DRCRuleDefinition]:
        """Return all rules applicable to a given physical layer."""
        return [
            rule for rule in self._rules_by_id.values()
            if layer_name in rule.target_layers
        ]

    def bind_deck_provenance(self, deck_path: Path) -> None:
        """Scan an extracted DRC deck to bind source line ranges and snippets to catalog rules.

        Args:
            deck_path: Path to the .lydrc or .drc deck.
        """
        extractor = DRCDeckExtractor()
        extracted: ExtractedDeck = extractor.extract(deck_path)

        for line_idx, line in enumerate(extracted.script_lines, start=1):
            for rule_id, rule in list(self._rules_by_id.items()):
                # Check for output match: e.g. .output("M1.W.1"
                cat = rule.category_name
                pattern = f'.output("{cat}"'
                if pattern in line:
                    actual_line = extracted.text_start_line + line_idx - 1 if extracted.is_xml_macro else line_idx
                    updated = DRCRuleDefinition(
                        rule_id=rule.rule_id,
                        category_name=rule.category_name,
                        description=rule.description,
                        target_layers=rule.target_layers,
                        constraints=rule.constraints,
                        source_deck=deck_path.name,
                        source_line_start=actual_line,
                        source_line_end=actual_line,
                        raw_source_snippet=line.strip(),
                        is_ambiguous=rule.is_ambiguous,
                        upstream_anomaly=rule.upstream_anomaly,
                    )
                    self.register_rule(updated)
