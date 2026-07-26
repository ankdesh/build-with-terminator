"""
cli.py — Converter CLI entrypoint
==================================
Provides the `ipxact-convert` command-line tool.

Usage:
    uv run ipxact-convert --input <input_2014.xml> --output <output_2022.xml>
    uv run ipxact-convert --input old.xml --output new.xml --vendor my_org
"""

import argparse
import sys
from pathlib import Path

from src.tools.converter.converter import IPXACTConverter


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for ipxact-convert."""
    parser = argparse.ArgumentParser(
        prog="ipxact-convert",
        description=(
            "Convert an IP-XACT IEEE 1685-2014 XML file to IEEE 1685-2022.\n\n"
            "Operations performed:\n"
            "  • Migrate namespaces from 2014 → 2022\n"
            "  • Normalize <ipxact:vendor> to the target vendor\n"
            "  • Translate deprecated <isPresent> → Accellera Vendor Extensions\n"
            "  • Flag Category 3 (excluded) elements as stderr WARNINGs\n"
            "  • Flag Category 2 (optional) elements as stderr INFOs"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        metavar="FILE",
        help="Path to the source IP-XACT 2014 XML file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        metavar="FILE",
        help="Destination path for the generated IP-XACT 2022 XML file.",
    )
    parser.add_argument(
        "--vendor",
        "-v",
        default="saiti",
        metavar="NAME",
        help=(
            "Vendor identifier to enforce in all <ipxact:vendor> elements. "
            "Defaults to 'saiti' per organizational convention."
        ),
    )
    return parser


def main() -> None:
    """Entrypoint for the `ipxact-convert` CLI command."""
    parser = build_parser()
    args = parser.parse_args()

    converter = IPXACTConverter(target_vendor=args.vendor)

    try:
        converter.convert(
            input_path=Path(args.input),
            output_path=Path(args.output),
        )
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
