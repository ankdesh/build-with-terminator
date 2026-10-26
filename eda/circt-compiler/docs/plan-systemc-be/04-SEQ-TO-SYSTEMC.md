# 04 — Seq → SystemC Lowering

> **Objective**: Lower sequential CIRCT dialect operations (`seq.compreg`, `seq.compreg.ce`,
> `seq.firreg`, `seq.fifo`, `seq.hlmem`, clock ops) into SystemC clocked processes
> (`SC_METHOD` with `sensitive << clk.pos()` or `SC_THREAD` with `wait()`).

---

## 4.1 Current State

- **No `seq` dialect support exists** in either `HWToSystemC` or `ExportSystemC`.
- The only sequential lowering in CIRCT is `lower-seq-to-sv` (targets SystemVerilog).
- `seq` ops in input cause `HWToSystemC` to fail: the `SeqDialect` is not registered
  in the conversion target's legal set.
- **`!seq.clock` type** has no mapping to SystemC.

---

## 4.2 Lowering Strategy

### 4.2.1 Clock Type Mapping

| CIRCT Type | SystemC Equivalent | Notes |
|-----------|-------------------|-------|
| `!seq.clock` | `sc_in<bool>` (module port) or `sc_signal<bool>` (internal) | SystemC uses `bool` signals with `.pos()`/`.neg()` edge sensitivity |
| `seq.const_clock` | Constant `sc_clock` in testbench | Not directly needed inside modules |
| `seq.to_clock` / `seq.from_clock` | Identity (both are `bool`/`i1` underneath) | Fold away during conversion |

### 4.2.2 Register Lowering: `seq.compreg` → `SC_METHOD`

**CIRCT IR**:
```mlir
%reg = seq.compreg %next, %clk : i32
```

**Target SystemC structure**:
```cpp
SC_MODULE(mymod) {
  sc_in<bool> clk;
  sc_signal<sc_uint<32>> reg;   // State storage
  sc_uint<32> next_val;         // Combinational next-state

  SC_CTOR(mymod) {
    SC_METHOD(update_reg);
    sensitive << clk.pos();     // Posedge-triggered
  }

  void update_reg() {
    reg.write(next_val);        // Capture next state
  }

  void innerLogic() {
    next_val = /* combinational logic */;
  }
};
```

### 4.2.3 Register with Reset: `seq.compreg` with reset

```mlir
%reg = seq.compreg %next, %clk reset %rst, %resetVal : i32
```

**Target**:
```cpp
void update_reg() {
  if (rst.read()) {
    reg.write(reset_val);
  } else {
    reg.write(next_val);
  }
}
```

### 4.2.4 Register with Clock Enable: `seq.compreg.ce`

```mlir
%reg = seq.compreg.ce %next, %clk, %ce : i32
```

**Target**:
```cpp
void update_reg() {
  if (ce.read()) {
    reg.write(next_val);
  }
  // else: hold current value (implicit in sc_signal)
}
```

### 4.2.5 Clock Gating: `seq.clock_gate`

```mlir
%gated_clk = seq.clock_gate %clk, %enable : !seq.clock
```

**Target**: Either:
- Emit as gated sensitivity: `sensitive << clk.pos()` + `if (enable)` guard
- Or emit a dedicated `sc_signal<bool>` with AND logic: `gated_clk = clk & enable`

---

## 4.3 Implementation Plan

### New Files to Create

| File | Purpose |
|------|---------|
| `lib/Conversion/SeqToSystemC/SeqToSystemC.cpp` | New conversion pass `--convert-seq-to-systemc` |
| `include/circt/Conversion/SeqToSystemC.h` | Pass declaration |
| `lib/Conversion/SeqToSystemC/CMakeLists.txt` | Build integration |

### Pass Behavior

1. **Input**: `builtin.module` containing `hw.module` ops with `seq.*` ops inside.
2. **Processing**:
   - Walk all `seq.compreg` / `seq.compreg.ce` / `seq.firreg` ops.
   - For each register:
     a. Create a `systemc.signal` for the register state.
     b. Create a `systemc.cpp.variable` for the next-state value.
     c. Create a dedicated `systemc.func` (e.g., `update_regN`) containing the
        register update logic (optionally with reset/clock-enable guards).
     d. In `systemc.ctor`, register the func via `systemc.method` with
        `systemc.sensitive` pointing to the clock input's `.pos()` edge.
   - Replace all uses of the register result with `systemc.signal.read` of the state signal.
   - Replace the register's `%next` operand connection: ensure the combinational
     logic writes to the next-state variable.
3. **Output**: Modified `builtin.module` with `systemc.*` ops replacing `seq.*` ops.

### Pass Ordering

```bash
circt-opt \
  --convert-seq-to-systemc \  # 1. Lower seq → systemc (registers, clocks)
  --convert-hw-to-systemc  \  # 2. Lower hw → systemc (modules, instances)
  input.mlir
```

> [!NOTE]
> `--convert-seq-to-systemc` must run **before** `--convert-hw-to-systemc` because
> the seq pass needs to insert signals and methods into the `hw.module` body before
> it gets converted to `systemc.module`.
> 
> **Alternative**: Run seq lowering as a sub-pass within `HWToSystemC` itself.

---

## 4.4 Operations Coverage Matrix

| Seq Op | Priority | Lowering Target | Complexity |
|--------|----------|----------------|------------|
| `seq.compreg` | **P0** | `SC_METHOD` + `sensitive << clk.pos()` + `sc_signal` | Medium |
| `seq.compreg.ce` | **P0** | Same + `if (ce)` guard | Medium |
| `seq.firreg` | **P1** | Same + async/sync reset + preset handling | Medium-High |
| `seq.shiftreg` | **P1** | Chain of `sc_signal` registers | Medium |
| `seq.clock_gate` | **P1** | `if (enable)` guard or AND-gated clock signal | Low |
| `seq.clock_mux` | **P2** | `sel ? clk_a : clk_b` signal | Low |
| `seq.clock_div` | **P2** | Counter-based divider in `SC_METHOD` | Medium |
| `seq.clock_inv` | **P2** | `~clk` signal | Low |
| `seq.to_clock` / `seq.from_clock` | **P0** | Identity fold (both `bool`/`i1`) | Trivial |
| `seq.const_clock` | **P2** | Testbench `sc_clock` instantiation | Low |
| `seq.fifo` | **P3** | `SC_MODULE` with read/write pointers + `sc_signal` array | High |
| `seq.hlmem` | **P3** | `sc_signal` array with read/write port methods | High |
| `seq.firmem` + ports | **P3** | Similar to `seq.hlmem` | High |
| `seq.initial` | **P2** | `SC_THREAD` with one-shot execution | Low |

---

## 4.5 Testing Strategy

### Unit Tests (FileCheck)
```mlir
// RUN: circt-opt --convert-seq-to-systemc --convert-hw-to-systemc %s | FileCheck %s

hw.module @counter(in %clk: !seq.clock, in %rst: i1, out count: i8) {
  %next = comb.add %reg, %one : i8
  %one = hw.constant 1 : i8
  %zero = hw.constant 0 : i8
  %reg = seq.compreg %next, %clk reset %rst, %zero : i8
  hw.output %reg : i8
}
// CHECK: SC_METHOD(update_
// CHECK: sensitive << clk.pos()
// CHECK: reg.write(
```

### Differential Co-Sim
See [09-TIER2-SEQUENTIAL-TESTS.md](09-TIER2-SEQUENTIAL-TESTS.md).

---

## 4.6 Acceptance Criteria

- [ ] `seq.compreg` with and without reset lowers to `SC_METHOD` with posedge sensitivity
- [ ] `seq.compreg.ce` lowers with clock-enable guard
- [ ] `seq.firreg` with async/sync reset lowers correctly
- [ ] Clock type (`!seq.clock`) maps to `sc_in<bool>` / `sc_signal<bool>`
- [ ] `seq.to_clock` / `seq.from_clock` fold away
- [ ] `seq.clock_gate` emits enable-gated logic
- [ ] Counter and shift-register designs pass differential co-simulation vs. Verilator
