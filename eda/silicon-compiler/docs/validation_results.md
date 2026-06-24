# Validation Results

Validation was run on 2026-06-24 with Python 3.12, SiliconCompiler 0.37.12, and `yowasp-yosys` 0.66.

## Commands

```bash
uv sync
.venv/bin/python -m py_compile scripts/run_synthesis.py tests/test_synthesis_setup.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/run_synthesis.py --target freepdk45
.venv/bin/python scripts/run_synthesis.py --target sky130
.venv/bin/python scripts/run_synthesis.py --target asap7
```

## Results

| Target | Status | Cells | Cell area | Nets | Pins | Result file |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `freepdk45` | pass | 1821 | 2154.334 | 1898 | 77 | `results/freepdk45.json` |
| `sky130` | pass | 1483 | 10741.552 | 1519 | 77 | `results/sky130.json` |
| `asap7` | pass | 1451 | 149.82408 | 1487 | 77 | `results/asap7.json` |

The flow stops after Yosys logic synthesis. It does not run floorplanning, placement, CTS, routing, extraction, signoff, or STA.
