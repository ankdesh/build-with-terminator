#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASSETS_DIR="${PROJECT_ROOT}/app/src/main/assets/models"
MODEL_FILE="${ASSETS_DIR}/face_detection_yunet_2023mar.onnx"
MODEL_URL="https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

echo "========================================================="
echo " Downloading OpenCV YuNet Face Detection ONNX Model"
echo "========================================================="

mkdir -p "${ASSETS_DIR}"

if [ ! -f "${MODEL_FILE}" ]; then
    echo "[-] Downloading YuNet ONNX model (~232 KB)..."
    curl -L --retry 3 -o "${MODEL_FILE}" "${MODEL_URL}"
    echo "[+] Download complete: ${MODEL_FILE}"
else
    echo "[+] Model file already exists at ${MODEL_FILE}"
fi

ls -lh "${MODEL_FILE}"
echo "========================================================="
