import os
import subprocess
import time
import logging
import re
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Constants
DEFAULT_INTERVAL = 10
DEFAULT_DISPLAY = os.environ.get("DISPLAY", ":0.0")

class ScreenAudioCapturer:
    """Handles capturing screenshots of the full screen and system audio in segments."""

    def __init__(
        self,
        interval: int = DEFAULT_INTERVAL,
        duration: Optional[int] = None,
        output_dir: str = "captures",
        audio_source: Optional[str] = None
    ) -> None:
        self.interval = interval
        self.duration = duration
        self.output_dir = output_dir
        self.monitor_source = audio_source
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_monitor_source(self) -> str:
        """Finds the PulseAudio/PipeWire monitor source for system audio loopback."""
        if self.monitor_source:
            logger.info(f"Using user-specified audio source: {self.monitor_source}")
            return self.monitor_source

        try:
            # 1. Get the default sink
            sink_result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                check=True
            )
            default_sink = sink_result.stdout.strip()
            logger.info(f"Default audio sink: {default_sink}")

            # 2. Find the monitor source corresponding to this sink
            sources_result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Look for <default_sink>.monitor in the sources list
            for line in sources_result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    source_name = parts[1]
                    if default_sink in source_name and "monitor" in source_name:
                        logger.info(f"Found monitor source: {source_name}")
                        return source_name

            # Fallback to appending .monitor to the default sink
            fallback_source = f"{default_sink}.monitor"
            logger.warning(f"Monitor source not found in list, falling back to: {fallback_source}")
            return fallback_source
        except FileNotFoundError as e:
            logger.error("pactl command not found. Cannot auto-detect audio source.")
            raise RuntimeError(
                "pactl is not installed on this system. Please install it (typically via pulseaudio-utils "
                "or pipewire-utils), or specify the audio source manually using --audio-source / -a."
            ) from e
        except Exception as e:
            logger.error(f"Failed to detect PulseAudio/PipeWire monitor source: {e}")
            raise RuntimeError("Could not find system audio monitor source. Is PulseAudio/PipeWire running?") from e

    def _get_screen_resolution(self) -> str:
        """Attempts to detect the screen resolution using xrandr."""
        try:
            result = subprocess.run(["xrandr"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if "*" in line:
                    # Line looks like: "   1920x1080     60.00*+  59.94..."
                    parts = line.strip().split()
                    if parts:
                        res = parts[0]
                        if "x" in res:
                            logger.info(f"Detected screen resolution: {res}")
                            return res
        except Exception as e:
            logger.warning(f"Could not detect screen resolution via xrandr: {e}")
        
        # Fallback default
        logger.info("Using fallback screen resolution: 1920x1080")
        return "1920x1080"

    def capture_screenshot(self, image_path: str) -> None:
        """Takes a screenshot of the full screen using ffmpeg."""
        res = self._get_screen_resolution()
        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-video_size", res,
            "-i", DEFAULT_DISPLAY,
            "-vframes", "1",
            image_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.debug(f"Saved screenshot: {image_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to capture screenshot. Exit code: {e.returncode}")
            logger.error(f"ffmpeg stdout: {e.stdout}")
            logger.error(f"ffmpeg stderr: {e.stderr}")

    def run(self) -> None:
        """Runs the capture loop."""
        self.monitor_source = self._get_monitor_source()
        
        logger.info(f"Starting capture session in: {self.output_dir}")
        logger.info(f"Interval: {self.interval}s, Max Duration: {self.duration}s")
        
        start_time = time.time()
        index = 0
        
        # Take the initial screenshot at t=0
        initial_img = os.path.join(self.output_dir, f"screenshot_{index:04d}.png")
        self.capture_screenshot(initial_img)
        
        active_audio_process: Optional[subprocess.Popen] = None
        
        try:
            while True:
                elapsed = time.time() - start_time
                if self.duration and elapsed >= self.duration:
                    logger.info("Target duration reached. Stopping capture.")
                    break

                # Determine recording duration for this segment
                segment_duration = self.interval
                if self.duration:
                    remaining = self.duration - elapsed
                    if remaining < self.interval:
                        segment_duration = int(remaining)
                        if segment_duration <= 0:
                            break

                audio_path = os.path.join(self.output_dir, f"audio_{index:04d}.wav")
                
                # Start recording audio in background
                audio_cmd = [
                    "ffmpeg", "-y",
                    "-f", "pulse",
                    "-i", self.monitor_source,
                    "-t", str(segment_duration),
                    audio_path
                ]
                logger.debug(f"Starting audio recording segment {index} ({segment_duration}s)")
                active_audio_process = subprocess.Popen(audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Wait for the audio segment to finish
                active_audio_process.wait()
                active_audio_process = None
                
                # Move to next index for the upcoming screenshot and segment
                index += 1
                
                # Take screenshot corresponding to the end of this audio segment
                next_img = os.path.join(self.output_dir, f"screenshot_{index:04d}.png")
                self.capture_screenshot(next_img)
                
        except KeyboardInterrupt:
            logger.info("Capture session interrupted by user.")
        finally:
            if active_audio_process and active_audio_process.poll() is None:
                logger.info("Terminating active audio recording...")
                active_audio_process.terminate()
                active_audio_process.wait()
            logger.info(f"Capture session finished. Total segments captured: {index}")
