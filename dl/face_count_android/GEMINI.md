# Project Constitution: Face Count Android

## Mission & Purpose
Face Count Android is a lightweight, modern Android application engineered to accurately detect and count human faces—with explicit support for tilted, rotated, and partially visible or occluded faces—while strictly containing the application distribution footprint to under 15 MB.

---

## Architectural Principles

1. **Modular & Decoupled Architecture**:
   - Clean Architecture pattern:
     - `domain`: Pure business entities (`FaceDetection`, `BoundingBox`, `Landmark`, `DetectionResult`) and engine interface (`FaceDetector`).
     - `data`: Implementation of detector engine (`OpenCVYuNetDetector`), asset management (`ModelAssetManager`), and image utilities (`BitmapUtils`).
     - `ui`: Presentation layer with Jetpack Compose, Material 3, and reactive unidirectional data flow (`StateFlow`).
2. **One Primary Class per File**:
   - Every class, interface, and top-level data contract resides in its own distinct file.
3. **Footprint & Binary Size Optimization**:
   - Release builds bundle only 64-bit ARM (`arm64-v8a`), reducing binary weight from >60MB to ~12-15MB.
   - Debug builds include `arm64-v8a` and `x86_64` for seamless local testing on Android emulators.
   - Ultra-lightweight ONNX model: YuNet (`face_detection_yunet_2023mar.onnx`, 228 KB) deployed via OpenCV DNN (`FaceDetectorYN`).
4. **Fail Explicitly & Early**:
   - Explicit assertions and exceptions for model loading and unreadable image buffers.
   - Safe resource lifecycle: all native OpenCV `Mat` structures are released in `finally` blocks.

---

## Reproducible Environment & Toolchains

- **JDK**: Eclipse Temurin OpenJDK 17.
- **Android SDK**: Compile SDK 34, Min SDK 24, Build Tools 34.0.0.
- **Automation Scripts**:
  - `scripts/setup_toolchain.sh`: Sets up JDK 17, Android commandline tools, platform, and emulator.
  - `scripts/setup_opencv.sh`: Configures OpenCV 4.10.0 Android SDK with `arm64-v8a` and `x86_64` native binaries.
  - `scripts/download_model.sh`: Downloads YuNet ONNX model directly to assets.
  - `scripts/start_emulator.sh`: Headless AVD launch and boot verification.
  - `scripts/install_phone.sh`: Automated physical phone deployment and launch via ADB.
  - `scripts/run_tests.sh`: Automated build, APK size analysis, emulator deployment, and screenshot verification.
  - `env.sh`: Sourced environment variables for reproducible shell execution.
