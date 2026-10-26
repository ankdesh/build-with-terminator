# 01 — Environment & Build Setup

This guide details how to set up the development environment, install prerequisites, configure CMake, and build CIRCT with SystemC and Slang support from scratch on any Linux workstation or build server.

---

## 1.1 Prerequisites & System Dependencies

Ensure the following packages and tools are installed before configuring the build:

### Ubuntu / Debian

```bash
sudo apt-get update && sudo apt-get install -y \
  build-essential \
  cmake \
  ninja-build \
  git \
  python3 \
  python3-dev \
  verilator \
  libsystemc-dev \
  binutils-gold
```

> [!NOTE]
> If `libsystemc-dev` is not available in your package manager, install or compile SystemC from Accellera (e.g. version 2.3.3 or 2.3.4) and set:
> ```bash
> export SYSTEMC_HOME=/path/to/systemc-install
> export CMAKE_PREFIX_PATH=$SYSTEMC_HOME:$CMAKE_PREFIX_PATH
> ```

### Python Environment Tooling (`uv`)

Install `uv` for fast, deterministic Python virtual environment management:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 1.2 Repository Layout & Git Isolation

The CIRCT source tree and build artifacts are contained in a dedicated `external/` folder that is ignored by the top-level repository's version control. CIRCT modifications are tracked on a separate branch (`develop-asd`).

```
eda/circt-compiler/
├── .gitignore              # Ignores external/, .venv/, sim_build/, *.vcd, *.fst
├── docs/
│   └── plan/               # Planning and architectural specifications
├── external/               # ← Git-ignored boundary
│   ├── circt/              # CIRCT source clone (branch: develop-asd)
│   │   ├── llvm/           # LLVM submodule (pinned at circt's required commit)
│   │   ├── lib/Conversion/HWToSystemC/
│   │   ├── lib/Target/ExportSystemC/
│   │   ├── lib/Dialect/SystemC/
│   │   └── ...
│   └── build/              # Unified LLVM + MLIR + CIRCT build directory
│       ├── bin/            # circt-opt, circt-translate, firtool, circt-verilog, FileCheck
│       └── lib/            # Static libraries
├── tests/                  # Differential co-simulation test suite (Python/uv)
│   ├── pyproject.toml
│   ├── conftest.py
│   ├── designs/            # .mlir, .sv, .fir test designs
│   ├── tier1_comb/
│   ├── tier2_seq/
│   ├── tier3_hierarchy/
│   └── tier4_complex/
├── scripts/                # Utility scripts
└── GEMINI.md               # Project constitution
```

Ensure `.gitignore` contains:

```gitignore
external/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
sim_build/
*.vcd
*.fst
```

---

## 1.3 Step-by-Step Initial Setup

Run the following commands from the project root (`eda/circt-compiler/`):

```bash
# 1. Create wrapper directory
mkdir -p external

# 2. Clone the CIRCT repository
git clone https://github.com/ankdesh/circt external/circt

# 3. Create and switch to the develop-asd branch
git -C external/circt checkout -b develop-asd

# 4. Initialize LLVM submodule (shallow clone recommended to minimize download size)
git -C external/circt submodule update --init --depth 1 llvm
```

---

## 1.4 CMake Configuration

Generate the Ninja build files using a unified build. CIRCT is built in-tree with LLVM and MLIR:

```bash
cmake -G Ninja \
  -S external/circt/llvm/llvm \
  -B external/build \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DLLVM_ENABLE_PROJECTS="mlir" \
  -DLLVM_EXTERNAL_PROJECTS="circt" \
  -DLLVM_EXTERNAL_CIRCT_SOURCE_DIR=$(pwd)/external/circt \
  -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_USE_SPLIT_DWARF=ON \
  -DLLVM_TARGETS_TO_BUILD="host" \
  -DLLVM_USE_LINKER=gold \
  -DLLVM_PARALLEL_LINK_JOBS=1 \
  -DCIRCT_SLANG_FRONTEND_ENABLED=ON \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

### Explanation of Key Flags

| Flag | Purpose |
|------|---------|
| `-DCMAKE_BUILD_TYPE=RelWithDebInfo` | Optimized binary with debug info for gdb stepping |
| `-DLLVM_ENABLE_ASSERTIONS=ON` | Enables compiler invariant checks and MLIR verifiers |
| `-DLLVM_USE_SPLIT_DWARF=ON` | Separates debug symbols into `.dwo` files to minimize peak linker memory |
| `-DLLVM_TARGETS_TO_BUILD="host"` | Restricts codegen to host architecture (X86), eliminating unneeded backends |
| `-DLLVM_USE_LINKER=gold` | Uses GNU Gold (or `lld` if available) for faster linking |
| `-DLLVM_PARALLEL_LINK_JOBS=1` | Restricts parallel link processes to prevent Out-Of-Memory (OOM) |
| `-DCIRCT_SLANG_FRONTEND_ENABLED=ON` | Enables Slang frontend (`circt-verilog`) for SystemVerilog ingestion |
| `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` | Generates `compile_commands.json` for language servers (`clangd`) |

---

## 1.5 Build Execution & Resource Guidelines

Build the specific tool binaries required for the SystemC backend and testing:

```bash
ninja -C external/build -j <NUM_JOBS> circt-opt circt-translate firtool circt-verilog FileCheck count not
```

### Sizing `<NUM_JOBS>` to Avoid OOM

Building large MLIR/CIRCT translation units requires sufficient RAM per compiler thread:

| Host Memory | Recommended `-j` Flag | `-DLLVM_PARALLEL_LINK_JOBS` | Expected Build Time |
|-------------|-----------------------|-----------------------------|---------------------|
| ≤ 16 GB RAM | `-j 1` or `-j 2` | `1` | 2–3 hours |
| 32 GB RAM | `-j 4` | `1` | ~45 minutes |
| 64 GB RAM | `-j 8` to `-j 12` | `2` | ~20 minutes |
| 128+ GB RAM | `-j $(nproc)` | `4` | ~10 minutes |

> [!TIP]
> Targeting only `circt-opt circt-translate firtool circt-verilog FileCheck count not` compiles ~3,057 units, avoiding ~4,000 unneeded LLVM tools and test harnesses.

---

## 1.6 Post-Build Verification (Smoke Tests)

Once compilation finishes, verify that the binaries and toolchains are functional:

```bash
# 1. Verify binary versions and help banners
external/build/bin/circt-opt --version
external/build/bin/circt-translate --version
external/build/bin/firtool --version
external/build/bin/circt-verilog --version

# 2. Test HW -> SystemC pass execution
cat <<'EOF' > /tmp/smoke.mlir
hw.module @smoke(in %a: i32, in %b: i32, out sum: i32) {
  %c = comb.add %a, %b : i32
  hw.output %c : i32
}
EOF

external/build/bin/circt-opt --convert-hw-to-systemc /tmp/smoke.mlir

# 3. Test ExportSystemC on an existing dialect sample
external/build/bin/circt-translate --export-systemc \
  external/circt/test/Target/ExportSystemC/basic.mlir

# 4. Run CIRCT lit tests for the SystemC dialect and exporter
external/build/bin/llvm-lit -sv \
  external/circt/test/Conversion/HWToSystemC/ \
  external/circt/test/Dialect/SystemC/ \
  external/circt/test/Target/ExportSystemC/
```

---

## 1.7 Incremental Rebuilding After Code Modifications

When editing files in `external/circt/` on the `develop-asd` branch:

```bash
# Rebuild only the affected compiler binaries
ninja -C external/build circt-opt circt-translate

# Run affected lit tests
external/build/bin/llvm-lit -sv external/circt/test/Target/ExportSystemC/
```

Link `compile_commands.json` to the CIRCT source directory for IDE autocomplete and diagnostics:

```bash
ln -sf $(pwd)/external/build/compile_commands.json external/circt/compile_commands.json
```
