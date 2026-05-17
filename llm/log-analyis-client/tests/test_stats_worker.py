import pytest
import os
from executors.stats import StatsExecutor

@pytest.fixture
def sample_log_file(tmp_path):
    """
    Creates a sample log file for testing.
    
    Rationale:
    Using pytest's tmp_path fixture ensures isolated, clean test environments
    that don't leave artifacts behind.
    """
    log_file = tmp_path / "test_stats.log"
    log_content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
    log_file.write_text(log_content)
    return str(log_file)

def test_stats_worker_get_stats(sample_log_file):
    """
    Verifies that get_stats correctly computes the line count and file size.
    """
    executor = StatsExecutor()
    
    result = executor.execute("get_stats", {"target_file": sample_log_file})
    
    assert result["status"] == "success"
    assert result["line_count"] == 5
    assert result["file_size_bytes"] > 0

def test_stats_worker_get_sample(sample_log_file):
    """
    Verifies that get_sample respects the limit parameter and returns
    the correct number of lines, even when the limit exceeds the file size.
    """
    executor = StatsExecutor(default_n=2)
    
    # Test default limit
    result_default = executor.execute("get_sample", {"target_file": sample_log_file})
    assert result_default["status"] == "success"
    assert result_default["returned_count"] == 2
    assert len(result_default["lines"]) == 2
    assert result_default["lines"] == ["Line 1", "Line 2"]
    
    # Test explicit limit smaller than file
    result_explicit = executor.execute("get_sample", {"target_file": sample_log_file, "limit": 3})
    assert result_explicit["returned_count"] == 3
    assert len(result_explicit["lines"]) == 3
    
    # Test limit greater than file size
    result_exceed = executor.execute("get_sample", {"target_file": sample_log_file, "limit": 100})
    assert result_exceed["returned_count"] == 5
    assert len(result_exceed["lines"]) == 5
