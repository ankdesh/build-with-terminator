# SiliconCompiler + Yosys Logic Synthesis Setup

This project validates a local SiliconCompiler setup for logic synthesis only.
The current flow stops after the Yosys ASIC synthesis task and does not run
floorplan, placement, CTS, routing, extraction, signoff, or STA tasks.

## Targets

The script supports three open PDK/library configurations from the installed
LambdaPDK package:

- `freepdk45`: FreePDK45 with Nangate45 standard cells.
- `sky130`: SkyWater 130 nm with the Sky130 high-density standard-cell library.
- `asap7`: ASAP7 with RVT as the main standard-cell library plus LVT and SLVT.

`freepdk45` is the default because it is small and is a good first validation
target. The other targets are useful for later comparisons because they give
different technology/library characteristics while keeping the RTL and tool
flow constant.

## Flow

`scripts/run_synthesis.py` builds a SiliconCompiler `ASIC` project around the
sample RTL in `rtl/mac_unit.v` and uses the SiliconCompiler/LambdaPDK target
configuration to resolve the standard-cell Liberty files for the selected PDK.

The default `direct` runner then writes a plain Yosys script under
`build/direct/<target>/synth.ys` and invokes the project-local `yowasp-yosys`
executable through `bin/yosys`. This avoids requiring a system-wide Yosys
install. Compressed Liberty files are decompressed into the target build
directory because the WASM Yosys package is built without zlib support.

The script also keeps an optional `--runner sc` mode that creates a custom
SiliconCompiler flow named `yosys_logic_synthesis` with only one node:

```text
synthesis -> siliconcompiler.tools.yosys.syn_asic.ASICSynthesis
```

That stock scheduler path expects a regular system Yosys binary with Tcl support.
The bundled `yowasp-yosys` package can run the direct flow, but it cannot execute
SiliconCompiler's stock Tcl synthesis task.

## Outputs

Each run writes the normal SiliconCompiler build tree under `build/` and a small
machine-readable summary under `results/<target>.json`. The JSON summary records
the target, flow name, design name, and key metrics such as cells, area,
register count, nets, pins, warnings, and errors when SiliconCompiler reports
them.

## Future DC Comparison Notes

Keep the RTL, clock period, target libraries, and result extraction stable when
adding Synopsys Design Compiler. Add DC as a parallel synthesis-only flow rather
than reusing Yosys-specific settings, then normalize the metric names in a common
post-processing script.

