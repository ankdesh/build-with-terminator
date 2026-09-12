#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/env.sh" ]; then
    # shellcheck source=/dev/null
    source "${PROJECT_ROOT}/env.sh"
fi

AVD_NAME="FaceCountAVD"
SYS_IMAGE="system-images;android-34;google_apis;x86_64"

echo "========================================================="
echo " Starting Android Emulator: ${AVD_NAME}"
echo "========================================================="

# 1. Check if AVD exists, create if missing
if ! avdmanager list avd | grep -q "${AVD_NAME}"; then
    echo "[-] Creating AVD '${AVD_NAME}'..."
    echo "no" | avdmanager create avd -n "${AVD_NAME}" -k "${SYS_IMAGE}" --force
    echo "[+] AVD created."
else
    echo "[+] AVD '${AVD_NAME}' exists."
fi

# 2. Check if emulator is already running
RUNNING_DEVICE=$(adb devices | grep -E "emulator-[0-9]+" | awk '{print $1}' | head -n 1 || true)
if [ -n "${RUNNING_DEVICE}" ]; then
    echo "[+] Emulator already running: ${RUNNING_DEVICE}"
else
    echo "[-] Launching emulator in headless mode..."
    # If KVM is writable, we don't need -no-accel
    nohup emulator -avd "${AVD_NAME}" \
        -no-window \
        -no-audio \
        -no-boot-anim \
        -gpu swiftshader_indirect \
        -camera-back none \
        -camera-front none \
        > /tmp/emulator.log 2>&1 &
    disown || true
    
    echo "[-] Waiting for device to appear on adb..."
    adb wait-for-device
    
    echo "[-] Waiting for system boot to complete..."
    BOOT_COMPLETED=""
    MAX_ATTEMPTS=60
    ATTEMPT=0
    while [ "${BOOT_COMPLETED}" != "1" ]; do
        ATTEMPT=$((ATTEMPT + 1))
        if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
            echo "[!] Timeout waiting for emulator to boot."
            cat /tmp/emulator.log | tail -n 20
            exit 1
        fi
        sleep 3
        BOOT_COMPLETED=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
        echo "    Boot status (${ATTEMPT}/${MAX_ATTEMPTS}): ${BOOT_COMPLETED}"
    done
    
    # Dismiss lockscreen
    adb shell input keyevent 82 || true
    echo "[+] Emulator fully booted and unlocked!"
fi

echo "========================================================="
