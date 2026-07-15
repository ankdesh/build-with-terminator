# SystemC TLM 2.0 Approximately-Timed (AT) Performance Models

This project implements four hardware performance modeling examples in C++ using the **SystemC TLM 2.0 Approximately-Timed (AT) 2-phase protocol** (`BEGIN_REQ` and `END_REQ`). These examples showcase timing-accurate transaction-level simulation of:

0. **Simple Pipeline Stage** (A ➡ B ➡ C basic 3-cycle pipeline stage modeling).
1. **Pipelined Computation** (3-cycle adder and 4-cycle multiplier ALU with in-order retirement).
2. **Interblock Streaming with Backpressure** (producer and consumer communicating via a fixed-sized FIFO interconnect using AXI-Stream model).
3. **Arbitration** (4 initiators contending for a shared switch using Round-Robin arbitration).

---

## Directory Structure

```text
systemc_at_with_tlm2_0/
├── CMakeLists.txt            # Root CMake file to configure all examples
├── README.md                 # Root documentation (this file)
├── GEMINI.md                 # Project constitution
├── systemc-src/              # Cloned SystemC source repository
├── systemc-dist/             # Local SystemC installation prefix
├── example0_simple/          # Example 0: Simple Pipeline Stage
│   ├── initiator_a.h         # Stimulus traffic source A
│   ├── pipeline_b.h          # 3-cycle pipelined stage B
│   ├── target_c.h            # Endpoint target C
│   ├── main.cpp              # Testbench
│   └── README.md             # Example-specific documentation
├── example1_pipeline/        # Example 1: Pipelined ALU
│   ├── initiator.h           # Traffic source
│   ├── alu_target.h          # Pipelined execution unit
│   ├── main.cpp              # Testbench
│   └── README.md             # Example-specific documentation
├── example2_backpressure/    # Example 2: FIFO-based Backpressure
│   ├── producer.h            # Bursty write generator
│   ├── consumer.h            # Target consumer
│   ├── fifo_target.h         # FIFO with streaming handshakes and stalls
│   ├── main.cpp              # Testbench
│   └── README.md             # Example-specific documentation
├── example3_arbitration/     # Example 3: Shared Switch Arbitration
│   ├── initiator.h           # Traffic generator
│   ├── target_node.h         # Destination memory endpoints
│   ├── switch_target.h       # Round-Robin arbitrated interconnect
│   ├── main.cpp              # Testbench
│   └── README.md             # Example-specific documentation
├── tests/
│   └── test_performance_models.py  # Automated integration test suite
└── .venv/                    # Local Python virtual environment for pytest
```

---

## Building the Project

### Prerequisites
Make sure you have `git`, `cmake`, `g++`, and `make` installed on your Linux system.

### Step 1: Compile SystemC Locally
The project contains a local build of SystemC 2.3.3 installed in `systemc-dist`:
```bash
git clone --depth 1 -b 2.3.3 https://github.com/accellera-official/systemc.git systemc-src
cd systemc-src
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$(pwd)/../../systemc-dist -DCMAKE_CXX_STANDARD=17 -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
make install
```

### Step 2: Build the Examples
Configure and build all example binaries using CMake:
```bash
cd /home/ankdesh/explore/build-with-terminator/arch/systemc_at_with_tlm2_0
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

This compiles four executables:
- `./example0_simple/example0_simple`
- `./example1_pipeline/example1_pipeline`
- `./example2_backpressure/example2_backpressure`
- `./example3_arbitration/example3_arbitration`

---

## Running the Examples & Generating Waveforms

### Run Individually
You can run each binary from the `build` directory, optionally passing a **scenario index** (`1`, `2`, or `3`) as an argument:
```bash
./example0_simple/example0_simple [scenario_index]
./example1_pipeline/example1_pipeline [scenario_index]
./example2_backpressure/example2_backpressure [scenario_index]
./example3_arbitration/example3_arbitration [scenario_index]
```
If no scenario is specified, it defaults to scenario `1`.

Running the binary performs the simulation and automatically writes a native **VCD (Value Change Dump) file** (e.g., `example0_sc1.vcd`) to your execution directory. You can open these VCD files directly in hardware waveform viewers like **GTKWave**.

### Run All Scenarios & Export Visualizer Data
To execute all examples across all three scenarios, parse their waveforms, and update the web visualizer's datasets automatically, run the Python utility script from the root directory:
```bash
.venv/bin/python run_scenarios.py
```

---

## Timeline & VCD Waveform Visualizer

To inspect transaction lifecycles and digital hardware signals interactively:
1. Open the [visualizer/index.html](file:///home/ankdesh/explore/build-with-terminator/arch/systemc_at_with_tlm2_0/visualizer/index.html) file in a web browser.
2. Select an example and scenario from the sidebar config panel.
3. Toggle between **Gantt Phases** (transaction lifecycles) and **Waveforms (VCD)** (digital signal timing transitions).
4. Use the playback scrubber/slider to step through cycles and view animated hardware component updates.

---

## Running the Integration Tests

An automated Python integration test suite is provided to verify the timing behavior and phase rules of all four examples. 

To run the tests:
```bash
.venv/bin/pytest tests/test_performance_models.py -v
```

The test runner will execute the compiled binaries, parse the trace timestamps, and assert that:
0. **Example 0** matches pipeline latency (3 cycles execution in B + 1 cycle in C = 5 cycles total path latency).
1. **ALU latency** (3 cycles for ADD, 4 cycles for MUL) and **in-order retirement** are preserved under 2-phase handshakes.
2. **Backpressure** stalls the Producer when the FIFO is full ($N \ge 4$), and resumes it when the Consumer drains it.
3. **Round-robin arbitration** fairly distributes latency and serialization among all 4 competing initiators.
