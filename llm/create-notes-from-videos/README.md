# Video Note Capturer

A set of Python scripts to capture and process slides and audio from online video tutorials (running in Google Chrome) on Linux.

---

## Requirements & Prerequisites

Apart from the Python packages, this tool relies on a few system-level utilities for screen and audio capture.

### Installing Prerequisites on Debian/Ubuntu:
```bash
sudo apt update
sudo apt install ffmpeg pulseaudio-utils
```

- **Linux OS** with an X11/XWayland session.
- **`ffmpeg`**: Used for recording audio and taking screenshots.
- **`pactl`** (from `pulseaudio-utils` or `pipewire-utils`): Used to auto-detect the default audio monitor source.

---

## Installation

Create the virtual environment and install the dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

---

## Usage

### 1. Capture Session

To capture the full screen and system audio in real-time (it is recommended to play the video tutorial maximized or in fullscreen):

```bash
python capture.py --interval 10 --duration 120 --output-dir captures/my_session
```

**Options:**
- `--interval`, `-i`: Time in seconds between snapshots (default: `10`).
- `--duration`, `-d`: Total capture time in seconds. If omitted, it captures indefinitely until you press `Ctrl+C`.
- `--output-dir`, `-o`: Directory to save the raw captures (default: `captures/session_<timestamp>`).
- `--audio-source`, `-a`: Manually specify the PulseAudio/PipeWire audio source (e.g., `default` or a specific monitor source like `alsa_output.pci-0000_00_1f.3.analog-stereo.monitor`). If not specified, the script will attempt to auto-detect it using `pactl`.

### 2. Process Session

To transcribe the audio segments, compare consecutive screenshots using SSIM, and merge similar slides:

```bash
python process.py --input-dir captures/my_session --output-dir processed/my_session --threshold 0.95 --model base
```

**Options:**
- `--input-dir`, `-i`: The directory containing the raw captured snapshots and audio.
- `--output-dir`, `-o`: The directory where the final slides and transcripts will be saved (default: `processed/session_<timestamp>`).
- `--threshold`, `-t`: SSIM similarity threshold (default: `0.95`). Slides with a similarity score above this threshold are merged together with their transcripts.
- `--model`, `-m`: The Whisper model size to use (e.g., `tiny`, `base`, `small`, `medium`, `large-v3`). Using `tiny` or `base` is recommended for speed on CPU.

