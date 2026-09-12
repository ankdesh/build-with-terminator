#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-$HOME/.android_toolchain}"

echo "========================================================="
echo " Setting up Android Toolchain and JDK 17"
echo " Target directory: ${TOOLCHAIN_DIR}"
echo "========================================================="

mkdir -p "${TOOLCHAIN_DIR}/downloads"
mkdir -p "${TOOLCHAIN_DIR}/jdk-17"
mkdir -p "${TOOLCHAIN_DIR}/android-sdk"

# 1. Install Eclipse Temurin JDK 17 if not already installed
JDK_DIR="${TOOLCHAIN_DIR}/jdk-17"
if [ ! -f "${JDK_DIR}/bin/javac" ]; then
    echo "[-] Downloading Eclipse Temurin JDK 17 (x64 Linux)..."
    JDK_TAR="${TOOLCHAIN_DIR}/downloads/temurin-jdk17.tar.gz"
    curl -L --retry 3 -o "${JDK_TAR}" "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk"
    echo "[-] Extracting JDK 17..."
    tar -xzf "${JDK_TAR}" -C "${JDK_DIR}" --strip-components=1
    rm -f "${JDK_TAR}"
    echo "[+] JDK 17 installed successfully at ${JDK_DIR}"
else
    echo "[+] JDK 17 already present at ${JDK_DIR}"
fi

export JAVA_HOME="${JDK_DIR}"
export PATH="${JAVA_HOME}/bin:${PATH}"
echo "Java version: $(java -version 2>&1 | head -n 1)"

# 2. Install Android Command-Line Tools
ANDROID_SDK_DIR="${TOOLCHAIN_DIR}/android-sdk"
CMDLINE_TOOLS_DIR="${ANDROID_SDK_DIR}/cmdline-tools/latest"
if [ ! -f "${CMDLINE_TOOLS_DIR}/bin/sdkmanager" ]; then
    echo "[-] Downloading Android Command-Line Tools..."
    CMDLINE_ZIP="${TOOLCHAIN_DIR}/downloads/commandlinetools.zip"
    curl -L --retry 3 -o "${CMDLINE_ZIP}" "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    echo "[-] Extracting Command-Line Tools..."
    TMP_EXTRACT="${TOOLCHAIN_DIR}/downloads/cmdline_tmp"
    mkdir -p "${TMP_EXTRACT}"
    unzip -q -o "${CMDLINE_ZIP}" -d "${TMP_EXTRACT}"
    mkdir -p "${ANDROID_SDK_DIR}/cmdline-tools"
    rm -rf "${CMDLINE_TOOLS_DIR}"
    mv "${TMP_EXTRACT}/cmdline-tools" "${CMDLINE_TOOLS_DIR}"
    rm -rf "${TMP_EXTRACT}" "${CMDLINE_ZIP}"
    echo "[+] Android Command-Line Tools installed at ${CMDLINE_TOOLS_DIR}"
else
    echo "[+] Android Command-Line Tools already present at ${CMDLINE_TOOLS_DIR}"
fi

export ANDROID_HOME="${ANDROID_SDK_DIR}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_DIR}"
export PATH="${CMDLINE_TOOLS_DIR}/bin:${ANDROID_SDK_DIR}/platform-tools:${ANDROID_SDK_DIR}/emulator:${PATH}"

# 3. Accept licenses
echo "[-] Accepting Android SDK licenses..."
yes | "${CMDLINE_TOOLS_DIR}/bin/sdkmanager" --licenses > /dev/null 2>&1 || true

# 4. Install required SDK components
echo "[-] Installing platform-tools, platforms;android-34, build-tools;34.0.0, emulator, system-image, and NDK..."
"${CMDLINE_TOOLS_DIR}/bin/sdkmanager" \
    "platform-tools" \
    "platforms;android-34" \
    "build-tools;34.0.0" \
    "emulator" \
    "system-images;android-34;google_apis;x86_64" \
    "ndk;25.2.9519653"

# 5. Create local.properties in project root
cat <<EOF > "${PROJECT_ROOT}/local.properties"
sdk.dir=${ANDROID_SDK_DIR}
EOF
echo "[+] Updated ${PROJECT_ROOT}/local.properties"

# 6. Generate env.sh for simple sourcing
cat <<EOF > "${PROJECT_ROOT}/env.sh"
#!/usr/bin/env bash
export JAVA_HOME="${JDK_DIR}"
export ANDROID_HOME="${ANDROID_SDK_DIR}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_DIR}"
export PATH="\${JAVA_HOME}/bin:\${ANDROID_HOME}/cmdline-tools/latest/bin:\${ANDROID_HOME}/platform-tools:\${ANDROID_HOME}/emulator:\${PATH}"
EOF
chmod +x "${PROJECT_ROOT}/env.sh"
echo "[+] Generated ${PROJECT_ROOT}/env.sh. Run 'source env.sh' to activate."

echo "========================================================="
echo " Toolchain setup completed successfully!"
echo "========================================================="
