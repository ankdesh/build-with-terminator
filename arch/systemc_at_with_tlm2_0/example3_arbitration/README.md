# Example 3: Shared Switch Arbitration (Approximately-Timed TLM 2.0)

This example models a **Shared Communication Switch** connecting **4 Initiator IPs** to **4 Destination Target Nodes**. The switch acts as a shared resource that can only transmit one transaction at a time, arbitrating access using a **Round-Robin** scheduling policy.

---

## How Arbitration is Modeled in TLM 2.0 AT

When multiple initiators access a shared communication resource (such as a bus or switch crossbar) simultaneously, they contend for access. In a 2-phase Approximately-Timed (AT) performance model, this contention is modeled by delaying the request completion (`END_REQ`):

1. **Simultaneous Requests**:
   - At **cycle 1** (T = 10ns), all 4 initiators send a write transaction (`BEGIN_REQ`) directed to different destination target nodes.
   - The Switch Target receives all 4 requests. It records the transactions in a pending request list `m_pending_requests` and returns `TLM_ACCEPTED` to all of them.
   - Because no `END_REQ` is returned, all 4 initiators are **stalled** (waiting for their request phase to be released).

2. **Round-Robin Selection**:
   - The switch's arbiter thread (`arbiter_thread`) activates.
   - It selects the winning request based on the current Round-Robin index pointer `m_rr_index`.
   - Supposing `m_rr_index = 0`, **Initiator 0** wins.

3. **Grant and Transmission**:
   - The switch sends a backward call with phase `END_REQ` to **Initiator 0** (releasing its request phase stall and completing the initiator's handshake).
   - The switch forwards the request (`BEGIN_REQ`) to **Target Node 0**.
   - The switch marks itself as **busy** for 3 cycles (30ns) to model the transmission time.
   - The other 3 initiators remain stalled in their request phase.

4. **Sequential Processing**:
   - At **cycle 4** (T = 40ns), the switch transmission completes.
   - The switch frees itself and runs the arbiter on the remaining pending requests (1, 2, 3).
   - Since `m_rr_index` was updated to 1, **Initiator 1** is selected and granted access.
   - This process repeats until all requests are serviced, causing the destination target node transactions to complete at different cycles (**cycle 4**, **cycle 7**, **cycle 10**, and **cycle 13**), reflecting their arbitration latency penalties!

---

## Design and Code Structure

### 1. Multi-Socket Binding
The switch interconnect uses SystemC utility sockets designed for multiple connections:
- `tlm_utils::multi_passthrough_target_socket` (target side: receives from multiple initiators).
- `tlm_utils::multi_passthrough_initiator_socket` (initiator side: forwards to multiple target nodes).

### 2. Switch Interconnect Target (`switch_target.h`)
- Maintains a map `m_trans_to_init` mapping transaction pointers to their source initiator ID.
- **Payload Event Queue (`tlm_utils::peq_with_get`)**: Manages the 3-cycle switch transmission lock asynchronously. 
- When the transmission delay expires, the payload is retrieved from the PEQ, releasing the switch busy status and notifying the arbiter to process the remaining queued initiators.
