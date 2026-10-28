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

    def __init__(
        self,
        patched_gds: Path,
        reference_gds: Path | None = None,
        allowed_layers: set[tuple[int, int]] | None = None,
        protected_cells: set[str] | None = None,
        preservation: dict | None = None,
        top_cell: str | None = None,
    ) -> None:
        """Initialize validator with target patched GDS and optional reference GDS.

        Args:
            patched_gds: Path to the layout to validate.
            reference_gds: Path to baseline layout before patch.
            allowed_layers: Optional set of allowed (layer, datatype) tuples that may be edited.
            protected_cells: Optional set of cell names that must remain immutable.
        """
        self.patched_gds = Path(patched_gds).resolve()
        self.reference_gds = Path(reference_gds).resolve() if reference_gds else None
        self.allowed_layers = allowed_layers
        self.protected_cells = protected_cells
        self.preservation = preservation or {}
        self.top_cell = top_cell

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
        top_cells = list(layout.top_cells())
        top_cell = layout.cell(self.top_cell) if self.top_cell else (top_cells[0] if len(top_cells) == 1 else None)
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
                total_shapes += sum(1 for _ in _recursive_shapes(top_cell, layer_idx))

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
                ref_top = ref_layout.cell(self.top_cell) if self.top_cell else ref_layout.top_cell()
                if ref_top and top_cell_name != "none" and ref_top.name != top_cell_name:
                    violations.append(
                        f"Top-cell name mismatch: expected '{ref_top.name}', got '{top_cell_name}'."
                    )
                if abs(ref_layout.dbu - dbu) > 1e-9:
                    violations.append(
                        f"DBU mismatch: original layout DBU is {ref_layout.dbu}, patched is {dbu}."
                    )

                # Check protected cells
                protected = self.protected_cells if self.protected_cells is not None else {c.name for c in ref_layout.each_cell() if c != ref_top}
                if protected:
                    for pcell_name in protected:
                        ref_c = ref_layout.cell(pcell_name)
                        patch_c = layout.cell(pcell_name)
                        if ref_c is not None:
                            if patch_c is None:
                                violations.append(f"Protected master cell '{pcell_name}' was removed in patched layout.")
                            elif _cell_content(ref_layout, ref_c) != _cell_content(layout, patch_c):
                                violations.append(f"Protected master cell '{pcell_name}' contents changed.")
                # Protect placements of protected masters, including top-level instances.
                for parent in ref_layout.each_cell():
                    patch_parent = layout.cell(parent.name)
                    before_instances = _protected_instances(ref_layout, parent, protected)
                    after_instances = _protected_instances(layout, patch_parent, protected) if patch_parent else ()
                    if before_instances != after_instances:
                        violations.append(f"Protected instance definitions changed in '{parent.name}'")
            except Exception as exc:
                violations.append(f"Could not load reference GDS for comparison: {exc}")

        if top_cell is not None:
            for layer_key, expected in self.preservation.get("component_counts", {}).items():
                layer, datatype = map(int, layer_key.split("/"))
                idx = layout.find_layer(layer, datatype)
                observed = db.Region(top_cell.begin_shapes_rec(idx)).merged().count() if idx is not None else 0
                if observed != expected:
                    violations.append(f"Component preservation failed on {layer_key}: expected {expected}, observed {observed}")
            if self.reference_gds and self.preservation.get("protected_regions"):
                for region in self.preservation["protected_regions"]:
                    layer, datatype = region["layer"]
                    window = db.Region(db.Box(*region["box_dbu"]))
                    a = ref_layout.find_layer(layer, datatype)
                    b = layout.find_layer(layer, datatype)
                    before = db.Region(ref_top.begin_shapes_rec(a)) if a is not None else db.Region()
                    after = db.Region(top_cell.begin_shapes_rec(b)) if b is not None else db.Region()
                    if not ((before ^ after) & window).is_empty():
                        violations.append(f"Protected region changed on {layer}/{datatype}")
        is_valid = len(violations) == 0
        return ValidationResult(
            is_valid=is_valid,
            top_cell_name=top_cell_name,
            dbu_um=dbu,
            total_shapes=total_shapes,
            bbox_um=bbox_um,
            violations=violations,
        )


def _recursive_shapes(cell, layer):
    iterator = cell.begin_shapes_rec(layer)
    while not iterator.at_end():
        yield iterator.shape()
        iterator.next()


def _cell_content(layout, cell):
    shapes = tuple(sorted((str(layout.get_info(idx)), tuple(sorted(s.to_s() for s in cell.shapes(idx).each())))
                          for idx in layout.layer_indexes() if not cell.shapes(idx).is_empty()))
    instances = tuple(sorted((layout.cell(i.cell_index).name, str(i.cplx_trans), str(i.a), str(i.b), i.na, i.nb) for i in cell.each_inst()))
    return shapes, instances


def _protected_instances(layout, cell, protected):
    return tuple(sorted((layout.cell(i.cell_index).name, str(i.cplx_trans), str(i.a), str(i.b), i.na, i.nb)
                        for i in cell.each_inst() if layout.cell(i.cell_index).name in protected))
