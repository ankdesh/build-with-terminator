#!/usr/bin/env python3
import argparse
import logging
import sys
from datetime import datetime
from src.capture.capturer import ScreenAudioCapturer

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
        description="Capture screenshots of Google Chrome and system audio in segments."
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=10,
        help="Time interval between snapshots in seconds (default: 10)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=None,
        help="Total duration to capture in seconds (optional, captures indefinitely if omitted)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to save the captures (default: captures/session_<timestamp>)"
    )
    parser.add_argument(
        "--audio-source", "-a",
        type=str,
        default=None,
        help="Audio source name (e.g. default, or a specific .monitor source. Auto-detected if not specified)"
    )
    
    args = parser.parse_args()
    
    # Generate default output directory if not provided
    if not args.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = f"captures/session_{timestamp}"
        
    capturer = ScreenAudioCapturer(
        interval=args.interval,
        duration=args.duration,
        output_dir=args.output_dir,
        audio_source=args.audio_source
    )
    
    try:
        capturer.run()
    except Exception as e:
        logging.error(f"Fatal error during capture: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
