# SiliconCompiler Yosys Logic Synthesis

This repository sets up and validates SiliconCompiler with Yosys for logic
synthesis only. It uses a sample Verilog MAC block and open PDK/library targets
so the same baseline can later be compared with Synopsys Design Compiler.

## Setup

Use `uv` with a local virtual environment:

```bash
uv venv
uv sync
chmod +x bin/yosys scripts/run_synthesis.py
```

The default runner uses SiliconCompiler to configure the design and PDK/library target, then invokes project-local `yowasp-yosys` through `bin/yosys` with a plain Yosys script. A system-wide `yosys` binary is not required for the default path.

## Run

Run the default FreePDK45/Nangate45 synthesis:

```bash
.venv/bin/python scripts/run_synthesis.py --target freepdk45
```

Run additional targets:

```bash
.venv/bin/python scripts/run_synthesis.py --target sky130
.venv/bin/python scripts/run_synthesis.py --target asap7
```

The optional stock SiliconCompiler scheduler path is available with `--runner sc`, but it expects a full system Yosys build with Tcl support on `PATH`. The project-local `yowasp-yosys` binary is used by the default `direct` runner because it does not provide the same Tcl entrypoint as regular Yosys.

Use a different synthesis clock period:

```bash
.venv/bin/python scripts/run_synthesis.py --target freepdk45 --clock-period-ns 5
```

SiliconCompiler build artifacts are written to `build/`. Compact result
summaries are written to `results/<target>.json`. The generated netlists and Yosys logs are written under `build/direct/<target>/`.

## Validate

Run the setup tests:

```bash
.venv/bin/python -m unittest discover -s tests
```

For more details, see `docs/yosys_synthesis_setup.md`.

