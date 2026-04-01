# Remote UI Control with PyAutoGUI

This project provides a simple FastAPI-based server and Python client setup to remotely control GUI actions and take screenshots on a target machine (e.g., a remote Windows or Linux desktop) using `pyautogui`.

## General Idea
1. **Server (`server.py`)**: Runs on the target machine you want to control. It exposes two endpoints over HTTP:
   - `GET /screenshot`: Captures the screen using PyAutoGUI and returns a PNG image of current display.
   - `POST /action`: Accepts arbitrary Python code (as a string) in a JSON payload and safely executes it using `exec()`. You can inject `pyautogui` macros to simulate mouse movements, keyboard presses, etc.
2. **Client (`client.py`)**: Runs on your local machine. It uses the `requests` library to connect to the server's endpoints, fetch screenshots, and send Python UI interaction scripts.
3. **Tests (`test_remote.py`)**: A handy test script that invokes the client functions to verify endpoints are working by taking a screenshot and moving the mouse in a visible square. 

## Requirements
This project uses `uv` for dependency management. The main dependencies defined in `pyproject.toml` are:
- `fastapi` & `uvicorn` (for the server)
- `requests` (for the client)
- `pyautogui` (for UI interactions)
- `pillow` (for screenshot support on Linux)

## Getting Started

### 1. Installation

If you haven't already, sync your environment dependencies:
```bash
uv sync
```
*(On Linux: taking screenshots with PyAutoGUI requires native system tools. You may need to run `sudo apt install gnome-screenshot` if screenshots fail).*

### 2. Start the Server (On Target Machine)

Start the FastAPI server so it's accessible on your network (port 8000 by default):
```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```
*Note: If you run this on a headless Linux machine (no GUI), the screenshot and mouse movement tools will error out. It expects an active window manager / display.*

### 3. Controlling from Client

On your local machine, open `client.py` or run tests:
To test both the screenshot functionality and the macro execution, run:
```bash
uv run python test_remote.py
```

This will:
- Hit the `/screenshot` endpoint and save the image locally as `test_capture.png`
- Hit the `/action` endpoint to execute a brief remote macro that moves the mouse cursors visibly.

## Security Warning
The `/action` endpoint uses Python's builtin `exec()` function to run arbitrary code strings. **Do not expose this server to the public internet** or untrusted networks! This setup is meant for personal, localized remote-control tasks.
