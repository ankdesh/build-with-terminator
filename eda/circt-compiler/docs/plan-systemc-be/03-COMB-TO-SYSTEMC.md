# 03 — Comb → SystemC / EmitC Lowering

> **Objective**: Enable all 21 `comb` dialect operations to pass through the full
> `HWToSystemC` → `ExportSystemC` pipeline and emit valid, compilable SystemC C++ code.

---

## 3.1 Design Decision: Emission Patterns vs. Conversion Pass

Two implementation strategies are possible:

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| **A. Add `CombEmissionPatterns` to `ExportSystemC`** | Add `OpEmissionPattern<comb::AddOp>` etc. in a new `CombEmissionPatterns.cpp` | Simplest; no intermediate IR changes; direct C++ operator emission | Mixes C++ emission concerns with MLIR-level ops; harder to test in isolation |
| **B. Create a `CombToEmitC` conversion pass** | New `--convert-comb-to-emitc` pass that lowers `comb.*` to `emitc.*` (expressions, calls) | Clean separation; testable at MLIR level; reusable for other C-family backends | Requires modeling C operators in `emitc`; more code churn |

> [!IMPORTANT]
> **Recommended**: **Approach A** (emission patterns in `ExportSystemC`).
> Rationale: The existing architecture already dispatches on `OperationName` with full
> C++ precedence support. Adding `CombEmissionPatterns.cpp` follows the established
> pattern (`HWEmissionPatterns.cpp`, `EmitCEmissionPatterns.cpp`, `SystemCEmissionPatterns.cpp`).

---

## 3.2 Implementation Plan — All 21 `comb` Ops

### File to Create
```
lib/Target/ExportSystemC/Patterns/CombEmissionPatterns.cpp
lib/Target/ExportSystemC/Patterns/CombEmissionPatterns.h
```

### Registration
In `RegisterAllEmitters.h`, add:
```cpp
#include "Patterns/CombEmissionPatterns.h"
// In registerAllOpEmitters():
populateCombOpEmitters(opPatterns);
```

### Op-by-Op Mapping

| `comb` Op | C++ Emission | Precedence | Variadic Handling | Notes |
|-----------|-------------|------------|-------------------|-------|
| `comb.add` | `a + b` | `ADD` (6) | Chain: `a + b + c` | SystemC `sc_uint` supports `+` |
| `comb.sub` | `a - b` | `ADD` (6) | Binary only | |
| `comb.mul` | `a * b` | `MUL` (5) | Chain: `a * b * c` | |
| `comb.divs` | `a / b` | `MUL` (5) | Binary only | Signed division |
| `comb.divu` | `a / b` | `MUL` (5) | Binary only | Unsigned division |
| `comb.mods` | `a % b` | `MUL` (5) | Binary only | Signed modulo |
| `comb.modu` | `a % b` | `MUL` (5) | Binary only | Unsigned modulo |
| `comb.shl` | `a << b` | `SHIFT` (7) | Binary only | |
| `comb.shru` | `a >> b` | `SHIFT` (7) | Binary only | Logical shift (unsigned context) |
| `comb.shrs` | `a >> b` | `SHIFT` (7) | Binary only | Arithmetic shift (signed context) |
| `comb.and` | `a & b` | `BITWISE_AND` (11) | Chain: `a & b & c` | |
| `comb.or` | `a \| b` | `BITWISE_OR` (13) | Chain: `a \| b \| c` | |
| `comb.xor` | `a ^ b` | `BITWISE_XOR` (12) | Chain / unary NOT | 1-operand `comb.xor` = bitwise NOT `~a` |
| `comb.icmp` | `a == b`, `a < b`, etc. | `COMPARISON` (9) / `EQUALITY` (10) | Binary only | Map predicate attr to C++ operator |
| `comb.mux` | `sel ? a : b` | `CONDITIONAL` (16) | Ternary | |
| `comb.concat` | Bit concatenation | — | Variadic | Emit as `(a, b)` SystemC concat or shift+or pattern |
| `comb.extract` | Bit slice | — | — | `x.range(hi, lo)` for SystemC types, or `(x >> lo) & mask` |
| `comb.replicate` | Bit replication | — | — | Loop or manual concat |
| `comb.parity` | XOR reduction | — | — | `x.xor_reduce()` or manual fold |
| `comb.truth_table` | Lookup table | — | — | Emit as nested ternary or switch |
| `comb.reverse` | Bit reversal | — | — | Loop-based reversal or `sc_bv` `.reverse()` |

### Detailed Implementation Notes

#### 3.2.1 Variadic Ops (`add`, `mul`, `and`, `or`, `xor`)

These ops accept 2+ operands. Emit as chained binary expressions:
```cpp
// comb.add %a, %b, %c : i32  →  a + b + c
void emitInlined(Value val, EmissionPrinter &p) override {
  auto op = val.getDefiningOp<comb::AddOp>();
  interleave(op.getOperands(), p.getEmitter(),
    [&]() { p << " + "; });
}
```

#### 3.2.2 `comb.xor` as NOT

When `comb.xor` has exactly one operand (after canonicalization, CIRCT represents `~x` as
`comb.xor %x, -1`), emit as `~x` with precedence `UNARY`:
```cpp
// comb.xor %a, %allones : i32  →  ~a
// comb.xor %a, %b : i32        →  a ^ b
```

#### 3.2.3 `comb.icmp` Predicate Mapping

| MLIR Predicate | C++ Operator |
|---------------|-------------|
| `eq` | `==` |
| `ne` | `!=` |
| `slt` / `ult` | `<` |
| `sle` / `ule` | `<=` |
| `sgt` / `ugt` | `>` |
| `sge` / `uge` | `>=` |

#### 3.2.4 `comb.concat` — SystemC Concatenation

SystemC provides a `concat()` function and the `,` operator:
```cpp
// comb.concat %hi, %lo : i16, i16  →  (hi, lo)
// Or: sc_bv<32> result = (hi, lo);
```

For wide types, use `(op1, op2, op3)` with nested comma expressions.

#### 3.2.5 `comb.extract` — Bit Slicing

SystemC `sc_uint`/`sc_int` support `.range(hi, lo)`:
```cpp
// comb.extract %x from 4 : (i32) -> i8  →  x.range(11, 4)
```

For `i1` extraction, use `.bit(idx)` or `x[idx]`.

---

## 3.3 Testing Strategy

### Unit Tests (FileCheck)
Create `test/Target/ExportSystemC/comb_ops.mlir`:
```mlir
// RUN: circt-opt --convert-hw-to-systemc %s | circt-translate --export-systemc | FileCheck %s

hw.module @adder(in %a: i32, in %b: i32, out sum: i32) {
  %c = comb.add %a, %b : i32
  hw.output %c : i32
}
// CHECK: SC_MODULE(adder)
// CHECK: void innerLogic()
// CHECK: {{.*}} + {{.*}}
```

### Integration Tests (Compile + Lint)
Create `integration_test/Target/ExportSystemC/comb_basic.mlir`:
```mlir
// REQUIRES: systemc
// RUN: circt-opt --convert-hw-to-systemc %s | circt-translate --export-systemc > %t.cpp
// RUN: g++ -std=c++17 -fsyntax-only -I/usr/include %t.cpp
```

### Differential Co-Simulation Tests
Covered in [07-TESTING-FRAMEWORK.md](07-TESTING-FRAMEWORK.md) and [08-TIER1-COMBINATIONAL-TESTS.md](08-TIER1-COMBINATIONAL-TESTS.md).

---

## 3.4 Acceptance Criteria

- [ ] All 21 `comb` ops have emission patterns with correct C++ operator precedence
- [ ] Variadic ops (`add`, `mul`, `and`, `or`, `xor`) chain correctly for 2+ operands
- [ ] `comb.xor` emits `~` for single-operand NOT
- [ ] `comb.icmp` maps all 10 predicates to C++ comparison operators
- [ ] `comb.concat`, `comb.extract`, `comb.replicate` emit valid SystemC expressions
- [ ] All FileCheck tests pass
- [ ] Integration tests compile emitted C++ successfully with `g++ -lsystemc`
- [ ] At least 5 Tier 1 designs pass differential co-simulation
