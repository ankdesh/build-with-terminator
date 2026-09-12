#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/env.sh" ]; then
    # shellcheck source=/dev/null
    source "${PROJECT_ROOT}/env.sh"
fi

BUILD_VARIANT="release"
if [[ "${1:-}" == "--debug" ]]; then
    BUILD_VARIANT="debug"
fi

echo "========================================================="
echo " Installing Face Count App onto Connected Android Phone"
echo " Build Variant: ${BUILD_VARIANT}"
echo "========================================================="

# 1. Check for connected physical device
echo "[-] Checking for connected Android devices..."
DEVICES=$(adb devices -l | grep -v "List of devices attached" | grep -v "emulator-" | grep "device" || true)

if [ -z "${DEVICES}" ]; then
    echo "[!] No physical Android phone detected."
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Connect your phone via USB."
    echo "  2. On your phone, enable Developer Options:"
    echo "     Settings > About Phone > Tap 'Build Number' 7 times."
    echo "  3. Turn on USB Debugging:"
    echo "     Settings > Developer Options > USB Debugging (ON)."
    echo "  4. Accept the 'Allow USB debugging?' popup on your phone screen."
    echo "  5. Run 'adb devices' to confirm connection."
    echo ""
    exit 1
fi

echo "[+] Detected device(s):"
echo "${DEVICES}"
echo ""

# 2. Build the APK
cd "${PROJECT_ROOT}"
if [ "${BUILD_VARIANT}" == "release" ]; then
    echo "[-] Assembling Release APK (optimized arm64-v8a footprint)..."
    ./gradlew assembleRelease
    APK_PATH="${PROJECT_ROOT}/app/build/outputs/apk/release/app-release.apk"
else
    echo "[-] Assembling Debug APK..."
    ./gradlew assembleDebug
    APK_PATH="${PROJECT_ROOT}/app/build/outputs/apk/debug/app-debug.apk"
fi

if [ ! -f "${APK_PATH}" ]; then
    echo "[!] APK file not found at: ${APK_PATH}"
    exit 1
fi

echo "[+] APK built successfully: $(ls -lh "${APK_PATH}" | awk '{print $5}')"

# 3. Install APK on phone
echo "[-] Installing APK on phone..."
adb install -r -d "${APK_PATH}"

# 4. Launch app
echo "[-] Launching Face Count app..."
adb shell am start -n com.example.facecount/.ui.MainActivity

echo "========================================================="
echo " App successfully installed and launched on your phone!"
echo "========================================================="
