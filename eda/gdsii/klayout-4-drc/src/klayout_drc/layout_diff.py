"""Geometric layout difference calculator.

Computes layer-by-layer geometric diffs (added area, removed area, unchanged area)
between an immutable reference GDS and a patched candidate GDS.
"""

from dataclasses import dataclass, field
from pathlib import Path
import klayout.db as db


@dataclass(frozen=True)
class LayerDiff:
    """Geometric diff summary for a single GDS layer/datatype."""

    layer: int
    datatype: int
    added_area_um2: float
    removed_area_um2: float
    unchanged_area_um2: float

    @property
    def has_changes(self) -> bool:
        """True if any area was added or removed on this layer."""
        return self.added_area_um2 > 1e-12 or self.removed_area_um2 > 1e-12

    def to_dict(self) -> dict:
        """Convert layer diff to dictionary."""
        return {
            "layer": self.layer,
            "datatype": self.datatype,
            "added_area_um2": round(self.added_area_um2, 6),
            "removed_area_um2": round(self.removed_area_um2, 6),
            "unchanged_area_um2": round(self.unchanged_area_um2, 6),
            "has_changes": self.has_changes,
        }


@dataclass(frozen=True)
class LayoutDiffReport:
    """Aggregate layout difference metrics across all layers."""

    total_added_area_um2: float
    total_removed_area_um2: float
    net_area_delta_um2: float
    modified_layers: list[tuple[int, int]]
    layer_diffs: list[LayerDiff] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert diff report to dictionary."""
        return {
            "total_added_area_um2": round(self.total_added_area_um2, 6),
            "total_removed_area_um2": round(self.total_removed_area_um2, 6),
            "net_area_delta_um2": round(self.net_area_delta_um2, 6),
            "modified_layers": [list(ly) for ly in self.modified_layers],
            "layer_diffs": [ld.to_dict() for ld in self.layer_diffs],
        }


class LayoutDiffCalculator:
    """Computes exact geometric polygon differences between reference and patched layouts."""

    def __init__(self, reference_gds: Path, patched_gds: Path) -> None:
        """Initialize with reference and patched GDS paths.

        Args:
            reference_gds: Original baseline layout.
            patched_gds: Patched layout.
        """
        self.reference_gds = Path(reference_gds).resolve()
        self.patched_gds = Path(patched_gds).resolve()

    def compute_diff(self) -> LayoutDiffReport:
        """Compute layer-by-layer polygon diffs and return LayoutDiffReport."""
        ref_layout = db.Layout()
        ref_layout.read(str(self.reference_gds))
        ref_top = ref_layout.top_cell()
        ref_dbu = ref_layout.dbu

        patch_layout = db.Layout()
        patch_layout.read(str(self.patched_gds))
        patch_top = patch_layout.top_cell()
        patch_dbu = patch_layout.dbu

        # Collect union of all layer/datatype pairs
        all_layer_infos: set[tuple[int, int]] = set()
        for idx in ref_layout.layer_indexes():
            info = ref_layout.get_info(idx)
            all_layer_infos.add((info.layer, info.datatype))
        for idx in patch_layout.layer_indexes():
            info = patch_layout.get_info(idx)
            all_layer_infos.add((info.layer, info.datatype))

        layer_diffs: list[LayerDiff] = []
        total_added = 0.0
        total_removed = 0.0
        modified_layers: list[tuple[int, int]] = []

        for layer_num, datatype in sorted(all_layer_infos):
            ref_region = db.Region()
            if ref_top:
                ref_idx = ref_layout.find_layer(layer_num, datatype)
                if ref_idx is not None:
                    ref_region = db.Region(ref_top.shapes(ref_idx))

            patch_region = db.Region()
            if patch_top:
                patch_idx = patch_layout.find_layer(layer_num, datatype)
                if patch_idx is not None:
                    patch_region = db.Region(patch_top.shapes(patch_idx))

            # Rescale regions if DBUs differ
            if abs(ref_dbu - patch_dbu) > 1e-9:
                ref_region = ref_region.transformed(db.ICplxTrans(ref_dbu / patch_dbu))
                scale_to_um2 = patch_dbu * patch_dbu
            else:
                scale_to_um2 = patch_dbu * patch_dbu

            added_region = patch_region - ref_region
            removed_region = ref_region - patch_region
            unchanged_region = ref_region & patch_region

            added_area_um2 = added_region.area() * scale_to_um2
            removed_area_um2 = removed_region.area() * scale_to_um2
            unchanged_area_um2 = unchanged_region.area() * scale_to_um2

            diff = LayerDiff(
                layer=layer_num,
                datatype=datatype,
                added_area_um2=added_area_um2,
                removed_area_um2=removed_area_um2,
                unchanged_area_um2=unchanged_area_um2,
            )
            layer_diffs.append(diff)
            total_added += added_area_um2
            total_removed += removed_area_um2
            if diff.has_changes:
                modified_layers.append((layer_num, datatype))

        return LayoutDiffReport(
            total_added_area_um2=total_added,
            total_removed_area_um2=total_removed,
            net_area_delta_um2=total_added - total_removed,
            modified_layers=modified_layers,
            layer_diffs=layer_diffs,
        )
