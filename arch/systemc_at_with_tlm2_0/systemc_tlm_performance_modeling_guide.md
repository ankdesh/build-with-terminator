# SystemC TLM 2.0 AT Performance Modeling Guide & Hardware Specs

This document outlines the architectural patterns, rules, and idioms required to construct cycle-accurate performance models using the **SystemC TLM 2.0 2-Phase Approximately-Timed (AT) protocol**. 

It is divided into two sections:
1. **Modeling Guide**: Instructions and design rules for building AT components.
2. **Hardware Specifications**: Textual specs for Examples 0, 1, 2, and 3.

---

# SECTION 1: Performance Modeling Guide

To build a SystemC performance model that matches our timing and design style, follow these guidelines:

## 1. Handshake Protocol (2-Phase AT)
Use only the **2-phase Approximately-Timed (AT) protocol** using `nb_transport_fw` and `nb_transport_bw`:
- **Phase `BEGIN_REQ`**: Sent forward by the initiator to start a transaction.
- **Phase `END_REQ`**: Sent backward (or returned as a direct update) by the target to acknowledge request receipt. This completes the handshake and frees the interface socket.
- **No Response Phase**: Do not use `BEGIN_RESP` or `END_RESP` phases. The lifecycle ends immediately when the request phase closes.

## 2. Modeling Execution Latency
Do not use `sc_core::wait()` to model target block processing delays. Instead, use a **Payload Event Queue (PEQ)**:
- Include `#include <tlm_utils/peq_with_get.h>`
- Instantiate a PEQ: `tlm_utils::peq_with_get<tlm::tlm_generic_payload> m_peq{"peq"};`
- Register the incoming payload with a delay: `m_peq.notify(trans, delay + LATENCY);`
- Run an `SC_THREAD` that blocks on `wait(m_peq.get_event())` and processes expired transactions in order:
  ```cpp
  void worker_thread() {
      while (true) {
          wait(m_peq.get_event());
          tlm::tlm_generic_payload* trans;
          while ((trans = m_peq.get_next_transaction())) {
              // Perform computation and retire transaction here
          }
      }
  }
  ```

## 3. Modeling Flow Control & Backpressure
Stall the initiator when internal buffers (like FIFOs or pipeline stages) are full:
- **Stall Initiation**:
  - In `nb_transport_fw(trans, phase == BEGIN_REQ, delay)`:
  - If the buffer is full, do **NOT** update the phase to `END_REQ`.
  - Return `tlm::TLM_ACCEPTED`.
  - The initiator checks if the handshake completed. If not, it stalls its stimulus thread by blocking on a local event: `wait(m_end_req_event);`
  - Stash the transaction pointer in a pending queue: `m_pending_writes.push(&trans);`
- **Stall Release**:
  - When buffer space becomes available (e.g. consumer consumes an item):
  - Pop the oldest transaction from `m_pending_writes`.
  - Call the initiator's backward path: `socket->nb_transport_bw(*trans, phase = END_REQ, delay = 1_cycle);`
  - In the initiator's backward callback, notify the wait event: `m_end_req_event.notify(delay);`
  - The initiator unblocks and is free to send the next request.

## 4. Modeling Shared Resource Contention (Arbitration)
- Use multiple socket arrays or `tlm_utils::multi_passthrough_target_socket` to bind multiple initiators to a shared switch.
- When multiple requests arrive at the same cycle:
  - Capture all requests in a vector of pending requests.
  - Return `TLM_ACCEPTED` to stall all initiators.
  - In an arbiter thread, select a winner using **Round-Robin** scheduling.
  - Release the winner backward: send `nb_transport_bw(END_REQ)` to the winner.
  - Lock the switch for $D$ cycles using a PEQ. During this lock period, the switch is busy and cannot grant other requests.
  - Once the switch PEQ expires, unlock the switch and trigger the arbiter to process the remaining pending requests.

## 5. Cycle-Based Logging & VCD Tracing
- All log traces must output cycle counts:
  ```cpp
  inline int get_cycle() {
      return static_cast<int>(sc_core::sc_time_stamp() / sc_core::sc_time(10, sc_core::SC_NS) + 0.5);
  }
  #define CYC_LOG() "[CYCLE: " << get_cycle() << "] "
  ```
- Expose VCD tracing signals for queue occupancy, stalls, and interface transaction IDs (using `1-indexed` transaction IDs where `0` represents IDLE/NONE). For example, `sig_A_B_req_tx` traces active handshakes.

---

# SECTION 2: Textual Hardware Specifications

The following specs describe the hardware behavior of the four performance models. 

---

## Example 0: Simple Pipeline Stage

### Hardware Structure
- **Component A**: Stimulus generator (Initiator).
- **Component B**: 3-cycle pipelined stage (Target on input, Initiator on output).
- **Component C**: 1-cycle target endpoint (Target).

### Timing & Handshake Specifications
- **A-B Handshake**: Component A sends a transaction to Component B. Component B returns `END_REQ` after a 1-cycle register delay, allowing A to send a new transaction in the next cycle.
- **Component B Execution**: Component B models a 3-cycle pipelined processing latency using a PEQ. Multiple transactions can overlap in B's pipeline simultaneously.
- **B-C Handshake**: Once B's execution completes, B initiates a write transaction to Component C. Component C accepts it and returns `END_REQ` after a 1-cycle register delay.
- **Component C Execution**: Component C models a 1-cycle processing delay in its PEQ, doubles the data payload value, and retires.
- **Total Path Latency**: A transaction sent at cycle $T$ completes execution and retires in C at cycle $T + 5$ (1 cycle register delay in B + 3 cycles pipeline delay in B + 1 cycle endpoint processing delay in C).

### VCD Tracing
- `pipeline_depth`: Number of active transactions inside B.
- `A_B_req_tx`: Transaction ID currently active on the A-B request interface (active for 1 cycle).
- `B_C_req_tx`: Transaction ID currently active on the B-C request interface (active for 1 cycle).

---

## Example 1: Pipelined ALU

### Hardware Structure
- **CPU**: Stimulus generator (Initiator).
- **ALU**: Pipelined processing unit (Target).

### Timing & Handshake Specifications
- **Interface Handshake**: CPU sends operation requests to ALU. ALU returns `END_REQ` after a 1-cycle register delay, freeing the CPU to issue subsequent operations back-to-back.
- **ALU Latency**:
  - **ADD Operation**: 3 cycles execution latency.
  - **MUL Operation**: 4 cycles execution latency.
- **In-Order Retirement**: ALU contains an internal reorder buffer. Transactions must complete and retire in the strict order they were received. If a fast 3-cycle ADD finishes calculation *after* a slow 4-cycle MUL that was issued before it, the ADD must wait and retire in the same cycle as the MUL.
- **Data Output**: Upon retirement, the ALU performs the mathematical operation (ADD or MUL) and prints the result value.

### VCD Tracing
- `input_stage_occupied`: Active when a new request is being accepted (1 cycle duration).
- `pipeline_depth`: Number of operations currently active in the ALU pipeline.
- `active_op`: Current operating state of the pipeline (0 = IDLE, 1 = ADD, 2 = MUL, 3 = MIXED).
- `retired_tx_id`: ID of the transaction retired in the current cycle.

---

## Example 2: FIFO Backpressure Streaming

### Hardware Structure
- **Producer**: Bursty writer (Initiator).
- **FIFO Interconnect**: Fixed-capacity queue (Target on write, Initiator on read).
- **Consumer**: Endpoint block with variable processing speeds (Target).

### Timing & Handshake Specifications
- **Producer-FIFO Handshake**: Producer writes data packets to FIFO.
  - If FIFO has space (size < 4): FIFO returns `END_REQ` after a 1-cycle register delay.
  - If FIFO is full (size == 4): FIFO holds `END_REQ`, stalling the Producer until space is freed.
- **FIFO Latency**: FIFO models a 2-cycle write buffer processing delay in its PEQ before placing the item into its storage queue.
- **FIFO-Consumer Handshake**: FIFO acts as an initiator and pushes popped data packets to the Consumer.
  - If Consumer is ready: Consumer returns `END_REQ` after a 1-cycle register delay.
  - If Consumer is busy: Consumer holds `END_REQ`, stalling the FIFO from popping.
- **Consumer Latency**: Consumer models processing delays:
  - **Fast Consumer**: 1 cycle processing delay.
  - **Slow Consumer**: 2 cycles processing delay.
- **Backpressure Cascade**: When the Consumer is busy, the Consumer stalls the FIFO. The FIFO buffer fills up. Once FIFO capacity reaches 4, the FIFO stalls the Producer.

### VCD Tracing
- `fifo_size`: Number of items currently stored in the FIFO queue.
- `producer_stalled`: Active when the Producer is stalled due to a full FIFO.
- `consumer_stalled`: Active when the FIFO is stalled because the Consumer is busy.

---

## Example 3: Shared Switch Arbitration

### Hardware Structure
- **4 Initiators (IP 0 to 3)**: Generate contending write traffic directed to target nodes.
- **SwitchTarget**: shared crossbar switch (Target on ports 0..3, Initiator on ports 0..3).
- **4 Target Nodes (Node 0 to 3)**: Destination endpoints.

### Timing & Handshake Specifications
- **Contention & Stalling**: If multiple initiators issue requests simultaneously, the Switch Target accepts all of them, stores them in an arbitration list, and holds `END_REQ` on all ports. All initiators stall.
- **Round-Robin Arbiter**:
  - The Switch arbitrates between pending requests using Round-Robin scheduling.
  - The arbiter selects the winning initiator and returns `END_REQ` backward to release its stall.
  - The switch forwards the request (`BEGIN_REQ`) to the winner's destination Target Node.
  - Target Node accepts the request and returns `END_REQ` after a 1-cycle register delay.
- **Switch Transmission Delay**: The switch locks itself and remains busy for 3 cycles (30ns) to model transmission serialization. During this time, the arbiter is paused, and other contending initiators remain stalled.
- **Node Execution**: Target nodes process requests with a 1-cycle endpoint latency.

### VCD Tracing
- `switch_busy`: Active when the switch is transmitting a transaction (3 cycles duration per grant).
- `switch_rr_index`: Current Round-Robin pointer (0 to 3).
- `active_initiator_id`: ID of the initiator currently granted switch access (0 = NONE, 1 = IP 0, 2 = IP 1, etc.).
- `pending_req_count`: Number of initiators currently queued and stalled in the switch.
