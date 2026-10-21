"""Layout integrity validator for candidate layouts.

Verifies that patched GDS files conform to basic physical invariants:
valid top cell, preserved DBU, non-empty shapes, and reasonable bounding box bounds.
"""

from dataclasses import dataclass, field
from pathlib import Path
import klayout.db as db

from .config import DRCError


class LayoutValidationError(DRCError):
    """Raised when a candidate layout fails structural integrity checks."""
    pass


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of layout integrity validation."""

    is_valid: bool
    top_cell_name: str
    dbu_um: float
    total_shapes: int
    bbox_um: tuple[float, float, float, float]
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert validation result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "top_cell_name": self.top_cell_name,
            "dbu_um": self.dbu_um,
            "total_shapes": self.total_shapes,
            "bbox_um": list(self.bbox_um),
            "violations": self.violations,
        }


class LayoutValidator:
    """Validates structural layout integrity and checks for destructive edits."""

    def __init__(self, patched_gds: Path, reference_gds: Path | None = None) -> None:
        """Initialize validator with target patched GDS and optional reference GDS.

        Args:
            patched_gds: Path to the layout to validate.
            reference_gds: Path to baseline layout before patch.
        """
        self.patched_gds = Path(patched_gds).resolve()
        self.reference_gds = Path(reference_gds).resolve() if reference_gds else None

    def validate(self) -> ValidationResult:
        """Perform comprehensive layout integrity checks.

        Returns:
            ValidationResult: Detailed validation outcome.
        """
        violations: list[str] = []

        if not self.patched_gds.exists() or self.patched_gds.stat().st_size == 0:
            return ValidationResult(
                is_valid=False,
                top_cell_name="unknown",
                dbu_um=0.0,
                total_shapes=0,
                bbox_um=(0.0, 0.0, 0.0, 0.0),
                violations=["Patched GDS file does not exist or is empty (0 bytes)."],
            )

        layout = db.Layout()
        try:
            layout.read(str(self.patched_gds))
        except Exception as exc:
            return ValidationResult(
                is_valid=False,
                top_cell_name="corrupt",
                dbu_um=0.0,
                total_shapes=0,
                bbox_um=(0.0, 0.0, 0.0, 0.0),
                violations=[f"KLayout failed to parse GDS layout: {exc}"],
            )

        # 1. Check top cell
        top_cell = layout.top_cell()
        if top_cell is None:
            violations.append("Layout has no top cell defined.")
            top_cell_name = "none"
        else:
            top_cell_name = top_cell.name

        # 2. Check total shapes in top cell (prevent 'delete-all' cheating)
        total_shapes = 0
        if top_cell is not None:
            for layer_idx in layout.layer_indexes():
                shapes = top_cell.shapes(layer_idx)
                total_shapes += shapes.size()

        if total_shapes == 0:
            violations.append("Layout contains 0 shapes in top cell (all geometry was deleted).")

        # 3. Check DBU
        dbu = layout.dbu
        if dbu <= 0:
            violations.append(f"Invalid database unit (DBU <= 0): {dbu}")

        # 4. Check bounding box sanity
        bbox = top_cell.bbox() if top_cell else db.Box()
        if bbox.empty():
            violations.append("Top-cell bounding box is empty.")
            bbox_um = (0.0, 0.0, 0.0, 0.0)
        else:
            bbox_um = (
                bbox.left * dbu,
                bbox.bottom * dbu,
                bbox.right * dbu,
                bbox.top * dbu,
            )

        # 5. Check against reference layout if provided
        if self.reference_gds and self.reference_gds.exists():
            ref_layout = db.Layout()
            try:
                ref_layout.read(str(self.reference_gds))
                ref_top = ref_layout.top_cell()
                if ref_top and top_cell_name != "none" and ref_top.name != top_cell_name:
                    violations.append(
                        f"Top-cell name mismatch: expected '{ref_top.name}', got '{top_cell_name}'."
                    )
                if abs(ref_layout.dbu - dbu) > 1e-9:
                    violations.append(
                        f"DBU mismatch: original layout DBU is {ref_layout.dbu}, patched is {dbu}."
                    )
            except Exception as exc:
                violations.append(f"Could not load reference GDS for comparison: {exc}")

        is_valid = len(violations) == 0
        return ValidationResult(
            is_valid=is_valid,
            top_cell_name=top_cell_name,
            dbu_um=dbu,
            total_shapes=total_shapes,
            bbox_um=bbox_um,
            violations=violations,
        )
