"""DRC rule deck context processor.

Extracts rule definitions, parameter thresholds, and related comments from a DRC deck
matching specific violated rule categories found in the violation database.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Sequence

from .deck_extractor import DRCDeckExtractor
from .rule_catalog import DRCRuleCatalog
from .config import DRCConfigurationError, DRCParserError


@dataclass(frozen=True)
class ExtractedRuleInfo:
    """Structured information extracted for a specific DRC rule."""
    rule_name: str
    code_block: str
    comment: Optional[str] = None
    threshold_um: Optional[float] = None


class DRCContextProcessor:
    """Parses DRC decks and extracts contextual rule definitions for violated rules."""

    def __init__(self, drc_script_path: Path | str):
        self.drc_script_path = Path(drc_script_path).resolve()
        if not self.drc_script_path.exists():
            raise DRCConfigurationError(f"DRC script not found: {self.drc_script_path}")

    def extract_rules_for_violations(
        self, violated_rule_names: Sequence[str]
    ) -> dict[str, ExtractedRuleInfo]:
        """Extract rule code blocks from the DRC deck for all specified rule names.

        Args:
            violated_rule_names: Sequence of rule category strings (e.g. ['M1_W', 'M1_S']).

        Returns:
            Dictionary mapping rule name to ExtractedRuleInfo.
        """
        try:
            deck_content = DRCDeckExtractor().extract(self.drc_script_path).script_text
        except OSError as e:
            raise DRCParserError(f"Failed to read DRC deck '{self.drc_script_path}': {e}") from e

        catalog = DRCRuleCatalog()
        catalog.bind_deck_provenance(self.drc_script_path)
        extracted: dict[str, ExtractedRuleInfo] = {}
        lines = deck_content.splitlines()

        for rule_name in violated_rule_names:
            audited = catalog.get_rule_by_category(rule_name)
            if audited and audited.source_branches:
                constraints = "; ".join(f"{c.constraint_type}={c.value_um:g} {c.unit}" + (f" ({c.condition})" if c.condition else "") for c in audited.constraints)
                info = ExtractedRuleInfo(rule_name, audited.raw_source_snippet,
                    audited.description + "; " + constraints + f"; source lines {audited.source_line_start}-{audited.source_line_end}",
                    audited.constraints[0].value_um if audited.constraints and audited.constraints[0].unit == "um" else None)
            else:
                info = self._find_rule_in_lines(rule_name, lines)
            if info:
                extracted[rule_name] = info
            else:
                # Fallback if exact pattern not found
                extracted[rule_name] = ExtractedRuleInfo(
                    rule_name=rule_name,
                    code_block=f"# Rule '{rule_name}' was flagged in .lyrdb but exact definition was not isolated in deck",
                )

        return extracted

    def format_as_text(self, violated_rule_names: Sequence[str]) -> str:
        """Format the extracted rule definitions into a structured text prompt section."""
        extracted = self.extract_rules_for_violations(violated_rule_names)

        lines = [
            "=== DRC Rules Context ===",
            f"Source DRC Deck: {self.drc_script_path.name}",
            f"Total Violated Rules to Inspect: {len(violated_rule_names)}",
            "",
        ]

        for rule_name in sorted(violated_rule_names):
            info = extracted.get(rule_name)
            if not info:
                continue

            lines.append(f"--- Rule: {rule_name} ---")
            if info.comment:
                lines.append(f"Description: {info.comment}")
            if info.threshold_um is not None:
                lines.append(f"Constraint Threshold: {info.threshold_um:.8g} um ({info.threshold_um * 1000:.1f} nm)")
            lines.append("Code Definition:")
            for code_line in info.code_block.splitlines():
                lines.append(f"  {code_line}")
            lines.append("")

        return "\n".join(lines).strip()

    def _find_rule_in_lines(self, rule_name: str, lines: list[str]) -> Optional[ExtractedRuleInfo]:
        """Search lines for output declarations matching rule_name."""
        target_idx = -1
        # Match .output("RULE_NAME" or rule "RULE_NAME"
        pattern = re.compile(rf'["\']{re.escape(rule_name)}["\']')

        for idx, line in enumerate(lines):
            if pattern.search(line):
                target_idx = idx
                break

        if target_idx == -1:
            return None

        # Collect leading comments if any
        comment_lines = []
        c_idx = target_idx - 1
        while c_idx >= 0 and lines[c_idx].strip().startswith("#"):
            comment_lines.insert(0, lines[c_idx].strip().lstrip("#").strip())
            c_idx -= 1

        comment = " ".join(comment_lines) if comment_lines else None

        # Extract code line or block
        code_line = lines[target_idx].strip()

        # Try to extract numerical threshold (e.g. 0.018 or 18.nm)
        threshold_match = re.search(r'\((\d+\.?\d*)\s*,', code_line)
        threshold_um = float(threshold_match.group(1)) if threshold_match else None

        return ExtractedRuleInfo(
            rule_name=rule_name,
            code_block=code_line,
            comment=comment,
            threshold_um=threshold_um,
        )
