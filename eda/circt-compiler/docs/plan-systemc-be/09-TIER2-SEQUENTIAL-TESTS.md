# 09 — Tier 2: Sequential Test Cases

> **Prerequisite**: Seq lowering (04), comb emission (03), test framework (07).

---

## 9.1 Test Matrix

| # | Design | Seq Ops Used | Comb Ops Used | Cycles | Complexity |
|---|--------|-------------|---------------|--------|------------|
| 1 | `dff_simple` | `seq.compreg` | None | 100 | Trivial |
| 2 | `dff_with_reset` | `seq.compreg` (sync reset) | None | 200 | Low |
| 3 | `dff_async_reset` | `seq.firreg` (async reset) | None | 200 | Low |
| 4 | `dff_clock_enable` | `seq.compreg.ce` | None | 200 | Low |
| 5 | `counter_8bit` | `seq.compreg` | `comb.add`, `hw.constant` | 300 | Low |
| 6 | `counter_updown` | `seq.compreg` | `comb.add/sub`, `comb.mux` | 500 | Medium |
| 7 | `counter_modN` | `seq.compreg` | `comb.add`, `comb.icmp`, `comb.mux` | 500 | Medium |
| 8 | `shift_reg_8bit` | `seq.compreg` (chain of 8) | `comb.concat`, `comb.extract` | 200 | Medium |
| 9 | `shift_reg_lfsr` | `seq.compreg` | `comb.xor`, `comb.concat`, `comb.extract` | 500 | Medium |
| 10 | `fsm_mealy_3state` | `seq.compreg` | `comb.icmp`, `comb.mux`, `comb.and/or` | 500 | Medium |
| 11 | `fsm_moore_4state` | `seq.compreg` | `comb.icmp`, `comb.mux` | 500 | Medium |
| 12 | `edge_detector` | `seq.compreg` | `comb.and`, `comb.xor` | 200 | Low |
| 13 | `pulse_generator` | `seq.compreg` | `comb.add`, `comb.icmp`, `comb.mux` | 200 | Medium |
| 14 | `pipeline_3stage` | `seq.compreg` (3 stages) | `comb.add`, `comb.mul` | 300 | Medium |
| 15 | `clock_gated_reg` | `seq.clock_gate`, `seq.compreg` | `comb.add` | 200 | Medium |

---

## 9.2 Example Design: `counter_8bit`

### Input MLIR
```mlir
hw.module @counter_8bit(
    in %clk: !seq.clock,
    in %rst: i1,
    in %en: i1,
    out count: i8
) {
  %one = hw.constant 1 : i8
  %zero = hw.constant 0 : i8
  %next = comb.add %reg, %one : i8
  %gated = comb.mux %en, %next, %reg : i8
  %reg = seq.compreg %gated, %clk reset %rst, %zero : i8
  hw.output %reg : i8
}
```

### Expected SystemC Output
```cpp
SC_MODULE(counter_8bit) {
  sc_in<bool> clk;
  sc_in<bool> rst;
  sc_in<bool> en;
  sc_out<sc_uint<8>> count;

  sc_signal<sc_uint<8>> reg;

  SC_CTOR(counter_8bit) {
    SC_METHOD(update_reg);
    sensitive << clk.pos();

    SC_METHOD(innerLogic);
    sensitive << reg << en;
  }

  void update_reg() {
    if (rst.read()) {
      reg.write(0);
    } else {
      reg.write(next_val);
    }
  }

  void innerLogic() {
    sc_uint<8> next = reg.read() + 1;
    sc_uint<8> gated = en.read() ? next : reg.read();
    next_val = gated;
    count.write(reg.read());
  }
};
```

---

## 9.3 Stimulus Strategy for Sequential Designs

Sequential designs require **clock-aware stimulus**:

```python
def generate_sequential_stimulus(
    ports: list[PortInfo],
    num_cycles: int,
    reset_cycles: int = 5,  # Hold reset high for first N cycles
    seed: int = 42,
) -> list[dict[str, int]]:
    """Generate stimulus with initial reset phase."""
    rng = random.Random(seed)
    stimulus = []

    for cycle in range(num_cycles):
        values = {}
        for port in ports:
            if port.name == "clk":
                continue  # Handled by sc_clock / Verilator clock driver
            elif port.name == "rst":
                values["rst"] = 1 if cycle < reset_cycles else 0
            elif port.direction == "input":
                max_val = (1 << port.width) - 1
                values[port.name] = rng.randint(0, max_val)
        stimulus.append(values)

    return stimulus
```

---

## 9.4 FSM Verification Notes

For FSM designs, supplement random stimulus with directed test vectors:

```python
# Mealy machine: specific input sequences to exercise all transitions
DIRECTED_SEQUENCES = [
    # (input, expected_state, expected_output)
    (0, "S0", 0),
    (1, "S1", 0),
    (1, "S2", 0),
    (0, "S0", 1),  # Output depends on input AND state
]
```

The trace comparison should verify both output ports AND (if observable) state register
values extracted via `sc_trace`.

---

## 9.5 Acceptance Criteria

- [ ] All 15 Tier 2 designs compile through the seq→systemc→export pipeline
- [ ] `seq.compreg` with/without reset lowers correctly
- [ ] `seq.compreg.ce` clock-enable behavior matches Verilator
- [ ] Counter designs count correctly for 500+ cycles
- [ ] FSM designs traverse all states correctly
- [ ] LFSR produces matching pseudo-random sequences
- [ ] Pipeline designs correctly delay data by stage count
- [ ] Clock-gated register only updates when gate is enabled
