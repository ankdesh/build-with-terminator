"""
cli.py — Validator CLI entrypoint
===================================
Provides the `ipxact-validate` command-line tool.

This tool is designed to be called by:
  • The Gemini Generator Skill (via run_command) after writing XML files.
  • The converter pipeline to validate the output.
  • Engineers manually verifying any IP-XACT 2022 XML file.

Exit codes:
  0 — File is valid.
  1 — File is invalid or an error occurred.

Usage:
    uv run ipxact-validate <file.xml>
    uv run ipxact-validate <file.xml> --schema-cache-dir /path/to/cache
"""

import argparse
import sys
from pathlib import Path

from src.tools.validator.validator import IPXACTValidator


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for ipxact-validate."""
    parser = argparse.ArgumentParser(
        prog="ipxact-validate",
        description=(
            "Validate an IP-XACT XML file against the official IEEE 1685-2022 XSD schema.\n\n"
            "The XSD is fetched from Accellera on first run and cached locally.\n"
            "Exit code 0 = valid. Exit code 1 = invalid or error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        metavar="FILE",
        help="Path to the IP-XACT XML file to validate.",
    )
    parser.add_argument(
        "--schema-cache-dir",
        metavar="DIR",
        default=None,
        help=(
            "Override the directory used to cache the downloaded XSD schema. "
            "Defaults to src/tools/validator/schemas/ inside the project."
        ),
    )
    return parser


def main() -> None:
    """Entrypoint for the `ipxact-validate` CLI command."""
    parser = build_parser()
    args = parser.parse_args()

    cache_dir = Path(args.schema_cache_dir) if args.schema_cache_dir else None
    validator = IPXACTValidator(schema_cache_dir=cache_dir)

    try:
        is_valid = validator.validate(xml_path=Path(args.file))
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    # Exit with the appropriate code so run_command / shell scripts can check result.
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
