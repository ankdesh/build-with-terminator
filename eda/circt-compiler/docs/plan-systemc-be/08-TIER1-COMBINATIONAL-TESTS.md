# 08 — Tier 1: Combinational Test Cases

> **Prerequisite**: Comb emission patterns (03), graph linearization (06), test framework (07).

---

## 8.1 Test Matrix

| # | Design | Input Ports | Output Ports | Comb Ops Exercised | Complexity |
|---|--------|------------|-------------|-------------------|------------|
| 1 | `passthrough` | `a: i32` | `b: i32` | None (direct wire) | Trivial |
| 2 | `adder_32` | `a: i32, b: i32` | `sum: i32` | `comb.add` | Low |
| 3 | `subtractor_16` | `a: i16, b: i16` | `diff: i16` | `comb.sub` | Low |
| 4 | `multiplier_8` | `a: i8, b: i8` | `prod: i16` | `comb.mul`, `comb.concat` | Low |
| 5 | `bitwise_ops` | `a: i32, b: i32` | `and_r, or_r, xor_r, not_r: i32` | `comb.and`, `comb.or`, `comb.xor` | Low |
| 6 | `shift_ops` | `a: i32, shamt: i5` | `shl_r, shru_r, shrs_r: i32` | `comb.shl`, `comb.shru`, `comb.shrs` | Low |
| 7 | `comparator` | `a: i32, b: i32` | `eq, ne, slt, sle, sgt, sge, ult, ule, ugt, uge: i1` | `comb.icmp` (all 10 predicates) | Medium |
| 8 | `mux_2to1` | `sel: i1, a: i32, b: i32` | `out: i32` | `comb.mux` | Low |
| 9 | `mux_4to1` | `sel: i2, d0-d3: i32` | `out: i32` | `comb.mux` (nested) | Medium |
| 10 | `alu_8bit` | `a: i8, b: i8, op: i3` | `result: i8, zero: i1` | `comb.add/sub/and/or/xor/mux/icmp` | Medium |
| 11 | `extract_concat` | `a: i32` | `hi: i16, lo: i16, rejoined: i32` | `comb.extract`, `comb.concat` | Medium |
| 12 | `wide_adder_128` | `a: i128, b: i128` | `sum: i128` | `comb.add` on wide types | Medium |
| 13 | `wide_bv_1024` | `a: i1024, b: i1024` | `and_r: i1024` | `comb.and` on `sc_bv<1024>` | High |
| 14 | `parity_32` | `a: i32` | `p: i1` | `comb.parity` | Low |
| 15 | `replicate_8to32` | `a: i8` | `out: i32` | `comb.replicate` | Low |
| 16 | `divmod_unsigned` | `a: i32, b: i32` | `quot: i32, rem: i32` | `comb.divu`, `comb.modu` | Medium |
| 17 | `divmod_signed` | `a: si32, b: si32` | `quot: si32, rem: si32` | `comb.divs`, `comb.mods` | Medium |
| 18 | `multiop_chain` | `a-d: i16` | `out: i16` | `comb.add`, `comb.mul`, `comb.and` variadic (3+ operands) | Medium |
| 19 | `bit_reverse_16` | `a: i16` | `out: i16` | `comb.reverse` | Low |
| 20 | `non_power2_width` | `a: i7, b: i7` | `sum: i7` | `comb.add` on `i7` (non-standard width) | Medium |

---

## 8.2 Example Design: `adder_32.mlir`

```mlir
hw.module @adder_32(in %a: i32, in %b: i32, out sum: i32) {
  %s = comb.add %a, %b : i32
  hw.output %s : i32
}
```

### Expected Pipeline Output (after comb emission is implemented):
```cpp
#include <systemc.h>

SC_MODULE(adder_32) {
  sc_in<sc_uint<32>> a;
  sc_in<sc_uint<32>> b;
  sc_out<sc_uint<32>> sum;

  SC_CTOR(adder_32) {
    SC_METHOD(innerLogic);
    sensitive << a << b;
  }

  void innerLogic() {
    sum.write(a.read() + b.read());
  }
};
```

---

## 8.3 Example Test: `test_adder.py`

```python
import pytest
from lib.circt_runner import lower_to_systemc, export_systemc, export_verilog
from lib.systemc_compiler import generate_sc_main, compile_systemc
from lib.verilator_runner import compile_verilator, generate_verilator_tb
from lib.stimulus import generate_random_stimulus
from lib.trace_compare import compare_traces
from lib.design_info import parse_design_info

DESIGN = "tests/designs/adder_32.mlir"
NUM_CYCLES = 1000
SEED = 42

def test_adder_32_cosim(tmp_path):
    info = parse_design_info(DESIGN)
    stimulus = generate_random_stimulus(info.input_ports, NUM_CYCLES, SEED)

    # SystemC path
    sc_mlir = tmp_path / "sc.mlir"
    lower_to_systemc(DESIGN, sc_mlir)
    sc_cpp = tmp_path / "dut.h"
    export_systemc(sc_mlir, sc_cpp)
    sc_main = tmp_path / "sc_main.cpp"
    generate_sc_main(info, stimulus, sc_main)
    compile_systemc([sc_cpp, sc_main], tmp_path / "sc_sim")
    # ... run and capture CSV ...

    # Verilator path
    # ... export SV, compile, run ...

    result = compare_traces(tmp_path / "sc_out.csv", tmp_path / "vl_out.csv")
    assert result.passed, f"Cycle {result.first_mismatch_cycle}: {result.mismatched_signals}"
```

---

## 8.4 Acceptance Criteria

- [ ] All 20 Tier 1 designs compile through the SystemC pipeline
- [ ] All 20 designs produce valid SystemC C++ that compiles with `g++ -lsystemc`
- [ ] At least 15/20 designs pass differential co-simulation (1000 cycles, random seed)
- [ ] Wide-type designs (i128, i1024) pass co-simulation
- [ ] Non-standard width (`i7`) emits correctly and simulates
- [ ] All `comb.icmp` predicates produce matching results
