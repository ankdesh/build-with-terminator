# Video Note Capturer

A set of Python scripts to capture and process slides and audio from online video tutorials on Linux.

---

## How It Works

1. **Capture**: Records a single continuous audio file of the system speaker output (loopback) and periodically takes screenshots of the full screen, logging the exact elapsed timestamps of each screenshot to a JSON file. This eliminates any audio loss or gaps during transitions.
2. **Processing**:
   - Transcribes the entire continuous audio file at once using `faster-whisper`.
   - Maps the transcribed segments to their corresponding screenshots using the timestamps.
   - Performs SSIM (Structural Similarity Index) comparison to filter out duplicate/similar slides and merges their transcripts.
   - Sends the transcript of each unique slide to the **OpenAI API** to generate 2-level hierarchical pointwise notes, passing the transcripts of the **previous** and **next** slides as additional context to maintain lecture continuity.
   - Compiles the unique slide images and their corresponding notes into a structured PDF.

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

## Configuration

The project features a centralized configuration file: [config.json](file:///home/ankdesh/explore/build-with-terminator/llm/create-notes-from-videos/config.json).

You can edit this file to configure default settings:
- **`llm`**:
  - `model`: The OpenAI model to use (default: `gpt-4o-mini`).
  - `temperature`: Creativity control (default: `0.2`).
- **`whisper`**:
  - `model_size`: Whisper model size (default: `base`).
- **`capture`**:
  - `interval`: Time in seconds between snapshots (default: `10`).
  - `threshold`: SSIM similarity threshold for slide merging (default: `0.95`).

### OpenAI API Key
To use the summarization and PDF generation features, you must set your OpenAI API key in your terminal:
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

---

## Usage

### 1. Capture Session

To capture the full screen (it is recommended to play the video tutorial maximized or in fullscreen) and system audio:

```bash
python capture.py --interval 10 --duration 120 --output-dir captures/my_session
```

**Options:**
- `--interval`, `-i`: Time in seconds between snapshots (default: `10`).
- `--duration`, `-d`: Total capture time in seconds. If omitted, it captures indefinitely until you press `Ctrl+C`.
- `--output-dir`, `-o`: Directory to save the raw captures (default: `captures/session_<timestamp>`).
- `--audio-source`, `-a`: Manually specify the PulseAudio/PipeWire audio source. If not specified, it auto-detects it using `pactl`.

### 2. Process Session

To transcribe the audio, align segments, merge similar slides, generate context-aware notes, and compile the PDF:

```bash
python process.py --input-dir captures/my_session --output-dir processed/my_session
```

**Options:**
- `--input-dir`, `-i`: The directory containing the raw captured screenshots, continuous audio, and timestamps JSON.
- `--output-dir`, `-o`: The directory where the final slides, transcripts, notes, and PDF will be saved.
- `--threshold`, `-t`: SSIM similarity threshold (overrides `config.json`).
- `--model`, `-m`: Whisper model size to use (overrides `config.json`).
- `--llm-model`: OpenAI model to use (overrides `config.json`).
- `--llm-temperature`: OpenAI temperature (overrides `config.json`).
- `--skip-llm`: Skip OpenAI note generation and only use raw transcripts in the PDF.
- `--pdf-image-quality`: JPEG quality for images embedded in the PDF (1-100, default from config: `80`). Lower values reduce file size significantly.
