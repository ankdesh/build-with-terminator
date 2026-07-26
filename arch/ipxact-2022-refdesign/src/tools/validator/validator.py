"""
validator.py
============
IP-XACT 2022 XML schema validator.

On first invocation this module downloads the official Accellera 2022 XSD index
file and caches it locally in `schemas/`. Subsequent runs are fully offline.

The validator uses lxml's XMLSchema engine for fast, standards-compliant
validation and emits structured error messages to stderr including line numbers
and element paths, making it easy to locate problems.

Exit behavior (for shell / run_command integration):
  - Exit 0 → XML is valid against the 2022 schema.
  - Exit 1 → XML is invalid or schema could not be loaded.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    import requests
    from lxml import etree
except ImportError as exc:
    print(f"CRITICAL ERROR: Missing dependency — {exc}. Run: uv sync", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directory containing this file (src/tools/validator/)
_MODULE_DIR = Path(__file__).parent

# Local cache directory for downloaded XSD files.
SCHEMA_CACHE_DIR: Path = _MODULE_DIR / "schemas"

# The Accellera 2022 XSD index — this is the root schema that imports all others.
# NOTE: Accellera publishes this as part of the standard distribution.
XSD_INDEX_URL: str = (
    "https://www.accellera.org/XMLSchema/IPXACT/1685-2022/index.xsd"
)

# Local path where the root XSD will be cached.
XSD_CACHED_PATH: Path = SCHEMA_CACHE_DIR / "index.xsd"


class IPXACTValidator:
    """
    Validates IP-XACT XML files against the official IEEE 1685-2022 XSD schema.

    The schema is fetched from Accellera on first run and cached locally for
    offline use thereafter.

    Usage:
        validator = IPXACTValidator()
        is_valid = validator.validate(Path("output.xml"))
    """

    def __init__(self, schema_cache_dir: Optional[Path] = None) -> None:
        """
        Args:
            schema_cache_dir: Override for the XSD cache directory.
                              Defaults to src/tools/validator/schemas/.
        """
        self._cache_dir: Path = schema_cache_dir or SCHEMA_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cached_xsd_path: Path = self._cache_dir / "index.xsd"
        self._schema: Optional[etree.XMLSchema] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, xml_path: Path) -> bool:
        """
        Validate the given XML file against the 2022 XSD.

        Validation errors are printed to stderr with line numbers.

        Args:
            xml_path: Path to the IP-XACT XML file to validate.

        Returns:
            True if valid, False otherwise.

        Raises:
            FileNotFoundError: If xml_path does not exist.
        """
        if not xml_path.is_file():
            raise FileNotFoundError(f"File to validate not found: {xml_path}")

        schema = self._load_schema()
        if schema is None:
            # Schema load failed — already logged to stderr.
            return False

        try:
            doc = etree.parse(str(xml_path))
        except etree.XMLSyntaxError as exc:
            print(f"[ERROR] XML parse error in '{xml_path}': {exc}", file=sys.stderr)
            return False

        is_valid: bool = schema.validate(doc)

        if is_valid:
            print(f"[OK] '{xml_path}' is valid against the IP-XACT 2022 schema.", file=sys.stderr)
        else:
            print(
                f"[FAIL] '{xml_path}' failed schema validation. Errors:",
                file=sys.stderr,
            )
            for error in schema.error_log:
                print(
                    f"  Line {error.line}: [{error.type_name}] {error.message}",
                    file=sys.stderr,
                )

        return is_valid

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_schema(self) -> Optional[etree.XMLSchema]:
        """
        Load the XSD schema from the local cache, downloading it first if needed.

        Returns:
            An lxml.etree.XMLSchema object, or None if loading failed.
        """
        if self._schema is not None:
            # Already loaded in this session — reuse.
            return self._schema

        if not self._cached_xsd_path.is_file():
            self._download_schema()

        if not self._cached_xsd_path.is_file():
            print(
                "[ERROR] XSD schema not available. Cannot validate.",
                file=sys.stderr,
            )
            return None

        try:
            schema_doc = etree.parse(str(self._cached_xsd_path))
            self._schema = etree.XMLSchema(schema_doc)
            print(
                f"[*] Loaded XSD schema from cache: '{self._cached_xsd_path}'",
                file=sys.stderr,
            )
        except etree.XMLSchemaParseError as exc:
            print(f"[ERROR] Failed to parse XSD schema: {exc}", file=sys.stderr)
            return None

        return self._schema

    def _download_schema(self) -> None:
        """
        Fetch the Accellera 2022 XSD from the official URL and cache it locally.
        Emits a warning if the download fails (network unavailable, etc.).
        """
        print(
            f"[*] XSD schema not cached. Downloading from:\n    {XSD_INDEX_URL}",
            file=sys.stderr,
        )
        try:
            response = requests.get(XSD_INDEX_URL, timeout=30)
            response.raise_for_status()
            self._cached_xsd_path.write_bytes(response.content)
            print(
                f"[*] XSD cached to: '{self._cached_xsd_path}'",
                file=sys.stderr,
            )
        except requests.RequestException as exc:
            print(
                f"[WARNING] Could not download XSD schema: {exc}\n"
                "          Validation will be skipped. Supply XSD manually at:\n"
                f"          {self._cached_xsd_path}",
                file=sys.stderr,
            )
