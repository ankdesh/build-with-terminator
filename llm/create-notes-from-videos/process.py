#!/usr/bin/env python3
import argparse
import logging
import sys
import os
import json
from datetime import datetime
from src.process.processor import SessionProcessor

def setup_logging() -> None:
    """Sets up logging to stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def load_config() -> dict:
    """Loads configuration from config.json if it exists."""
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse config.json: {e}", file=sys.stderr)
    return {}

def main() -> None:
    setup_logging()
    config = load_config()
    
    # Extract config defaults
    llm_config = config.get("llm", {})
    whisper_config = config.get("whisper", {})
    capture_config = config.get("capture", {})
    pdf_config = config.get("pdf", {})
    
    parser = argparse.ArgumentParser(
        description="Process captured video tutorial sessions by transcribing audio and merging similar slides."
    )
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        required=True,
        help="Directory containing the captured screenshots and audio files"
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
        default=capture_config.get("threshold", 0.95),
        help=f"SSIM similarity threshold (default from config: {capture_config.get('threshold', 0.95)}). Value between 0.0 and 1.0."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=whisper_config.get("model_size", "base"),
        help=f"Whisper model size to use (default from config: {whisper_config.get('model_size', 'base')})"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=llm_config.get("model", "gpt-4o-mini"),
        help=f"OpenAI LLM model name (default from config: {llm_config.get('model', 'gpt-4o-mini')})"
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=llm_config.get("temperature", 0.2),
        help=f"OpenAI LLM temperature (default from config: {llm_config.get('temperature', 0.2)})"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip OpenAI note generation and only use raw transcripts in the PDF"
    )
    parser.add_argument(
        "--pdf-image-quality",
        type=int,
        default=pdf_config.get("image_quality", 80),
        help=f"JPEG quality for images embedded in the PDF (1-100, default from config: {pdf_config.get('image_quality', 80)})"
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
        model_size=args.model,
        llm_model=args.llm_model,
        llm_temperature=args.llm_temperature,
        skip_llm=args.skip_llm,
        pdf_image_quality=args.pdf_image_quality
    )
    
    try:
        processor.process()
    except Exception as e:
        logging.error(f"Fatal error during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
