# Synopsys Design Compiler Setup

This setup mirrors the sample RTL and PDK/library targets used by the Yosys flow, but it is designed to work before a Synopsys Design Compiler binary or license is available.

## Configuration

Edit `config/dc_config.json` when DC is available. The most important fields are:

- `dc_shell_bin`: executable name or absolute path for `dc_shell`.
- `license_env`: optional values for `SNPSLMD_LICENSE_FILE` or `LM_LICENSE_FILE`. Empty strings mean the script will look at the current shell environment.
- `design`: top module, RTL files, clock name, reset name, and clock period.
- `compile`: DC compile command and options.
- `targets.<target>.liberty_corner`: corner to resolve from SiliconCompiler/LambdaPDK.
- `targets.<target>.target_library_override`: explicit Liberty files to use instead of auto-resolving from SiliconCompiler. Use this when your licensed production PDK has different Liberty locations.
- `targets.<target>.link_library_extra`: extra DB or Liberty files needed for memories, IO, or DesignWare setup.
- `targets.<target>.dc_setup_extra_tcl`: raw Tcl lines inserted after `target_library` and `link_library` setup.

## Preflight Without DC

Generate Tcl and preflight JSON for all configured targets:

```bash
.venv/bin/python scripts/setup_dc.py --target all
```

The preflight checks:

- RTL files exist.
- Liberty files resolve through SiliconCompiler or the config override.
- Compressed Liberty files are decompressed into `build/dc/<target>/inputs/`.
- DC Tcl is generated at `build/dc/<target>/scripts/dc_synth.tcl`.
- `dc_shell` is discoverable on `PATH` or through `dc_shell_bin`.
- A license environment variable is present.

Without `dc_shell` or a license, the status is expected to be `preflight_only`. This is still a useful validation because it proves the sample RTL, target config, Liberty resolution, and generated DC scripts are coherent.

## Running DC Later

After updating `config/dc_config.json` and setting the license environment, run:

```bash
.venv/bin/python scripts/setup_dc.py --target freepdk45 --run
.venv/bin/python scripts/setup_dc.py --target sky130 --run
.venv/bin/python scripts/setup_dc.py --target asap7 --run
```

Each run writes reports and outputs under `build/dc/<target>/`:

- `reports/check_design.rpt`
- `reports/qor.rpt`
- `reports/area.rpt`
- `reports/timing.rpt`
- `reports/power.rpt`
- `outputs/mac_unit_<target>.vg`
- `outputs/mac_unit_<target>.ddc`
- `outputs/mac_unit_<target>.sdc`

## Comparison Notes

For a fair Yosys/DC comparison, keep the RTL, clock period, target Liberty set, and reported metrics fixed. If a production DC PDK uses `.db` libraries while Yosys uses `.lib`, record the exact source/corner relationship in this document or in a target-specific note before comparing results.
