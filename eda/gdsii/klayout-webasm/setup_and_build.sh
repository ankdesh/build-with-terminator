#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "  KLayout WebAssembly & React Sandbox Setup Script"
echo "================================================================="

# 1. Clone KLayout repository if missing
if [ ! -d "klayout" ]; then
    echo "--> [1/6] Cloning KLayout repository..."
    git clone --depth 1 https://github.com/KLayout/klayout.git klayout
else
    echo "--> [1/6] KLayout directory found."
fi

# Apply platform compatibility patches to KLayout source files
echo "--> Applying KLayout WebAssembly compatibility patches..."
python3 -c "
# 1. Add <cstdlib> & <cmath> to dbCommon.h
with open('klayout/src/db/db/dbCommon.h', 'r') as f:
    content = f.read()
if '<cstdlib>' not in content:
    content = content.replace('#if !defined(HDR_dbCommon_h)\n# define HDR_dbCommon_h', '#if !defined(HDR_dbCommon_h)\n# define HDR_dbCommon_h\n#include <cstdlib>\n#include <cmath>')
    with open('klayout/src/db/db/dbCommon.h', 'w') as f:
        f.write(content)

# 2. Fix std::abs ambiguity in dbPolygonTools.cc
with open('klayout/src/db/db/dbPolygonTools.cc', 'r') as f:
    content = f.read()
content = content.replace('std::abs (db::vprod (p2 - p1, p0 - pm1))', 'std::abs ((double) db::vprod (p2 - p1, p0 - pm1))')
content = content.replace('std::abs (db::vprod (p2 - p1, p1 - p0))', 'std::abs ((double) db::vprod (p2 - p1, p1 - p0))')
with open('klayout/src/db/db/dbPolygonTools.cc', 'w') as f:
    f.write(content)

# 3. Add __EMSCRIPTEN__ fallback to tlThreads.cc
with open('klayout/src/tl/tl/tlThreads.cc', 'r') as f:
    content = f.read()
content = content.replace('#if defined(_WIN32) || defined(__APPLE__)', '#if defined(_WIN32) || defined(__APPLE__) || defined(__EMSCRIPTEN__)')
with open('klayout/src/tl/tl/tlThreads.cc', 'w') as f:
    f.write(content)
"

# 2. Clone and install Emscripten SDK if missing
if [ ! -d "emsdk" ]; then
    echo "--> [2/6] Installing Emscripten SDK (emsdk)..."
    git clone https://github.com/emscripten-core/emsdk.git emsdk
    cd emsdk
    ./emsdk install latest
    ./emsdk activate latest
    cd ..
else
    echo "--> [2/6] Emscripten SDK directory found."
fi

# Source Emscripten environment variables
source ./emsdk/emsdk_env.sh

# 3. Build WebAssembly library using CMake & Emscripten
echo "--> [3/6] Building klayout_db WebAssembly module..."
rm -rf build_wasm
mkdir -p build_wasm
cd build_wasm
emcmake cmake ..
emmake make -j$(nproc)
cd ..

# 4. Copy build artifacts to pkg/ and demo/
echo "--> [4/6] Packaging WebAssembly artifacts..."
cp build_wasm/klayout_db.js build_wasm/klayout_db.wasm pkg/
mkdir -p demo/public
cp build_wasm/klayout_db.js build_wasm/klayout_db.wasm demo/public/
mkdir -p demo/node_modules/klayout-wasm
cp pkg/* demo/node_modules/klayout-wasm/

# 5. Install React Demo dependencies & Build Demo App
echo "--> [5/6] Building React Demo Sandbox Application..."
cd demo
npm install
npm run build
cd ..

echo "================================================================="
echo "  SUCCESS! KLayout WebAssembly package & React Sandbox are ready."
echo "  To start the application, run:"
echo "    cd demo && npm run dev"
echo "================================================================="
