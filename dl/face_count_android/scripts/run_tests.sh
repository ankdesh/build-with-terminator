#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================="
echo " Face Count Android - Automated Build & Verification Test"
echo "========================================================="

if [ -f "${PROJECT_ROOT}/env.sh" ]; then
    # shellcheck source=/dev/null
    source "${PROJECT_ROOT}/env.sh"
fi

mkdir -p "${PROJECT_ROOT}/test_output"

# Step 1: Build Debug APK (arm64-v8a + x86_64 for emulator)
echo "[-] Building Debug APK..."
cd "${PROJECT_ROOT}"
./gradlew assembleDebug

DEBUG_APK="${PROJECT_ROOT}/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "${DEBUG_APK}" ]; then
    echo "[!] Debug APK build failed."
    exit 1
fi

echo "[+] Debug APK built successfully:"
ls -lh "${DEBUG_APK}"
echo "Debug APK native library architectures:"
unzip -l "${DEBUG_APK}" | grep "lib/" || true

# Step 2: Build Release APK (Strictly arm64-v8a optimized)
echo "[-] Building Release APK with R8 minification and arm64-v8a ABI filter..."
./gradlew assembleRelease

RELEASE_APK="${PROJECT_ROOT}/app/build/outputs/apk/release/app-release.apk"
if [ ! -f "${RELEASE_APK}" ]; then
    RELEASE_APK="${PROJECT_ROOT}/app/build/outputs/apk/release/app-release-unsigned.apk"
fi

if [ -f "${RELEASE_APK}" ]; then
    echo "[+] Release APK built successfully:"
    ls -lh "${RELEASE_APK}"
    echo "Release APK native library contents (verifying single ABI arm64-v8a):"
    unzip -l "${RELEASE_APK}" | grep "lib/" || true
else
    echo "[!] Warning: Release APK not found at expected path."
fi

# Step 3: Launch Emulator
echo "[-] Ensuring Android emulator is running..."
"${SCRIPT_DIR}/start_emulator.sh"

# Step 4: Install Debug APK onto emulator
echo "[-] Installing app-debug.apk on emulator..."
adb install -r "${DEBUG_APK}"

# Step 5: Push test sample image to emulator device storage
echo "[-] Pushing test image to emulator /sdcard/Download/..."
adb push "${PROJECT_ROOT}/app/src/main/assets/samples/group_sample.jpg" /sdcard/Download/sample_face.jpg
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/sample_face.jpg > /dev/null 2>&1 || true

# Step 6: Launch application on emulator
echo "[-] Launching Face Count MainActivity on emulator..."
adb shell am force-stop com.example.facecount
adb logcat -c
adb shell am start -n com.example.facecount/.ui.MainActivity
sleep 5

# Step 7: Simulate tapping Sample Photo button to run detection
echo "[-] Triggering Sample Photo detection..."
adb shell input tap 105 588
sleep 3

# Step 8: Capture Screenshot & Verification Log
SCREENSHOT_PATH="${PROJECT_ROOT}/test_output/emulator_screenshot.png"
echo "[-] Capturing emulator screenshot to ${SCREENSHOT_PATH}..."
adb exec-out screencap -p > "${SCREENSHOT_PATH}"

echo "[-] Capturing application logcat..."
adb logcat -d | grep -iE "FaceCount|OpenCV|YuNet" | tail -n 30 > "${PROJECT_ROOT}/test_output/app_log.txt" || true

echo "========================================================="
echo " Verification Complete!"
echo " Screenshot: ${SCREENSHOT_PATH}"
echo " Log: ${PROJECT_ROOT}/test_output/app_log.txt"
echo "========================================================="
