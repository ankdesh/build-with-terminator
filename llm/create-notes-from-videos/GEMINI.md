# Project Constitution (GEMINI.md)

This document outlines the architectural guidelines, design decisions, and coding standards for the Video Note Capturer project.

---

## 1. Project Overview

The Video Note Capturer is a tool designed to capture slides and audio from online video tutorials (running in Google Chrome) and process them into a clean set of slide images and corresponding merged transcripts.

It consists of two main workflows:
1. **Capture**: Real-time periodic capturing of the Google Chrome window and loopback system audio.
2. **Processing**: Offline transcription using a local Whisper model, followed by SSIM-based image similarity filtering and transcript merging.

---

## 2. Architecture & Design Principles

As per our global guidelines:
- **One Primary Class Per File**: Keep modules lightweight and highly readable.
- **Modular, Interface-driven Design**: Interfaces and classes should be decoupled.
- **Explicit Error Handling**: Fail fast and early. Avoid swallowing exceptions.
- **No Magic Constants**: Hoist all constants (e.g., default intervals, thresholds, window names) to the top of the files or a configuration module.
- **Python Management**: Managed exclusively via `uv`.

---

## 3. Component Details

### 3.1 Capture Module (`src/capture`)
- `ScreenAudioCapturer`: The coordinator for the capture loop, capturing the full screen and system audio.

### 3.2 Processing Module (`src/process`)
- `SessionProcessor`: Orchestrates the processing flow.
- `AudioTranscriber`: Interfaces with `faster-whisper` to transcribe audio files.
- `ImageComparator`: Computes SSIM between two screenshots to determine if the slide has changed.

---

## 4. Coding Standards

- **Type Hinting**: All functions and methods must have complete type annotations.
- **Docstrings**: Document the intent, parameters, and return types of all classes and functions.
- **Logging**: Use the standard `logging` module with structured formats instead of `print` statements.
