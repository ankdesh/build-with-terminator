"""DRC deck extractor for unbundling KLayout XML macros into executable scripts.

Extracts Ruby DRC DSL text from <klayout-macro> XML envelopes, decodes XML/HTML
entities, and preserves source line provenance.
"""

from dataclasses import dataclass
import html
from pathlib import Path
import xml.etree.ElementTree as ET

from .config import DRCParserError


@dataclass(frozen=True)
class ExtractedDeck:
    """Represents extracted DRC script content and source provenance."""

    deck_path: Path
    script_text: str
    script_lines: tuple[str, ...]
    is_xml_macro: bool
    text_start_line: int


class DRCDeckExtractor:
    """Unbundles KLayout XML macro files (.lydrc) into raw DRC DSL scripts."""

    def extract(self, deck_path: Path) -> ExtractedDeck:
        """Extract the script DSL from a DRC deck file.

        Args:
            deck_path: Path to the .lydrc XML macro or plain .drc script.

        Returns:
            ExtractedDeck: Extracted script content with line provenance.

        Raises:
            DRCParserError: If the deck file cannot be read, XML is malformed,
                or <text> block is missing.
        """
        deck_path = Path(deck_path).resolve()
        if not deck_path.exists():
            raise DRCParserError(f"DRC deck file does not exist: {deck_path}")

        try:
            with open(deck_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            raise DRCParserError(f"Could not read DRC deck file {deck_path}: {exc}") from exc

        if "<klayout-macro>" in content:
            return self._extract_from_macro(deck_path, content)

        # Plain DRC script
        lines = tuple(content.splitlines())
        return ExtractedDeck(
            deck_path=deck_path,
            script_text=content,
            script_lines=lines,
            is_xml_macro=False,
            text_start_line=1,
        )

    def _extract_from_macro(self, deck_path: Path, content: str) -> ExtractedDeck:
        """Parse XML macro envelope and extract the <text> element content."""
        # Find start line of <text> in original content for line provenance
        text_start_line = 1
        for idx, line in enumerate(content.splitlines(), start=1):
            if "<text>" in line:
                text_start_line = idx
                break

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise DRCParserError(f"Failed to parse XML macro {deck_path}: {exc}") from exc

        text_elem = root.find("text")
        if text_elem is None or text_elem.text is None:
            raise DRCParserError(f"DRC XML macro {deck_path} does not contain a <text> element.")

        # Decode XML/HTML entities (&lt;, &gt;, &amp;, &quot;)
        raw_text = html.unescape(text_elem.text)
        lines = tuple(raw_text.splitlines())

        return ExtractedDeck(
            deck_path=deck_path,
            script_text=raw_text,
            script_lines=lines,
            is_xml_macro=True,
            text_start_line=text_start_line,
        )
