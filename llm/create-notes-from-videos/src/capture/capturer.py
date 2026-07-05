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
        """Runs the capture loop, recording audio continuously and logging screenshot timestamps."""
        import json
        from datetime import datetime
        self.monitor_source = self._get_monitor_source()
        
        # Determine the session prefix based on starting time
        start_time_dt = datetime.now()
        session_prefix = start_time_dt.strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Starting capture session in: {self.output_dir}")
        logger.info(f"Session Prefix: {session_prefix}")
        logger.info(f"Interval: {self.interval}s, Max Duration: {self.duration}s")
        
        continuous_audio_path = os.path.join(self.output_dir, f"{session_prefix}_continuous.wav")
        timestamps_path = os.path.join(self.output_dir, f"{session_prefix}_timestamps.json")
        
        # Start a single continuous audio recording in the background
        audio_cmd = [
            "ffmpeg", "-y",
            "-f", "pulse",
            "-i", self.monitor_source
        ]
        if self.duration:
            audio_cmd.extend(["-t", str(self.duration)])
        audio_cmd.append(continuous_audio_path)
        
        logger.info("Starting continuous background audio recording...")
        audio_process = subprocess.Popen(audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        start_time = time.time()
        index = 0
        timestamps_records = []
        
        try:
            while True:
                # Responsive sleep loop to handle KeyboardInterrupt immediately
                sleep_start = time.time()
                while time.time() - sleep_start < self.interval:
                    elapsed = time.time() - start_time
                    if self.duration and elapsed >= self.duration:
                        break
                    time.sleep(0.1)
                
                elapsed = time.time() - start_time
                if self.duration and elapsed >= self.duration:
                    logger.info("Target duration reached. Stopping capture.")
                    break
                
                img_name = f"{session_prefix}_part{index:04d}.png"
                img_path = os.path.join(self.output_dir, img_name)
                
                logger.info(f"Capturing screenshot: {img_name} at {elapsed:.2f}s")
                self.capture_screenshot(img_path)
                
                timestamps_records.append({
                    "screenshot": img_name,
                    "timestamp": elapsed
                })
                
                index += 1
                
        except KeyboardInterrupt:
            logger.info("Capture session interrupted by user.")
        finally:
            # 1. Stop the continuous audio recording and wait for it to flush
            if audio_process and audio_process.poll() is None:
                logger.info("Stopping continuous audio recording process...")
                audio_process.terminate()
                try:
                    audio_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Audio process did not terminate gracefully, killing it.")
                    audio_process.kill()
                    audio_process.wait()
            
            # 2. Write the timestamps metadata file
            logger.info(f"Saving screenshot timestamps to: {timestamps_path}")
            try:
                with open(timestamps_path, "w", encoding="utf-8") as f:
                    json.dump(timestamps_records, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save timestamps JSON: {e}")
                
            logger.info(f"Capture session finished. Total screenshots captured: {index + 1}")
