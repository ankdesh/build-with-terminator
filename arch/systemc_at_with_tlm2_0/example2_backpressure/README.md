# Example 2: Interblock FIFO with Backpressure (Approximately-Timed TLM 2.0)

This example models a **Producer** and a **Consumer** IP communicating via a fixed-capacity **FIFO Interconnect Target** (capacity = 4) in a streaming push pipeline:
`Producer (Initiator)` ➡ `FIFO Interconnect (Target/Initiator)` ➡ `Consumer (Target)`

The system demonstrates transaction-level flow control (backpressure) using a pure 2-phase handshake protocol.

---

## How Backpressure is Modeled in TLM 2.0 AT

In TLM 2.0, the initiator is prohibited from starting a new transaction on a socket until the active request phase of the current transaction has finished. The request phase is considered active from `BEGIN_REQ` until `END_REQ` is received by the initiator.

This rule provides a natural way to model backpressure in a 2-phase system:

1. **Under Normal Operation (FIFO size < Capacity)**:
   - Producer sends `BEGIN_REQ` to FIFO.
   - FIFO target accepts the write, pushes the data to its PEQ buffer (2 cycles latency), and returns `TLM_UPDATED` with `END_REQ` (after 1 cycle).
   - The producer receives `END_REQ` immediately, completing the request phase. It is free to start another transaction in the next cycle.

2. **Under Backpressure (FIFO is FULL)**:
   - Producer sends `BEGIN_REQ` to FIFO.
   - FIFO detects that the buffer is full. It returns `TLM_ACCEPTED` and does **NOT** return `END_REQ`.
   - The producer's request phase remains active. The producer is **stalled** (blocked in its internal thread waiting for `END_REQ`).
   - The transaction is placed in the FIFO's `m_pending_writes` queue.

3. **Stall Release (Consumer Drains)**:
   - When the Consumer completes processing a value, it releases its socket.
   - The FIFO interconnect target pops a stalled write from `m_pending_writes`, pushes it into the FIFO buffer, and sends a backward call to the producer socket with phase `END_REQ` (releasing the producer's stall).

---

## Design and Code Structure

### 1. Producer (`producer.h`)
- Generates a burst of 6 writes starting at **cycle 1** (T = 10ns).
- Uses `wait(m_end_req_event)` to block its thread if the target does not return `END_REQ` immediately.

### 2. Consumer (`consumer.h`)
- Acts as a Target block.
- Models a processing busy status. If busy, it returns `TLM_ACCEPTED` to the FIFO to stall the incoming write stream.
- In Scenario 1, starts processing at **cycle 10** (T = 100ns), demonstrating the FIFO buffer filling up and backpressuring the Producer.

### 3. FIFO Interconnect (`fifo_target.h`)
- Contains two sockets: target `write_socket` and initiator `read_socket`.
- Manages an internal `m_fifo_data` queue and queues for pending/stalled writes.
- Uses `m_peq` to model 2-cycle write buffer execution delay.
- Initiates writes to the Consumer, managing stalls if the Consumer is busy.
