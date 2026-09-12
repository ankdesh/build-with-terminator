#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================="
echo " Complete Automated Setup for Face Count Android App"
echo "========================================================="

chmod +x "${SCRIPT_DIR}"/*.sh

# Step 1: Toolchain (JDK 17 + Android SDK + Command-Line Tools + Emulator)
"${SCRIPT_DIR}/setup_toolchain.sh"

# Sourcing environment for next steps
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/env.sh"

# Step 2: OpenCV Android SDK
"${SCRIPT_DIR}/setup_opencv.sh"

# Step 3: Download YuNet ONNX model
"${SCRIPT_DIR}/download_model.sh"

echo "========================================================="
echo " All dependencies and toolchains configured successfully!"
echo " Next steps:"
echo "   1. source env.sh"
echo "   2. ./gradlew assembleDebug"
echo "   3. ./scripts/start_emulator.sh"
echo "   4. ./scripts/run_tests.sh"
echo "========================================================="
