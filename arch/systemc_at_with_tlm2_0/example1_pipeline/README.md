# Example 1: Pipelined ALU (Approximately-Timed TLM 2.0)

This example models a pipelined Arithmetic Logic Unit (ALU) that supports two types of operations with different execution latencies:
- **3-Cycle Adder**
- **4-Cycle Multiplier**

The system enforces **in-order retirement** (transactions must complete and retire in the order they were scheduled).

---

## How Approximately-Timed (AT) TLM 2.0 is Used

Approximately-Timed modeling uses the **2-phase protocol** to model detailed timing phases and interface contention:

1. **`BEGIN_REQ` (Forward Path)**: The Initiator (CPU) initiates the transaction and starts the request phase. It passes a generic payload pointing to the operands.
2. **`END_REQ` (Forward Return / Backward Path)**: The Target (ALU) receives the request and, after 1 cycle of input register delay, sends `END_REQ` back to the initiator. This completes the request phase, allowing the initiator to reuse the socket for a new transaction in the next cycle.

```
Initiator (CPU)                          Target (ALU)
      |                                        |
      | ----- nb_transport_fw(BEGIN_REQ) ----> | (Starts execution)
      | <---- nb_transport_fw returns END_REQ  | (Input buffer free after 1 cycle)
      |                                        |
      |          === ALU Execution ===         | (ADD = 3 cycles, MUL = 4 cycles)
      v                                        v
```

---

## Design and Code Structure

### 1. Initiator (`initiator.h`)
- Implements the stimulus thread generating transactions.
- Enforces the TLM 2.0 rule that no new transaction can be issued while a request phase is in progress (i.e. between `BEGIN_REQ` and `END_REQ`).
- Standardized logs output the current simulation time in cycle counts `[CYCLE: X]` (where 1 cycle = 10ns).

### 2. Target ALU (`alu_target.h`)
- Implements `nb_transport_fw` to accept incoming `BEGIN_REQ` phase.
- **Payload Event Queue (`tlm_utils::peq_with_get`)**: Manages out-of-order execution timing asynchronously.
- **In-Order Retirement Logic**:
  - The pipeline thread (`pipeline_thread`) blocks on `m_peq.get_event()`.
  - When the execution delay of a transaction expires, it is retrieved from the PEQ and marked as `completed`.
  - A strict retirement queue (`m_pipeline_queue`) monitors the head. Only *after* the oldest transaction is completed can subsequent completed transactions retire, enforcing in-order retirement. No backward response calls are executed.

---

## Verification Trace Details

During simulation runs (Scenario 1), the cycle-based log shows:
1. **Tx 0 (ADD)** is issued at **cycle 1**. Its request completes (`END_REQ`) at **cycle 2**. It finishes execution and retires at **cycle 4** (cycle 1 + 3 cycles latency).
2. **Tx 1 (MUL)** is issued at **cycle 2** (as soon as the ALU input stage is free). Its request completes at **cycle 3**. It completes execution and retires at **cycle 6** (cycle 2 + 4 cycles latency).
3. **Tx 2 (ADD)** is issued at **cycle 3**. Its request completes at **cycle 4**. Its calculation finishes at **cycle 6** (cycle 3 + 3 cycles latency).
4. Both Tx 1 (MUL) and Tx 2 (ADD) retire at **cycle 6**. Tx 1 (MUL) retires first because it entered first, followed immediately by Tx 2 (ADD). This confirms correct in-order retirement.
