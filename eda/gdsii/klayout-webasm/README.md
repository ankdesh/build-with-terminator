# KLayout WebAssembly (`klayout-wasm`) & React Sandbox

This repository contains the C++ WebAssembly compilation setup for KLayout's core database library (`klayout_tl` and `klayout_db`), TypeScript declarations, and an interactive **React CAD & DRC Sandbox Application**.

---

## Architecture Overview

- **C++ Database Engine**: Extracted pure C++ modules of `klayout_tl`, `klayout_gsi`, and `klayout_db` (bypassing Qt GUI, scripting wrappers, cURL, and Git dependencies).
- **Embind Binding Layer**: C++ bindings (`bindings/klayout_bind.cc`) exposing geometry (`Point`, `Box`, `Polygon`, `Edge`), hierarchy (`Layout`, `LayerProperties`), DRC Boolean engine (`Region` AND/OR/XOR/NOT/Sizing), and file stream readers/writers for GDSII and OASIS streams using Emscripten's virtual filesystem (MEMFS).
- **NPM Package**: `klayout-wasm` in `pkg/` containing `klayout.d.ts` TypeScript definitions and `klayout_db.js` / `klayout_db.wasm`.
- **React Sandbox App**: Modern Vite + React + TypeScript CAD sandbox in `demo/` with an HTML5 2D Canvas renderer.

---

## Automated One-Step Setup & Build Script

To replicate the entire WebAssembly compilation, C++ patching, packaging, and React demo setup on any fresh server, simply run:

```bash
chmod +x setup_and_build.sh
./setup_and_build.sh
```

This automated script handles:
1. Cloning KLayout repository (if missing) and applying WebAssembly compatibility patches.
2. Installing & activating Emscripten SDK (`emsdk`).
3. Compiling KLayout C++ database core to `klayout_db.wasm` and `klayout_db.js`.
4. Packaging `klayout-wasm` with TypeScript `.d.ts` definitions.
5. Installing React demo dependencies (`npm install`) and building the app (`npm run build`).

---

## Quick Start: Running the React Sandbox App

> [!IMPORTANT]
> **Do not open `index.html` directly via `file://` protocol**. Modern web browsers block WebAssembly loading and ES module imports over `file://` due to CORS security policies. The app must be served via a local HTTP server (`http://localhost`).

### 1. Launch the React Development Server

```bash
cd demo
npm install
npm run dev
```

Open your browser and navigate to: **[http://localhost:3000](http://localhost:3000)**

### 2. Build or Preview Production Bundle

```bash
cd demo
npm run build
npm run preview
```

---

## Building the WebAssembly Binary from Source

If you modify C++ source files or Embind bindings, rebuild the Wasm target using the Emscripten toolchain.

### Prerequisites

- Emscripten SDK (`emsdk`)
- CMake >= 3.15
- GCC / Clang & Make

### Build Steps

```bash
# 1. Activate Emscripten SDK environment
source ./emsdk/emsdk_env.sh

# 2. Configure and compile using CMake
mkdir -p build_wasm
cd build_wasm
emcmake cmake ..
emmake make -j$(nproc)

# 3. Copy generated Wasm artifacts to package and React demo
cd ..
cp build_wasm/klayout_db.js build_wasm/klayout_db.wasm pkg/
cp build_wasm/klayout_db.js build_wasm/klayout_db.wasm demo/public/
mkdir -p demo/node_modules/klayout-wasm
cp pkg/* demo/node_modules/klayout-wasm/
```

---

## React Sandbox Features

- 🎨 **HTML5 2D Canvas Renderer**: High-performance CAD shape rendering with zoom, pan, grid overlay, and coordinate display.
- ⚡ **Region Boolean & DRC Engine**: Interactive UI for performing Region operations (`AND`, `OR`, `XOR`, `NOT`, `Sizing`) powered by KLayout's C++ algorithms.
- 📐 **CAD Presets**: Instant loading of NMOS Transistor and CMOS Inverter micro-layouts.
- 💾 **GDSII Stream Export**: Generate layout primitives programmatically and export GDSII streams.

---

## License

KLayout core database code is licensed under the GNU General Public License (GPL v2 or later).
