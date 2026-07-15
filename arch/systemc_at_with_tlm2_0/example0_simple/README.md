# Example 0: Simple Pipeline Stage (Approximately-Timed TLM 2.0)

This example models a basic 3-component processing pipeline:
`Component A (Initiator)` ➡ `Component B (Pipelined Stage)` ➡ `Component C (Target Endpoint)`

Component B performs a fixed 3-cycle pipelined processing operation before forwarding the transaction to Component C.

---

## Architecture and Handshake Flow

1. **`BEGIN_REQ` (A ➡ B)**: Component A initiates a transaction. B receives it, registers it in its internal processing queue, and returns `END_REQ` after 1 cycle register delay to release A's socket.
2. **Pipelined Execution (B)**: B enqueues the transaction in a Payload Event Queue (`tlm_utils::peq_with_get`) with a 3-cycle delay. B's pipeline can hold multiple transactions in flight simultaneously.
3. **Forwarding (B ➡ C)**: When the PEQ delay expires, B pops the transaction and initiates a forward transaction to Component C (`BEGIN_REQ`).
4. **Endpoint Processing (C)**: C receives the request, returns `END_REQ` after 1 cycle, and schedules a completion event in its PEQ after a 1-cycle processing delay.

```
Component A                  Component B (3 cy)               Component C (1 cy)
     |                               |                                |
     | --- nb_transport_fw(REQ) ---> | (Pushed to PEQ)                |
     | <--- returns END_REQ (1 cy) - |                                |
     |                               |                                |
     |                               |          === PEQ Latency ===   | (3 cycles)
     |                               |                                |
     |                               | --- nb_transport_fw(REQ) ----> |
     |                               | <--- returns END_REQ (1 cy) -- |
     v                               v                                v
```

---

## Scenarios

### 1. Scenario 1: Single Transaction
- A single transaction is sent at cycle 1.
- Completes request phase at cycle 2.
- Finishes execution in B and is forwarded to C at cycle 4.
- C completes and retires transaction at cycle 6 (total latency: 5 cycles).

### 2. Scenario 2: Back-to-Back 5 Requests
- 5 transactions are sent on consecutive cycles (cycles 1, 2, 3, 4, 5).
- Since B returns `END_REQ` after 1 cycle, A's request socket is released in time for the next transaction.
- B's PEQ holds multiple overlapping transactions in flight.
- Target C completes and retires transactions consecutively at cycles 6, 7, 8, 9, 10.

### 3. Scenario 3: Alternate Cycles
- 3 transactions are sent on alternate cycles (cycles 1, 3, 5).
- Shows B's pipeline occupancy filling and draining dynamically.
