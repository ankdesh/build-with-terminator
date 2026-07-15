import subprocess
import re
import os
import pytest

# Paths to the compiled binaries
BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")
EXAMPLE0_BIN = os.path.join(BUILD_DIR, "example0_simple", "example0_simple")
EXAMPLE1_BIN = os.path.join(BUILD_DIR, "example1_pipeline", "example1_pipeline")
EXAMPLE2_BIN = os.path.join(BUILD_DIR, "example2_backpressure", "example2_backpressure")
EXAMPLE3_BIN = os.path.join(BUILD_DIR, "example3_arbitration", "example3_arbitration")

def run_binary(binary_path, args=None):
    assert os.path.exists(binary_path), f"Binary {binary_path} does not exist. Did you compile the project?"
    cmd = [binary_path]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return result.stdout

def test_example1_pipeline():
    """
    Verifies the timing and correct in-order retirement of the Pipelined ALU (2-phase).
    - Tx 0 (ADD) at cycle 1 finishes at cycle 4 (3 cycles delay)
    - Tx 1 (MUL) at cycle 2 finishes at cycle 6 (4 cycles delay)
    - Tx 2 (ADD) at cycle 3 finishes at cycle 6 (3 cycles delay). Must retire in-order.
    """
    output = run_binary(EXAMPLE1_BIN)
    print(output)
    
    # Assertions on Tx 0 (first ADD)
    assert "[CYCLE: 1] [INITIATOR] Sending BEGIN_REQ for Tx 0 (ADD 10, 20)" in output
    assert "[CYCLE: 4] [TARGET] Tx 0 completed (computation retired). Result: 30" in output

    # Assertions on Tx 1 (MUL)
    assert "[CYCLE: 2] [INITIATOR] Sending BEGIN_REQ for Tx 1 (MUL 5, 6)" in output
    assert "[CYCLE: 6] [TARGET] Tx 1 completed (computation retired). Result: 30" in output

    # Assertions on Tx 2 (second ADD)
    assert "[CYCLE: 3] [INITIATOR] Sending BEGIN_REQ for Tx 0 (ADD 30, 40)" in output
    # Even though Tx 2 (ADD) completes calculation at cycle 6, it must not retire until Tx 1 (MUL) retires at cycle 6.
    assert "[CYCLE: 6] [TARGET] Tx 1 completed (computation retired). Result: 30" in output
    assert "[CYCLE: 6] [TARGET] Tx 0 completed (computation retired). Result: 70" in output
    
    # Verify final transaction (MUL at cycle 11)
    assert "[CYCLE: 11] [INITIATOR] Sending BEGIN_REQ for Tx 1 (MUL 7, 8)" in output
    assert "[CYCLE: 15] [TARGET] Tx 1 completed (computation retired). Result: 56" in output

def test_example2_backpressure():
    """
    Verifies that the FIFO (capacity 4) correctly triggers backpressure stalls (2-phase).
    - First 5 writes (cycles 1, 2, 3, 4, 5) are accepted immediately.
    - Write 6 (cycle 6) is stalled due to full FIFO.
    - At cycle 10, slow consumer starts processing.
    - The FIFO pops an item, freeing space, which triggers release of stalled Write 6.
    - Write 6 request phase completes (END_REQ) at cycle 11.
    """
    output = run_binary(EXAMPLE2_BIN)
    print(output)

    # Check that Write 1-5 are sent and accepted
    assert "[CYCLE: 1] [PRODUCER] Sending write BEGIN_REQ (Tx 1) with value: 101" in output
    assert "[CYCLE: 2] [PRODUCER] Direct update: phase END_REQ for Tx 1." in output
    assert "[CYCLE: 2] [PRODUCER] Sending write BEGIN_REQ (Tx 2) with value: 102" in output
    assert "[CYCLE: 3] [PRODUCER] Sending write BEGIN_REQ (Tx 3) with value: 103" in output
    assert "[CYCLE: 4] [PRODUCER] Sending write BEGIN_REQ (Tx 4) with value: 104" in output
    assert "[CYCLE: 5] [PRODUCER] Sending write BEGIN_REQ (Tx 5) with value: 105" in output

    # Check that Write 6 is stalled at cycle 6
    assert "[CYCLE: 6] [PRODUCER] Sending write BEGIN_REQ (Tx 6) with value: 106" in output
    assert "[CYCLE: 6] [FIFO] Write request BEGIN_REQ received. Size: 4/4" in output
    assert "[CYCLE: 6] [FIFO] FIFO FULL! Stall write request." in output
    assert "[CYCLE: 6] [PRODUCER] Stalling on Tx 6 due to backpressure..." in output

    # Check that Consumer starts processing at cycle 10
    assert "[CYCLE: 10] [CONSUMER] Starting slow consumer processing (draining FIFO)..." in output
    assert "[CYCLE: 11] [FIFO] Consumer accepted write request." in output

    # Check that Write 6 is released after the pop (cycle 10 release)
    assert "[CYCLE: 10] [FIFO] [STALL RELEASE] Accepting pending write (FIFO size: 4)" in output
    assert "[CYCLE: 11] [PRODUCER] Received END_REQ for write transaction 6" in output
    assert "[CYCLE: 11] [PRODUCER] Stall released for Tx 6." in output

def test_example3_arbitration():
    """
    Verifies that simultaneous requests at cycle 1 are arbitrated using Round-Robin (2-phase).
    - Initiator 0 is granted immediately (grant at cycle 1, completes request phase END_REQ at cycle 2).
    - Initiator 1 is granted at cycle 4 (completes request phase at cycle 5).
    - Initiator 2 is granted at cycle 7 (completes request phase at cycle 8).
    - Initiator 3 is granted at cycle 10 (completes request phase at cycle 11).
    """
    output = run_binary(EXAMPLE3_BIN)
    print(output)

    # Check coordinated launch at cycle 1
    assert "[CYCLE: 1] [INITIATOR_0] Sending BEGIN_REQ to target 0." in output
    assert "[CYCLE: 1] [INITIATOR_1] Sending BEGIN_REQ to target 1." in output
    assert "[CYCLE: 1] [INITIATOR_2] Sending BEGIN_REQ to target 2." in output
    assert "[CYCLE: 1] [INITIATOR_3] Sending BEGIN_REQ to target 3." in output

    # Check Round-Robin grant sequence and timing
    
    # 1. Initiator 0 grant
    assert "[CYCLE: 1] [SWITCH] Arbiter GRANTED access to Initiator 0 (next RR: 1)" in output
    assert "[CYCLE: 2] [INITIATOR_0] Received END_REQ (arbitration grant, switch busy phase starts)." in output

    # 2. Initiator 1 grant
    assert "[CYCLE: 4] [SWITCH] Arbiter GRANTED access to Initiator 1 (next RR: 2)" in output
    assert "[CYCLE: 5] [INITIATOR_1] Received END_REQ (arbitration grant, switch busy phase starts)." in output

    # 3. Initiator 2 grant
    assert "[CYCLE: 7] [SWITCH] Arbiter GRANTED access to Initiator 2 (next RR: 3)" in output
    assert "[CYCLE: 8] [INITIATOR_2] Received END_REQ (arbitration grant, switch busy phase starts)." in output

    # 4. Initiator 3 grant
    assert "[CYCLE: 10] [SWITCH] Arbiter GRANTED access to Initiator 3 (next RR: 0)" in output
    assert "[CYCLE: 11] [INITIATOR_3] Received END_REQ (arbitration grant, switch busy phase starts)." in output

def test_example0_simple():
    """
    Verifies Example 0 (Simple Pipeline Stage A -> B -> C - 2-phase):
    - B models 3 cycles of execution delay via PEQ.
    - C models 1 cycle of endpoint processing via PEQ.
    - Total path latency: 5 cycles (starts at cycle 1, finishes at cycle 6).
    """
    # 1. Scenario 1: Single Transaction
    out1 = run_binary(EXAMPLE0_BIN)
    assert "[CYCLE: 1] [INITIATOR_A] Sending BEGIN_REQ for Tx 0 with value: 100" in out1
    assert "[CYCLE: 4] [PIPELINE_B] Execution complete for Tx 0, forwarding request to Component C." in out1
    assert "[CYCLE: 6] [TARGET_C] Tx 0 completed (computation retired). Result: 200" in out1

    # 2. Scenario 2: Back-to-back 5 requests, one each cycle
    out2 = run_binary(EXAMPLE0_BIN, ["2"])
    
    assert "[CYCLE: 1] [INITIATOR_A] Sending BEGIN_REQ for Tx 0" in out2
    assert "[CYCLE: 2] [INITIATOR_A] Sending BEGIN_REQ for Tx 1" in out2
    assert "[CYCLE: 3] [INITIATOR_A] Sending BEGIN_REQ for Tx 2" in out2
    assert "[CYCLE: 4] [INITIATOR_A] Sending BEGIN_REQ for Tx 3" in out2
    assert "[CYCLE: 5] [INITIATOR_A] Sending BEGIN_REQ for Tx 4" in out2
    
    # Check pipeline completions
    assert "[CYCLE: 6] [TARGET_C] Tx 0 completed (computation retired). Result: 200" in out2
    assert "[CYCLE: 7] [TARGET_C] Tx 1 completed (computation retired). Result: 202" in out2
    assert "[CYCLE: 8] [TARGET_C] Tx 2 completed (computation retired). Result: 204" in out2
    assert "[CYCLE: 9] [TARGET_C] Tx 3 completed (computation retired). Result: 206" in out2
    assert "[CYCLE: 10] [TARGET_C] Tx 4 completed (computation retired). Result: 208" in out2

    # 3. Scenario 3: 3 requests on alternate cycles (cycles 1, 3, 5)
    out3 = run_binary(EXAMPLE0_BIN, ["3"])
    
    assert "[CYCLE: 1] [INITIATOR_A] Sending BEGIN_REQ for Tx 0" in out3
    assert "[CYCLE: 3] [INITIATOR_A] Sending BEGIN_REQ for Tx 1" in out3
    assert "[CYCLE: 5] [INITIATOR_A] Sending BEGIN_REQ for Tx 2" in out3
    
    assert "[CYCLE: 6] [TARGET_C] Tx 0 completed (computation retired). Result: 200" in out3
    assert "[CYCLE: 8] [TARGET_C] Tx 1 completed (computation retired). Result: 202" in out3
    assert "[CYCLE: 10] [TARGET_C] Tx 2 completed (computation retired). Result: 204" in out3
