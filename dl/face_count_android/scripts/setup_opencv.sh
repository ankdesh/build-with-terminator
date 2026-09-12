#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOWNLOADS_DIR="${PROJECT_ROOT}/tools/downloads"
OPENCV_VERSION="4.10.0"
OPENCV_ZIP="${DOWNLOADS_DIR}/opencv-${OPENCV_VERSION}-android-sdk.zip"
OPENCV_URL="https://github.com/opencv/opencv/releases/download/${OPENCV_VERSION}/opencv-${OPENCV_VERSION}-android-sdk.zip"

echo "========================================================="
echo " Setting up OpenCV ${OPENCV_VERSION} Android SDK"
echo "========================================================="

mkdir -p "${DOWNLOADS_DIR}"

if [ ! -f "${OPENCV_ZIP}" ]; then
    echo "[-] Downloading OpenCV ${OPENCV_VERSION} Android SDK..."
    curl -L --retry 3 -o "${OPENCV_ZIP}" "${OPENCV_URL}"
else
    echo "[+] OpenCV SDK archive already downloaded at ${OPENCV_ZIP}"
fi

TMP_DIR="${DOWNLOADS_DIR}/opencv_tmp"
rm -rf "${TMP_DIR}"
mkdir -p "${TMP_DIR}"

echo "[-] Extracting OpenCV Java sources and native libraries..."
# Extract java sources and only arm64-v8a + x86_64 native libraries to save space
unzip -q -o "${OPENCV_ZIP}" "OpenCV-android-sdk/sdk/java/*" -d "${TMP_DIR}"
unzip -q -o "${OPENCV_ZIP}" "OpenCV-android-sdk/sdk/native/libs/arm64-v8a/libopencv_java4.so" -d "${TMP_DIR}"
unzip -q -o "${OPENCV_ZIP}" "OpenCV-android-sdk/sdk/native/libs/x86_64/libopencv_java4.so" -d "${TMP_DIR}"
unzip -q -o "${OPENCV_ZIP}" "OpenCV-android-sdk/sdk/native/libs/arm64-v8a/libc++_shared.so" -d "${TMP_DIR}" 2>/dev/null || true
unzip -q -o "${OPENCV_ZIP}" "OpenCV-android-sdk/sdk/native/libs/x86_64/libc++_shared.so" -d "${TMP_DIR}" 2>/dev/null || true

# Target module directory: opencv
OPENCV_MODULE_DIR="${PROJECT_ROOT}/opencv"
mkdir -p "${OPENCV_MODULE_DIR}/src/main/java"
mkdir -p "${OPENCV_MODULE_DIR}/src/main/jniLibs/arm64-v8a"
mkdir -p "${OPENCV_MODULE_DIR}/src/main/jniLibs/x86_64"

# Copy Java sources and resources
cp -r "${TMP_DIR}/OpenCV-android-sdk/sdk/java/src/"* "${OPENCV_MODULE_DIR}/src/main/java/"
mkdir -p "${OPENCV_MODULE_DIR}/src/main/res"
if [ -d "${TMP_DIR}/OpenCV-android-sdk/sdk/java/res" ]; then
    cp -r "${TMP_DIR}/OpenCV-android-sdk/sdk/java/res/"* "${OPENCV_MODULE_DIR}/src/main/res/"
fi

# Copy native libraries
cp "${TMP_DIR}/OpenCV-android-sdk/sdk/native/libs/arm64-v8a/libopencv_java4.so" "${OPENCV_MODULE_DIR}/src/main/jniLibs/arm64-v8a/"
cp "${TMP_DIR}/OpenCV-android-sdk/sdk/native/libs/x86_64/libopencv_java4.so" "${OPENCV_MODULE_DIR}/src/main/jniLibs/x86_64/"

# Copy libc++_shared.so from NDK if available
NDK_DIR="${ANDROID_SDK_ROOT:-$HOME/.android_toolchain/android-sdk}/ndk"
if [ -d "${NDK_DIR}" ]; then
    LATEST_NDK=$(ls -1d "${NDK_DIR}"/* 2>/dev/null | tail -n 1 || true)
    if [ -n "${LATEST_NDK}" ]; then
        ARM64_LIBCXX="${LATEST_NDK}/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so"
        X86_64_LIBCXX="${LATEST_NDK}/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/x86_64-linux-android/libc++_shared.so"
        if [ -f "${ARM64_LIBCXX}" ]; then
            cp "${ARM64_LIBCXX}" "${OPENCV_MODULE_DIR}/src/main/jniLibs/arm64-v8a/"
        fi
        if [ -f "${X86_64_LIBCXX}" ]; then
            cp "${X86_64_LIBCXX}" "${OPENCV_MODULE_DIR}/src/main/jniLibs/x86_64/"
        fi
    fi
fi

# Clean up temp
rm -rf "${TMP_DIR}"

echo "[+] OpenCV ${OPENCV_VERSION} module initialized at ${OPENCV_MODULE_DIR}"
echo "Native libraries:"
ls -lh "${OPENCV_MODULE_DIR}/src/main/jniLibs/arm64-v8a/"
ls -lh "${OPENCV_MODULE_DIR}/src/main/jniLibs/x86_64/"

echo "========================================================="
echo " OpenCV setup completed successfully!"
echo "========================================================="
