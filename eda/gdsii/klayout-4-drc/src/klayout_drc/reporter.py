"""Formats DRC violation data into human-readable text reports and summary structures.

Provides the reporter responsible for generating textual violation details,
bounding box / polygon coordinates, and category totals.
"""

from pathlib import Path
from typing import Optional

from .parser import DRCReportData


class DRCReporter:
    """Generates textual reports and summary representations from DRCReportData."""

    def __init__(self, data: DRCReportData) -> None:
        """Initialize with parsed DRC report data.
        
        Args:
            data: Structured DRC report data.
        """
        self.data = data

    def generate_textual_report(self) -> str:
        """Format a detailed human-readable report.
        
        Returns:
            str: Multi-line textual summary with coordinates and rule descriptions.
        """
        lines: list[str] = [
            "=== DRC Violations Details ===",
            f"Source: {self.data.source_path}",
        ]

        if not self.data.categories:
            lines.append("\nNo DRC violations found.")
            lines.append("\n==============================")
            lines.append("Total Violations: 0\n")
            return "\n".join(lines)

        for category in self.data.categories:
            lines.append(f"\nRule: {category.name} - {category.description}")
            lines.append(f"  -> {category.count} violation(s) found:")
            for item in category.violations:
                cell_info = f" (Cell: {item.cell_name})" if item.cell_name else ""
                lines.append(f"    Violation {item.item_id}{cell_info}:")
                for geo in item.geometries:
                    label = geo.kind.replace("_", " ").capitalize()
                    lines.append(f"      {label}: {geo.representation}")

        lines.append("\n==============================")
        lines.append(f"Total Violations: {self.data.total_violations}\n")
        return "\n".join(lines)

    def write_textual_report(self, target_path: Path) -> Path:
        """Write the textual report to a file on disk.
        
        Args:
            target_path: Destination path for the report file.
            
        Returns:
            Path: The resolved path to the written file.
        """
        resolved_path = target_path.resolve()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        report_text = self.generate_textual_report()
        resolved_path.write_text(report_text, encoding="utf-8")
        return resolved_path

    def get_summary(self) -> dict[str, int]:
        """Return a mapping of rule names to violation counts."""
        return {cat.name: cat.count for cat in self.data.categories}
