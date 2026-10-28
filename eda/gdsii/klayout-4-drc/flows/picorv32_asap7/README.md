# PicoRV32 ASAP7 baseline

This case runs the upstream YosysHQ PicoRV32 RTL through synthesis, floorplan,
power grid generation, placement, clock tree synthesis, routing, parasitic
extraction, timing reports, and GDS generation. The final GDS is a baseline for
later autofix work. This setup does not inject faults or run the repair agent.

The core uses the native memory interface. It has the compressed instruction
set, iterative multiplier, divider, and barrel shifter enabled (RV32IMC).
The register file uses standard cells. There are no SRAM macros, pad ring,
firmware, or external memories in this core block.

The first target is a 1 ns clock, 40% core utilization, 55% placement density,
and the ASAP7 RVT library at the typical corner. ASAP7 SDC time units are **ps**:
`1000` means 1 ns. OpenROAD and the GDS export use the platform's 1x physical
dimensions. Keep the final GDS at that scale when checking it with KLayout.

## Run

Requires Docker access, Git, Python 3.12+, and about 4.5 GiB of available host
RAM. The container uses two CPU threads and a 4 GiB memory limit. It has no
network access during the build. Setup needs network access to fetch ORFS and,
if absent, the pinned container image.

From the project root:

```bash
python3 flows/picorv32_asap7/flow.py prepare
python3 flows/picorv32_asap7/flow.py run
python3 flows/picorv32_asap7/flow.py audit --profile beol
python3 flows/picorv32_asap7/flow.py status
python3 flows/picorv32_asap7/flow.py verify
```

To copy the existing local ORFS checkout and Git objects during setup:

```bash
python3 flows/picorv32_asap7/flow.py prepare \
  --orfs-source output/c2c3/toolchain/orfs
```

The new checkout is independent of the earlier benchmark. The flow mounts
ORFS and its input snapshot read-only. It writes generated files under
`output/picorv32_asap7/runs/baseline/`.

Use `run --resume` after a failure or interruption. Resume requires unchanged
inputs, toolchain receipt, and resource settings. Use `run --attempt NAME`
for a new build after a configuration change. Each RTL-to-GDS run has a
60-minute limit. DRC runs separately through `audit`. To change the output
root, put `--output PATH` before the subcommand.
`verify` checks the saved hashes without starting any EDA tool.

The BEOL audit uses the project's existing `asap7_c2c3_v1` deck. Its snapshot,
hash, report, and log remain in a separate `audits/` directory. This audit
does not establish compliance with the full public deck.

To reproduce the independent full-deck attempt with a 6 GiB limit:

```bash
python3 flows/picorv32_asap7/flow.py audit --profile public --memory-gib 6
```

This command needs at least 6.5 GiB of available host RAM. Each audit keeps
its own input deck, GDS hash, memory limit, log, report, and outcome. The audit
timeout defaults to 30 minutes. A failed audit does not rebuild the design.
The public audit exceeded both the 4 GiB and 6 GiB limits during `ACTIVE.LUP.1`
on this host. It needs more memory or a separately validated change to its
execution method. See [the measured baseline](BASELINE.md) for both receipts.

## Retained outputs

- `orfs/`: pinned flow scripts and ASAP7 collateral.
- `toolchain.json`: source revisions, image digest, tool versions, binary
  hashes, and hashes of the checked-out flow files.
- `runs/baseline/inputs/`: exact RTL, license, constraints, and config snapshot.
- `runs/baseline/results/asap7/picorv32_autofix/baseline/6_final.*`: GDS, DEF,
  OpenDB, netlist, SDC, and SPEF. Earlier stage files remain beside them.
- `runs/baseline/reports/` and `logs/`: timing, congestion, route DRC, public
  KLayout DRC, and stage metrics.
- `runs/baseline/run.json`: completion state, artifact hashes, DRC item counts,
  final metrics, and a history of run attempts.
- `runs/baseline/audits/`: independent BEOL and full public audit receipts.

`gds_generated` means that the RTL-to-GDS command completed and all required
artifacts exist. `flow_status` reports this phase separately from audits.
`complete` means that the full public DRC audit also completed. Check the
recorded DRC counts and timing metrics separately. An audit can complete and
report faults. A successful RTL-to-GDS command can leave timing violations.

Use the project Python environment to check the GDS hierarchy and physical
scale against the final DEF:

```bash
RUN=output/picorv32_asap7/runs/baseline
FINAL=$RUN/results/asap7/picorv32_autofix/baseline
.venv/bin/python flows/picorv32_asap7/inspect_gds.py \
  --gds "$FINAL/6_final.gds" --def "$FINAL/6_final.def" \
  --output "$RUN/gds_inspection.json"
```

The public ASAP7 deck is a research audit. It is not foundry signoff. The flow
does not claim LVS, post-synthesis equivalence, or firmware verification.
For later autofix work, retain `6_final.odb` with the GDS so edits can be tied
to routed nets and protected standard-cell geometry. Keep native faults
separate from faults injected for an experiment.

## Sources

The RTL is copied unchanged from
[YosysHQ/PicoRV32](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461).
Its ISC license is retained in `rtl/COPYING`.

Flow scripts and ASAP7 collateral come from
[OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/64939f3717ad7c694199ba04cb98924b98022868).
The full revisions, image digest, and vendored file hashes are in
`sources.lock.json`. Keep the upstream ASAP7 license files with any distributed
platform collateral.
