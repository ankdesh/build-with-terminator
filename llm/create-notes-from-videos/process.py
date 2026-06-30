#!/usr/bin/env python3
import argparse
import logging
import sys
from datetime import datetime
from src.process.processor import SessionProcessor

def setup_logging() -> None:
    """Sets up logging to stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def main() -> None:
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Process captured video tutorial sessions by transcribing audio and merging similar slides."
    )
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        required=True,
        help="Directory containing the raw captured screenshots and audio files"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to save the processed slides and transcripts (default: processed/session_<timestamp>)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.95,
        help="SSIM similarity threshold (default: 0.95). Value between 0.0 and 1.0."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="base",
        help="Whisper model size to use (default: base. Options: tiny, base, small, medium, large-v3)"
    )
    
    args = parser.parse_args()
    
    # Generate default output directory if not provided
    if not args.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = f"processed/session_{timestamp}"
        
    processor = SessionProcessor(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        threshold=args.threshold,
        model_size=args.model
    )
    
    try:
        processor.process()
    except Exception as e:
        logging.error(f"Fatal error during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
