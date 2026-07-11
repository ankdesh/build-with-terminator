import argparse
import sys
import logging

from systemc_gen.parser import IPXACTParser
from systemc_gen.generator import SystemCGenerator

def setup_logging():
    """Sets up default logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

def main():
    setup_logging()
    parser = argparse.ArgumentParser(
        description="SystemC/TLM-2.0 Scaffold Generator from IP-XACT XML specifications."
    )
    parser.add_argument(
        "--ipxact",
        required=True,
        help="Path to the input IP-XACT XML file."
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Target output directory for the generated SystemC files."
    )

    args = parser.parse_args()

    try:
        logging.info(f"Parsing IP-XACT file: {args.ipxact}")
        ipxact_parser = IPXACTParser(args.ipxact)
        component = ipxact_parser.parse()

        logging.info(f"Generating SystemC scaffolding for component '{component.name}' into: {args.out}")
        generator = SystemCGenerator(args.out)
        output_path = generator.generate(component)

        logging.info(f"Scaffolding successfully generated at: {output_path}")
        print(f"Success: Scaffolding generated at {output_path}")
    except Exception as e:
        logging.error(f"Error during execution: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
