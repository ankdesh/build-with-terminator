# 11 — Tier 4: Complex Subsystem Tests

> **Prerequisite**: All prior lowering work (03–06), test framework (07).

---

## 11.1 Test Matrix

| # | Design | Category | Key Constructs | Complexity |
|---|--------|----------|---------------|------------|
| 1 | `sync_fifo_8x16` | Memory | 8-deep × 16-bit FIFO with full/empty flags | High |
| 2 | `simple_ram_32x8` | Memory | 32-entry × 8-bit single-port synchronous RAM | High |
| 3 | `dual_port_ram` | Memory | Dual-port RAM (1 read, 1 write port) | High |
| 4 | `accumulator` | Datapath | Registered accumulator with load/clear | Medium |
| 5 | `mac_unit` | Datapath | Multiply-accumulate: `acc += a * b` | Medium |
| 6 | `barrel_shifter` | Datapath | 32-bit combinational barrel shifter | Medium |
| 7 | `priority_encoder` | Control | 8-bit priority encoder | Medium |
| 8 | `arbiter_rr` | Control | 4-port round-robin arbiter | High |
| 9 | `uart_tx` | Interface | UART transmitter (shift register + baud counter) | High |
| 10 | `spi_master` | Interface | SPI master (shift reg + FSM + clock divider) | Very High |
| 11 | `pwm_generator` | Misc | PWM output with configurable duty cycle | Medium |
| 12 | `clock_divider` | Clock | Divide-by-N clock divider | Medium |
| 13 | `debouncer` | Misc | Switch debouncer (multi-cycle filter) | Medium |
| 14 | `crc_8bit` | Datapath | 8-bit CRC calculator (LFSR-based) | Medium |
| 15 | `gray_counter` | Datapath | Gray code counter with binary output | Medium |

---

## 11.2 Memory Design Patterns

### 11.2.1 Sync FIFO via `seq.hlmem` (if supported)

```mlir
// Ideal: use seq.hlmem
%mem = seq.hlmem @fifo_mem %clk, %rst : <16 x i8>
%rd = seq.read %mem[%rd_ptr] : <16 x i8>
seq.write %mem[%wr_ptr] %data, %wr_en, %clk : <16 x i8>
```

### 11.2.2 Sync FIFO via manual register array (fallback)

If `seq.hlmem` is not supported in Phase 2, implement FIFOs as:
- Array of `seq.compreg` (one per storage element)
- Read/write pointer registers
- Full/empty flag combinational logic

### 11.2.3 Expected SystemC for FIFO

```cpp
SC_MODULE(sync_fifo) {
  sc_in<bool> clk, rst;
  sc_in<bool> wr_en, rd_en;
  sc_in<sc_uint<16>> data_in;
  sc_out<sc_uint<16>> data_out;
  sc_out<bool> full, empty;

  sc_signal<sc_uint<16>> mem[8];  // Storage array
  sc_signal<sc_uint<4>> wr_ptr, rd_ptr;
  sc_signal<sc_uint<4>> count;
  // ...
};
```

---

## 11.3 Stimulus Strategy for Complex Designs

Complex designs need **protocol-aware stimulus** rather than pure random:

```python
# FIFO stimulus: interleave writes and reads
def generate_fifo_stimulus(depth: int, width: int, num_ops: int):
    """Generate write/read operations respecting FIFO protocol."""
    ops = []
    fill_level = 0
    for _ in range(num_ops):
        can_write = fill_level < depth
        can_read = fill_level > 0
        if can_write and (not can_read or random.random() > 0.5):
            ops.append({"wr_en": 1, "rd_en": 0, "data_in": random.randint(0, 2**width - 1)})
            fill_level += 1
        elif can_read:
            ops.append({"wr_en": 0, "rd_en": 1, "data_in": 0})
            fill_level -= 1
        else:
            ops.append({"wr_en": 0, "rd_en": 0, "data_in": 0})
    return ops
```

---

## 11.4 UART TX Protocol Verification

The UART TX test requires verifying the serial output bit timing:

```python
def verify_uart_tx(trace: list[dict], baud_divider: int):
    """Verify UART TX output follows 8N1 protocol."""
    # 1. Detect start bit (falling edge on tx)
    # 2. Sample data bits at baud rate intervals
    # 3. Verify stop bit is high
    # 4. Compare reconstructed byte to transmitted data
    ...
```

---

## 11.5 Acceptance Criteria

- [ ] Sync FIFO correctly stores/retrieves data without corruption
- [ ] RAM designs correctly read previously written data
- [ ] MAC unit accumulates correctly over 1000+ cycles
- [ ] Barrel shifter matches Verilator for all shift amounts
- [ ] Priority encoder outputs match for all input patterns
- [ ] Round-robin arbiter grants fairly across all ports
- [ ] UART TX serial output matches expected protocol timing
- [ ] CRC calculator matches reference CRC-8 implementation
- [ ] Gray counter output matches binary-to-gray conversion
