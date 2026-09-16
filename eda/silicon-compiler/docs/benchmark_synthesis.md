# LSILS/EPFL Arithmetic Benchmark Synthesis

The EPFL/LSILS benchmark suite is included as a git submodule, not copied into this repository:

```text
third_party/lsils-benchmarks -> https://github.com/lsils/benchmarks
```

Initialize it in a fresh checkout with:

```bash
git submodule update --init --recursive eda/silicon-compiler/third_party/lsils-benchmarks
```

From this directory, the arithmetic Verilog benchmarks are read from `third_party/lsils-benchmarks/arithmetic/*.v`. All arithmetic designs use `module top`.

## Configuration

Benchmark setup is controlled by `config/benchmark_synthesis.json`. It records:

- submodule path
- arithmetic benchmark names and RTL files
- default target
- top module
- DC binary/license placeholders
- DC combinational constraints

## Generate DC Scripts

Design Compiler is not available in this environment, so the supported validation is preflight-only. This command generates DC Tcl for all 10 arithmetic benchmarks across all three configured PDK/library targets:

```bash
.venv/bin/python scripts/run_benchmarks.py --benchmark all --target all --tool dc
```

Generated Tcl is written under:

```text
build/benchmarks/dc/<target>/<benchmark>/scripts/dc_synth.tcl
```

Preflight JSON is written under:

```text
results/benchmarks/dc/<target>/<benchmark>.json
```

A preflight result is expected to be `preflight_only` until `dc_shell` and a license environment are available.

## Run Yosys

Do not run the full arithmetic benchmark suite with Yosys unless you explicitly want a long run. The current validation scope is only Barrel shifter:

```bash
.venv/bin/python scripts/run_benchmarks.py --benchmark bar --target freepdk45 --tool yosys
```

This writes:

```text
results/benchmarks/yosys/freepdk45/bar.json
build/benchmarks/yosys/freepdk45/bar/synth.ys
build/benchmarks/yosys/freepdk45/bar/yosys.log
build/benchmarks/yosys/freepdk45/bar/outputs/bar_freepdk45.vg
```

## Compare Results

The runner writes comparison files after each run:

```text
results/benchmarks/comparison.csv
results/benchmarks/comparison.json
```

With the current environment, comparison contains one real Yosys result for Barrel shifter and DC preflight rows without metrics. Once DC is available, add/report DC metrics into the corresponding JSON files or extend `scripts/run_benchmarks.py` to parse DC reports after `dc_shell` execution.
