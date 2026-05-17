import pytest

from orchestrator import Orchestrator


async def python_aggregation_tool(scanner, results):
    """
    A mock Python tool that demonstrates zero-copy access to the GMM-mapped memory.
    It takes raw offsets from C++ and reads the data directly via memoryview.
    """
    print(f"\n[Python Tool] Starting aggregation of {len(results)} matches...")

    limit = 5
    aggregated_data = []

    for i, match in enumerate(results[:limit]):
        # ZERO-COPY ACCESS:
        mview = scanner.get_data(match.offset, match.length)
        line_text = bytes(mview).decode("utf-8", errors="ignore").strip()
        aggregated_data.append(line_text)
        print(f"  [Aggregator] Processed line {i + 1}: {line_text[:60]}...")

    return {"status": "success", "processed_count": min(len(results), limit), "total_available": len(results)}


@pytest.fixture
def test_log_file(tmp_path):
    """Creates a dummy log file to verify parallel scanning."""
    log_file = tmp_path / "large_test.log"
    print(f"[*] Generating test log: {log_file}...")

    with open(log_file, "w") as f:
        for i in range(50000):
            if i % 5000 == 0:
                f.write(f"TIMESTAMP-{i} [ERROR] Critical failure in subsystem {i // 5000}\n")
            elif i % 1000 == 0:
                f.write(f"TIMESTAMP-{i} [WARN] Unusual latency detected\n")
            else:
                f.write(f"TIMESTAMP-{i} [INFO] System heartbeat healthy\n")

    return str(log_file)


@pytest.mark.asyncio
async def test_orchestrator_workflow(test_log_file):
    """
    Verifies that the orchestrator can start, process an instruction queue,
    and cleanly shut down.
    """
    orchestrator = Orchestrator(test_log_file)
    await orchestrator.start()

    # 1. Send instruction to C++ scanner executor
    print("[Agent] Sending instruction: SCAN for 'ERROR' on C++ executor")
    await orchestrator.send_instruction({"action": "scan", "executor": "scanner", "pattern": "ERROR"})

    # Wait for the scan to finish
    await orchestrator.wait_until_idle()

    # 2. Simulate the python aggregation tool using the orchestrator's results
    # (Since the aggregate action is not a standard executor, we call the mock tool directly in this test)
    if orchestrator.last_results:
        scanner_executor = orchestrator.executors.get("scanner")
        if scanner_executor:
            agg_result = await python_aggregation_tool(scanner_executor.scanner, orchestrator.last_results)
            assert agg_result["status"] == "success"
            assert agg_result["total_available"] > 0
    else:
        pytest.fail("Orchestrator scan did not yield last_results")

    await orchestrator.stop()
