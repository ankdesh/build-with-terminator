# PicoRV32 ASAP7 baseline result

Run date: 28 October 2026. Run name: `baseline`.

The complete RTL-to-GDS flow passed. The final GDS also passed the hierarchy,
routing-layer presence, and physical-scale checks against the final DEF.
The existing `asap7_c2c3_v1` BEOL deck completed with zero markers across its
11 checks. The full public audit exceeded both the 4 GiB and 6 GiB memory
limits during `ACTIVE.LUP.1`. Both attempts are retained. The full public
audit has no complete report or final marker count.

| Item | Measured result |
|---|---:|
| Clock target | 1000 ps / 1 GHz |
| Timing corner | TC: 0.70 V, 0 °C, RVT |
| Initial core utilization | 40% |
| Placement density target | 0.55 |
| Die size | 74.218 × 74.218 µm |
| Core area | 4905.31 µm² |
| Synthesis cells | 16,600 |
| Final standard cells, excluding fillers | 17,273 |
| Total OpenDB instances, including fillers | 41,863 |
| Final setup worst slack | +27.0727 ps |
| Final hold worst slack | +47.4385 ps |
| Setup and hold total negative slack | 0 ps |
| Setup and hold violation counts | 0 |
| Max slew, capacitance, and fanout violations | 0 |
| OpenROAD routing DRC violations | 0 |
| Antenna net and pin violations | 0 |
| BEOL markers under `asap7_c2c3_v1` | 0 |
| Full public ASAP7 DRC | Incomplete: memory limit |
| VDD worst static IR drop | 2.94 mV / 0.42% |
| GDS size | 21,374,196 bytes |
| GDS database unit | 0.00025 µm / 0.25 nm |
| GDS top cell | `picorv32` |
| GDS cell definitions | 72 |
| Empty GDS cells | 0 |

The core uses native memory ports and RV32IMC parameters. The multiplier,
divider, and barrel shifter are enabled. The upstream RTL is unchanged.
Disabled IRQ and external PCPI features leave unused top-level ports in this
direct core build. OpenROAD reports these unused ports during optimization.

## Files

All generated files remain under `output/picorv32_asap7/`. They are excluded
from Git. The flow inputs, pinned source, run guide, and checks are retained
in this repository.

Final files:

```text
output/picorv32_asap7/runs/baseline/
  results/asap7/picorv32_autofix/baseline/
    6_final.gds
    6_final.def
    6_final.odb
    6_final.v
    6_final.sdc
    6_final.spef
  reports/asap7/picorv32_autofix/baseline/
    5_route_drc.rpt
    6_finish.rpt
    final_all.webp
  audits/beol_001/
    audit.json
    report.lyrdb
  audits/public_002/
    audit.json
    audit.log
  gds_inspection.json
  run.json
```

GDS SHA-256:

```text
b8218c1fbaab1c53fdecc3297c0ee8678be42ab7b4ea01084f1a34b99a120234
```

`run.json` records required artifacts, file hashes, final metrics, and the
public DRC result. Its `flow_status` is `complete`; its overall `drc_failed`
status records the failed full audit. `toolchain.json` in the output root records the image,
source, PDK, and tool binary hashes. `gds_inspection.json` records the GDS/DEF
comparison and stored geometry counts by layer.

The [run guide](README.md) gives setup and resume commands.
[Source pins](sources.lock.json) identify the exact upstream inputs.
The [machine-readable baseline summary](baseline_summary.json) records the
final file hashes and separate flow and audit outcomes.

## Full public audit limits

The original 4 GiB attempt took 8 minutes 44 seconds and reached 4,179,528 KiB
peak resident memory. The independent 6 GiB retry took 11 minutes 48 seconds
and reached 6,278,812 KiB. Both were killed while evaluating the latch-up
interaction in public deck line 186. The 6 GiB retry returned exit code 137.
No complete full-deck `.lyrdb` was produced. Its final marker count is unknown.

The host had about 7.1 GiB available after the retry. A larger bounded retry
needs more free memory. The independent `audit` command supports a different
memory limit on a suitable host. The BEOL audit completed in 81.2 seconds.
Its zero-marker result applies to the eleven named checks in that deck.

## Validation scope

Nine focused tests passed. They cover source identity, incomplete flow
outputs, DRC item accounting, scale checks, refusal of a modified baseline,
and existing ASAP7 profile checks.

No artificial faults were injected. No repair agent was run. LVS, sequential
equivalence, and firmware simulation were not run. The public ASAP7 deck is
a research audit. Foundry signoff was not established.

Keep this baseline unchanged. Use copies for later autofix experiments and
retain the native GDS grid, standard-cell geometry, and routed net identities.
