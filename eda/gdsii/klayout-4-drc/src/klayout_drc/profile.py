"""DRC Profile definition and manager for technology-specific rule decks.

Provides typed models for selecting deck parameter variable names, PDK layer mappings,
and database unit (DBU) conventions.
"""

from dataclasses import dataclass, field
from pathlib import Path
import yaml

from .config import (
    DEFAULT_RULES_DIR,
    DRCConfigurationError,
)


@dataclass(frozen=True)
class DRCProfile:
    """Configuration profile for a specific DRC deck and PDK technology ruleset."""

    name: str
    description: str
    deck_path: Path
    param_in_gds: str = "input"
    param_report: str = "report"
    extra_params: dict[str, str] = field(default_factory=dict)
    layers: dict[str, tuple[int, int]] = field(default_factory=dict)
    dbu_um: float = 0.001

    def validate(self) -> None:
        """Validate profile parameters and ensure deck file exists."""
        if not self.deck_path.exists():
            raise DRCConfigurationError(f"DRC profile deck file does not exist: {self.deck_path}")


class DRCProfileManager:
    """Registry and loader for technology-specific DRC execution profiles."""

    def __init__(self) -> None:
        """Initialize registry with built-in profiles."""
        self._profiles: dict[str, DRCProfile] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register default built-in profiles for legacy mini and ASAP7."""
        legacy_mini = DRCProfile(
            name="legacy_mini",
            description="Synthetic ASAP7 3-rule mini DRC deck with legacy layer conventions",
            deck_path=DEFAULT_RULES_DIR / "asap7_mini.drc",
            param_in_gds="input",
            param_report="report",
            layers={"M1": (18, 0), "V1": (19, 0)},
            dbu_um=0.001,
        )
        self.register_profile(legacy_mini)

        asap7_public = DRCProfile(
            name="asap7_public_full",
            description="Public ASAP7 KLayout DRC deck with authentic PDK layer conventions",
            deck_path=DEFAULT_RULES_DIR / "drc_ASAP7.lydrc",
            param_in_gds="in_gds",
            param_report="report_file",
            layers={"V0": (18, 0), "M1": (19, 0), "M2": (20, 0), "V1": (21, 0)},
            dbu_um=0.00025,
        )
        self.register_profile(asap7_public)

    def register_profile(self, profile: DRCProfile) -> None:
        """Register a new DRC profile in the registry."""
        self._profiles[profile.name] = profile

    def get_profile(self, name: str) -> DRCProfile:
        """Retrieve a registered profile by name.

        Args:
            name: Name identifier of the profile.

        Raises:
            DRCConfigurationError: If profile name is not found.
        """
        if name not in self._profiles:
            available = ", ".join(self._profiles.keys())
            raise DRCConfigurationError(
                f"DRC profile '{name}' not found. Available profiles: {available}"
            )
        return self._profiles[name]

    def list_profiles(self) -> list[str]:
        """Return names of all registered profiles."""
        return list(self._profiles.keys())

    def load_from_yaml(self, yaml_path: Path) -> DRCProfile:
        """Load and register a DRC profile from a YAML file.

        Args:
            yaml_path: Path to the YAML profile specification.

        Raises:
            DRCConfigurationError: If file cannot be read or lacks required fields.
        """
        yaml_path = Path(yaml_path).resolve()
        if not yaml_path.exists():
            raise DRCConfigurationError(f"Profile YAML file does not exist: {yaml_path}")

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            raise DRCConfigurationError(f"Failed to parse profile YAML: {exc}") from exc

        required = ["name", "deck_path"]
        for key in required:
            if key not in data:
                raise DRCConfigurationError(f"Missing required profile field: {key}")

        deck_path = Path(data["deck_path"])
        if not deck_path.is_absolute():
            deck_path = (yaml_path.parent / deck_path).resolve()

        layers_raw = data.get("layers", {})
        layers = {k: tuple(v) for k, v in layers_raw.items()}

        profile = DRCProfile(
            name=data["name"],
            description=data.get("description", ""),
            deck_path=deck_path,
            param_in_gds=data.get("param_in_gds", "input"),
            param_report=data.get("param_report", "report"),
            extra_params=data.get("extra_params", {}),
            layers=layers,
            dbu_um=float(data.get("dbu_um", 0.001)),
        )
        self.register_profile(profile)
        return profile
