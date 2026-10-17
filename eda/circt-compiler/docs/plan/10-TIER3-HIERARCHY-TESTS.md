# 10 — Tier 3: Module Hierarchy Tests

> **Prerequisite**: Comb (03) + Seq (04) lowering, HW aggregates (05), test framework (07).

---

## 10.1 Test Matrix

| # | Design | Modules | Instances | Key Constructs | Complexity |
|---|--------|---------|-----------|---------------|------------|
| 1 | `hier_passthrough` | 2 (top + sub) | 1 | Basic instantiation + port binding | Low |
| 2 | `hier_adder_chain` | 2 (top + adder) | 3 (serial chain) | Multiple instances of same module | Medium |
| 3 | `hier_mixed_io` | 3 (top + comb_sub + seq_sub) | 2 | Comb + seq submodules | Medium |
| 4 | `hier_deep_3level` | 4 (top → mid → leaf × 2) | 3 | 3-level hierarchy | Medium |
| 5 | `hier_wide_fanout` | 2 (top + leaf) | 8 | 8 instances, wide fanout | Medium |
| 6 | `hier_feedback` | 2 (top + accum) | 1 | Output fed back as input via register | High |
| 7 | `hier_struct_port` | 2 (top + sub) | 1 | Struct-typed ports (needs 05) | High |
| 8 | `hier_array_port` | 2 (top + sub) | 1 | Array-typed ports (needs 05) | High |
| 9 | `hier_extern_module` | 2 (top + extern decl) | 1 | `hw.module.extern` (needs 05) | Medium |
| 10 | `hier_signal_shortcut` | 2 (top + sub) | 2 | Tests port binding optimizations (direct vs. intermediate signals) | Medium |

---

## 10.2 Key Verification Points

### 10.2.1 Port Binding Correctness
The `ConvertInstance` pattern in `HWToSystemC` has shortcut optimizations:
- **Input shortcut**: If the input value comes from `systemc.signal.read`, bind directly
  without an intermediate signal.
- **Output shortcut**: If the result has exactly one use that is `systemc.signal.write`,
  bind directly to that channel.

Tests must verify both the shortcut and non-shortcut paths.

### 10.2.2 Multi-Instance Naming
When the same module is instantiated multiple times, intermediate signals must have
unique names (e.g., `instanceName_portName`).

### 10.2.3 Hierarchical Signal Propagation
In `hier_deep_3level`, signals must propagate correctly through 3 levels:
```
top.input → mid.input → leaf.input → leaf.output → mid.output → top.output
```

---

## 10.3 Example Design: `hier_adder_chain`

```mlir
hw.module @adder(in %a: i32, in %b: i32, out sum: i32) {
  %s = comb.add %a, %b : i32
  hw.output %s : i32
}

hw.module @adder_chain(in %x: i32, in %y: i32, in %z: i32, out total: i32) {
  %ab = hw.instance "add1" @adder(a: %x: i32, b: %y: i32) -> (sum: i32)
  %abc = hw.instance "add2" @adder(a: %ab: i32, b: %z: i32) -> (sum: i32)
  hw.output %abc : i32
}
```

### Expected Verification
- `total = x + y + z` for all stimulus values
- No intermediate signal naming collisions between `add1` and `add2`
- SystemC output has two `systemc.instance.decl` and proper `bind_port` calls

---

## 10.4 Acceptance Criteria

- [ ] All 10 Tier 3 designs compile through the full pipeline
- [ ] Multi-instance designs have unique signal names
- [ ] 3-level hierarchy propagates signals correctly
- [ ] Port binding shortcuts are exercised and produce correct results
- [ ] Wide fanout (8 instances) compiles and simulates correctly
- [ ] Co-simulation matches Verilator for at least 500 cycles per design
