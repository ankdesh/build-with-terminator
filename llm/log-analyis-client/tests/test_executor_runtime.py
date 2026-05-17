import asyncio
import os
import sys

import pytest

# Ensure the build directory is in the path for tests
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "build"))


@pytest.fixture(scope="session")
def compiled_executor():
    try:
        import executor

        return executor
    except ImportError:
        pytest.fail("Executor extension not found in build directory. Run cmake and make first.")


@pytest.fixture
def log_file(tmp_path):
    """Creates a sample log file with known patterns."""
    path = tmp_path / "test.log"
    with open(path, "w") as f:
        for i in range(1000):
            if i % 100 == 0:
                f.write(f"Line {i}: [ERROR] Something went wrong\n")
            else:
                f.write(f"Line {i}: [INFO] Everything is fine\n")
    return str(path)


def test_parallel_scan_accuracy(compiled_executor, log_file):
    """Verifies that the parallel scanner finds the correct number of matches."""
    scanner = compiled_executor.Scanner(log_file)
    matches = scanner.scan("ERROR")

    # We wrote 10 lines with "ERROR" (0, 100, 200, ..., 900)
    assert len(matches) == 10

    # Verify the content of the first match
    first_match = matches[0]
    data = scanner.get_data(first_match.offset, first_match.length)
    assert b"Line 0: [ERROR]" in bytes(data)


def test_zero_copy_memoryview(compiled_executor, log_file):
    """Verifies that get_data returns a functional memoryview."""
    scanner = compiled_executor.Scanner(log_file)
    matches = scanner.scan("Line 100:")
    assert len(matches) == 1

    match = matches[0]
    mview = scanner.get_data(match.offset, match.length)

    assert isinstance(mview, memoryview)
    content = bytes(mview).decode("utf-8").strip()
    assert content == "Line 100: [ERROR] Something went wrong"


def test_global_memory_manager_sharing(compiled_executor, log_file):
    """Verifies that multiple scanners can use the same file via GMM."""
    scanner1 = compiled_executor.Scanner(log_file)
    scanner2 = compiled_executor.Scanner(log_file)

    matches1 = scanner1.scan("ERROR")
    matches2 = scanner2.scan("ERROR")

    assert len(matches1) == len(matches2)
    assert matches1[0].offset == matches2[0].offset


@pytest.mark.asyncio
async def test_cancellation(compiled_executor, tmp_path):
    """Verifies that a long-running scan can be interrupted."""
    # Create a larger file to ensure the scan takes some detectable time
    massive_log = tmp_path / "massive.log"
    with open(massive_log, "w") as f:  # noqa: ASYNC230
        for i in range(500000):
            f.write(f"Line {i} some random filler text for the scanner to churn through\n")

    scanner = compiled_executor.Scanner(str(massive_log))

    loop = asyncio.get_running_loop()
    # Run in executor to simulate async environment
    scan_task = loop.run_in_executor(None, scanner.scan, "PATTERN_THAT_WILL_NOT_BE_FOUND")

    # Small sleep to let the scan start
    await asyncio.sleep(0.01)

    scanner.cancel()

    results = await scan_task
    # If cancelled, it should return 0 results
    assert len(results) == 0


def test_invalid_path(compiled_executor):
    """Verifies that an invalid path raises a runtime error."""
    with pytest.raises(RuntimeError):
        compiled_executor.Scanner("/path/to/non/existent/file")
