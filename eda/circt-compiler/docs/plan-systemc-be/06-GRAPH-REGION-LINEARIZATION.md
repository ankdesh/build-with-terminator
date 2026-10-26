# 06 — Graph Region Linearization

> **Objective**: Implement a topological ordering pass that resolves use-before-def
> violations when `HWToSystemC` inlines `hw.module` graph regions into `systemc.func`
> SSACFG regions.

---

## 6.1 Problem Statement

`hw.module` bodies are **graph regions** — operations have no required ordering, and
cyclic use-chains are allowed (representing combinational feedback loops in hardware).

`systemc.func` bodies are **SSACFG regions** — every use must be dominated by its
definition (i.e., appear after it in program order).

When `HWToSystemC` (`ConvertHWModule`, line 82-84) moves the body of `hw.module` into
`systemc.func`, the operation ordering is preserved verbatim. If any operation uses
a value defined later in the block, MLIR's verifier rejects the IR.

**Example failure**:
```mlir
hw.module @cycle(in %a: i32, out b: i32) {
  %y = comb.add %x, %a : i32   // Uses %x before it's defined
  %x = comb.mul %a, %a : i32   // Defines %x
  hw.output %y : i32
}
```

After `--convert-hw-to-systemc`, the `systemc.func` body contains `%y = ... %x ...`
before `%x = ...`, violating SSA dominance.

---

## 6.2 Solution: Topological Sort Pass

### 6.2.1 Pass Design

**Name**: `--linearize-graph-regions` (or integrate into `--convert-hw-to-systemc`)

**Algorithm**:
1. For each `hw.module` body block (before inlining into `systemc.func`):
   a. Build a DAG of operation dependencies based on SSA def-use chains.
   b. Perform topological sort (DFS post-order or Kahn's algorithm).
   c. Reorder operations in the block to match the topological order.
   d. **Cycle detection**: If a true combinational cycle exists (e.g., `%a = f(%b)`,
      `%b = g(%a)` with no register breaking the cycle), emit a diagnostic error.

2. Handle the `hw.output` terminator: it must remain the last operation in the block.

### 6.2.2 Cycle Handling

True combinational cycles are **illegal in synthesizable RTL**. If detected:
- Emit a clear error: `"combinational cycle detected between operations at <loc>"`
- Fail the pass gracefully (do not abort or crash)

> [!NOTE]
> In practice, CIRCT's canonical form should not contain true combinational cycles
> in well-formed hardware. However, the pass must handle them defensively.

### 6.2.3 Implementation Location Options

| Option | Pros | Cons |
|--------|------|------|
| **Standalone pass** `--linearize-graph-regions` | Reusable; testable independently | Extra pass invocation |
| **Inside `ConvertHWModule::matchAndRewrite`** | No extra pass; ordering is guaranteed | Harder to test in isolation |

> **Recommended**: Implement inside `ConvertHWModule::matchAndRewrite` (after
> `rewriter.inlineRegionBefore` and before the function body is used), with the
> topological sort as a helper function that can be unit-tested.

### 6.2.4 Implementation Sketch

```cpp
// In HWToSystemC.cpp, after inlining the HW body into systemc.func:
static LogicalResult linearizeBlock(Block &block) {
  // 1. Build adjacency: op → set of ops it depends on (operand defs)
  llvm::DenseMap<Operation*, llvm::SmallPtrSet<Operation*, 4>> deps;
  for (auto &op : block) {
    for (Value operand : op.getOperands()) {
      if (auto *defOp = operand.getDefiningOp()) {
        if (defOp->getBlock() == &block)
          deps[&op].insert(defOp);
      }
    }
  }

  // 2. Topological sort (Kahn's algorithm)
  SmallVector<Operation*> sorted;
  llvm::DenseMap<Operation*, unsigned> inDegree;
  // ... standard Kahn's algorithm ...

  // 3. Detect cycles
  if (sorted.size() != block.getOperations().size() - 1) // exclude terminator
    return failure(); // cycle detected

  // 4. Reorder: move each op to the end of block in sorted order
  for (auto *op : sorted)
    op->moveBefore(block.getTerminator());

  return success();
}
```

---

## 6.3 Testing

### Unit Test (FileCheck)
```mlir
// RUN: circt-opt --convert-hw-to-systemc %s | FileCheck %s

// Operations defined in "wrong" order — should be reordered
hw.module @reorder(in %a: i32, in %b: i32, out c: i32) {
  %sum = comb.add %prod, %a : i32   // Uses %prod before def
  %prod = comb.mul %a, %b : i32     // Defines %prod
  hw.output %sum : i32
}
// CHECK: systemc.func
// CHECK: comb.mul
// CHECK-NEXT: comb.add
```

### Negative Test (Cycle Detection)
```mlir
// RUN: circt-opt --convert-hw-to-systemc %s 2>&1 | FileCheck %s --check-prefix=ERR

hw.module @cycle(in %a: i32, out b: i32) {
  %x = comb.add %y, %a : i32
  %y = comb.mul %x, %a : i32   // true cycle: x → y → x
  hw.output %x : i32
}
// ERR: error: combinational cycle detected
```

---

## 6.4 Acceptance Criteria

- [ ] Out-of-order operations in `hw.module` graph regions are reordered correctly
- [ ] True combinational cycles produce clear error diagnostics
- [ ] The terminator (`hw.output`) remains at the end of the block
- [ ] Block arguments (module ports) are handled correctly (they have no defining op)
- [ ] All existing `HWToSystemC` tests continue to pass
- [ ] New FileCheck tests cover reordering and cycle detection
