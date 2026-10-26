# 05 — HW Aggregates & Misc Lowering

> **Objective**: Support HW dialect aggregate types (arrays, structs, unions, enums)
> and miscellaneous ops (`hw.wire`, `hw.bitcast`, `hw.module.extern`) in the SystemC backend.

---

## 5.1 Struct Support

### 5.1.1 Type Mapping

| CIRCT Type | SystemC/C++ Emission |
|-----------|---------------------|
| `!hw.struct<field1: i32, field2: i8>` | `struct { sc_uint<32> field1; sc_uint<8> field2; }` or `emitc.opaque` |

**Implementation options**:
1. **EmitC opaque struct**: Map `!hw.struct` to `!emitc.opaque<"struct_name">` with
   a forward-declared C++ struct emitted at module scope.
2. **Inline struct emission**: Add a `TypeEmissionPattern` for `hw::StructType` that
   emits an anonymous `struct { ... }` or references a named typedef.

> [!IMPORTANT]
> Recommended: Emit named `struct` typedefs at the top of the generated header,
> then reference them by name inside `SC_MODULE` bodies.

### 5.1.2 Operations

| Op | C++ Emission | Priority |
|----|-------------|----------|
| `hw.struct_create` | `{ .field1 = val1, .field2 = val2 }` (C++20 designated init) or constructor call | P2 |
| `hw.struct_extract` | `obj.fieldName` via `emitc.member_access` | P2 |
| `hw.struct_inject` | Copy + field assignment | P2 |
| `hw.struct_explode` | Multi-field extraction | P2 |
| `hw.aggregate_constant` | Constant aggregate literal | P2 |

---

## 5.2 Array Support

### 5.2.1 Type Mapping

| CIRCT Type | SystemC/C++ Emission |
|-----------|---------------------|
| `!hw.array<4 x i32>` | `sc_uint<32>[4]` or `std::array<sc_uint<32>, 4>` |

### 5.2.2 Operations

| Op | C++ Emission | Priority |
|----|-------------|----------|
| `hw.array_create` | `{val0, val1, val2, val3}` initializer list | P2 |
| `hw.array_get` | `arr[idx]` | P2 |
| `hw.array_slice` | Loop or range copy | P3 |
| `hw.array_concat` | Concatenate arrays | P3 |
| `hw.array_inject` | Copy + element assignment | P3 |

---

## 5.3 Enum & Union Support

| Op | C++ Emission | Priority |
|----|-------------|----------|
| `hw.enum.constant` | C++ `enum class` member | P3 |
| `hw.enum.cmp` | `a == b` on enum values | P3 |
| `hw.union_create` | `std::variant` or tagged union | P3 |
| `hw.union_extract` | `std::get<>()` or union member access | P3 |

---

## 5.4 Miscellaneous Ops

| Op | Lowering Strategy | Priority |
|----|-------------------|----------|
| `hw.wire` | Fold away (identity wire) or emit as `sc_signal` / C++ reference | P2 |
| `hw.bitcast` | `static_cast<>` or `reinterpret_cast<>` | P2 |
| `hw.module.extern` | Emit as forward declaration `class ModName;` or `#include` | P2 |
| `hw.param.value` | Template parameter or `constexpr` | P3 |

---

## 5.5 Arbitrary Bitwidth Integer Emission Fix

Currently `ExportSystemC`'s `IntegerTypeEmitter` only handles i1/i8/i16/i32/i64.
Non-standard widths (e.g., `i3`, `i7`, `i42`, `i128`) must map to SystemC types:

```cpp
// In IntegerTypeEmitter:
if (bw == 1) return "bool";
if (bw <= 64) {
  if (type.isSigned()) return "sc_int<" + std::to_string(bw) + ">";
  return "sc_uint<" + std::to_string(bw) + ">";
}
if (bw <= 512) {
  if (type.isSigned()) return "sc_bigint<" + std::to_string(bw) + ">";
  return "sc_biguint<" + std::to_string(bw) + ">";
}
return "sc_bv<" + std::to_string(bw) + ">";
```

> [!WARNING]
> This fix is **P1** priority — it blocks any design using non-power-of-2 bit widths.

---

## 5.6 Acceptance Criteria

- [ ] `hw.struct_create` / `hw.struct_extract` emit valid C++ struct operations
- [ ] `hw.array_create` / `hw.array_get` emit valid C++ array operations
- [ ] `hw.wire` folds or emits correctly
- [ ] `hw.bitcast` emits valid C++ cast
- [ ] `hw.module.extern` emits forward declaration
- [ ] Non-standard integer bitwidths emit `sc_uint<N>` / `sc_int<N>`
- [ ] All new patterns have FileCheck unit tests
