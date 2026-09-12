# Face Count Android (OpenCV + YuNet)

A modern, ultra-lightweight Android application that detects and counts human faces—including partially visible, tilted, and occluded faces—drawing responsive bounding boxes, confidence badges, and facial landmarks with minimal application footprint (~12–15 MB).

---

## Key Features

- **OpenCV YuNet Detection Engine**: Employs `cv::FaceDetectorYN` using an ultra-compact (~228 KB) ONNX model capable of identifying multi-angle and partially occluded faces.
- **Minimal Footprint Packaging**:
  - Employs ABI filtering targeting `arm64-v8a` for release distribution (~12–15 MB APK vs standard 60–80 MB universal builds).
  - Supports `x86_64` in debug mode for emulator verification.
- **Dynamic Sensitivity Slider**: Allows users to fine-tune the detection confidence threshold in real-time (10% to 95%) with instant UI re-filtering without repeated native inference latency.
- **Jetpack Compose & Material 3 UI**: Clean, declarative UI with aspect-fit Canvas bounding box overlays, landmark pins, and latency telemetry.
- **Multiple Input Sources**:
  - Photo picker (Storage Access Framework / `PickVisualMedia`).
  - Camera capture (`TakePicturePreview`).
  - Instant bundled sample photo button for testing without external images.

---

## Project Structure

```
├── app/
│   ├── build.gradle.kts           # App configuration, ABI filters, Compose dependencies
│   ├── proguard-rules.pro         # Rules preserving OpenCV JNI and native symbols
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── assets/
│       │   ├── models/            # face_detection_yunet_2023mar.onnx (~228 KB)
│       │   └── samples/           # Bundled sample test image
│       └── java/com/example/facecount/
│           ├── FaceCountApp.kt    # OpenCV runtime initialization
│           ├── domain/            # Domain entities and FaceDetector interface
│           ├── data/              # OpenCVYuNetDetector, ModelAssetManager, BitmapUtils
│           └── ui/                # DetectionScreen, DetectionViewModel, Compose components
├── opencv/                        # OpenCV 4.10.0 Android Library module (arm64-v8a, x86_64)
├── scripts/
│   ├── setup_toolchain.sh         # Reproducible JDK 17 & Android SDK setup
│   ├── setup_opencv.sh            # Downloads & configures OpenCV Android SDK
│   ├── download_model.sh          # Downloads YuNet ONNX model weights
│   ├── start_emulator.sh          # Launches headless Android Virtual Device
│   └── run_tests.sh               # Builds APKs, verifies size, tests on emulator
├── env.sh                         # Toolchain environment variables
└── GEMINI.md                      # Project Constitution
```

---

## Quickstart & Reproducible Setup

### 1. Automated Setup
To configure the entire development environment, JDK 17, Android SDK, OpenCV SDK, and the YuNet model, run:

```bash
chmod +x scripts/*.sh
./scripts/setup_all.sh
```

Or run the individual scripts as needed:
```bash
# Set up JDK 17 and Android SDK (tools, platform 34, emulator)
./scripts/setup_toolchain.sh

# Download and configure OpenCV Android SDK
./scripts/setup_opencv.sh

# Download YuNet ONNX model
./scripts/download_model.sh
```

### 2. Activate Toolchain Environment
```bash
source env.sh
```

### 3. Build & Test on Emulator
```bash
# Builds APK, verifies size, starts emulator, installs app, and captures screenshot
./scripts/run_tests.sh
```

---

## Testing on a Physical Android Phone

You can install and test the application on your physical Android phone using either **Direct USB Installation via ADB** (fastest for development) or **Direct APK Sideloading** (no cables or adb required).

### Prerequisites: Enable Developer Options & USB Debugging
1. On your phone, navigate to **Settings > About Phone**.
2. Locate **Build Number** and tap it **7 times** until you see the prompt *"You are now a developer!"*.
3. Go to **Settings > System > Developer Options** (or search for *Developer Options*).
4. Toggle **USB Debugging** to **ON**.

---

### Method 1: Direct USB Installation (Recommended)

1. Connect your phone to your computer using a USB cable.
2. A prompt will appear on your phone: *"Allow USB debugging?"* — check **"Always allow from this computer"** and tap **Allow**.
3. Run the automated install script:
   ```bash
   source env.sh
   ./scripts/install_phone.sh
   ```
   *To install the debug build instead, pass the `--debug` flag:*
   ```bash
   ./scripts/install_phone.sh --debug
   ```
4. The script will verify device connection, build the APK, install it via ADB, and immediately launch the app on your phone.

*Manual command alternative:*
```bash
source env.sh
adb devices                                           # Verify phone is listed
./gradlew assembleRelease                             # Build optimized APK
adb install -r app/build/outputs/apk/release/app-release.apk
adb shell am start -n com.example.facecount/.ui.MainActivity
```

---

### Method 2: Sideloading the APK (No USB Cable or ADB Required)

If you prefer to download and install the APK directly on your phone without USB debugging:

1. **Build the Release APK**:
   ```bash
   source env.sh
   ./gradlew assembleRelease
   ```
   The APK is generated at:
   [`app/build/outputs/apk/release/app-release.apk`](file:///home/ankdesh/explore/build-with-terminator/dl/face_count_android/app/build/outputs/apk/release/app-release.apk)

2. **Serve the APK over Local Wi-Fi**:
   Start a temporary local web server from your terminal:
   ```bash
   cd app/build/outputs/apk/release
   python3 -m http.server 8000
   ```
   Find your computer's local IP address (`hostname -I | awk '{print $1}'`).
   On your phone (connected to the same Wi-Fi network), open the browser and go to:
   `http://<YOUR_COMPUTER_IP>:8000/app-release.apk`

   *(Alternatively, transfer `app-release.apk` via Google Drive, WhatsApp, Telegram, or USB MTP file transfer to your phone's `Downloads` folder).*

3. **Install on Phone**:
   - Tap the downloaded `app-release.apk` in your phone's notification bar or File Manager.
   - If prompted: *"For your security, your phone is not allowed to install unknown apps from this source"*, tap **Settings** and enable **"Allow from this source"**.
   - Tap **Install**, then **Open**.

---

### Method 3: Wireless ADB (Android 11+)

1. Connect your phone and PC to the same Wi-Fi network.
2. Under **Developer options**, enable **Wireless debugging**.
3. Tap **"Pair device with pairing code"** to view the IP, port, and 6-digit code.
4. In your terminal:
   ```bash
   source env.sh
   adb pair <IP>:<PORT> <PAIRING_CODE>
   adb connect <IP>:<CONNECT_PORT>
   adb install -r app/build/outputs/apk/release/app-release.apk
   ```

---

## Manual Steps (If Building from Android Studio)

1. Open the project folder (`face_count_android`) in Android Studio.
2. Android Studio will recognize the Gradle project automatically.
3. Ensure JDK 17 is selected under **Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK**.
4. Select `app` run configuration and select your connected phone from the target devices dropdown.
5. Click **Run** (or `Shift + F10`).
