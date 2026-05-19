import os

from executors.template_extractor import TemplateExtractorExecutor


def test_template_extractor_executor(tmp_path):
    # Create dummy log file
    log_file = tmp_path / "test.log"
    log_content = """2026-05-06 10:00:00 INFO User 123 logged in
2026-05-06 10:01:00 ERROR Connection failed to 192.168.1.1
2026-05-06 10:02:00 ERROR Connection failed to 10.0.0.1
"""
    log_file.write_text(log_content)

    executor = TemplateExtractorExecutor()
    # Mock the out dir to tmp_path to avoid littering
    executor._out_dir = str(tmp_path / "out")
    os.makedirs(executor._out_dir, exist_ok=True)

    assert executor.name == "template_extractor"
    assert "parse_templates" in executor.capabilities()

    # 1. Parse templates
    result = executor.execute(
        "parse_templates",
        {"target_file": str(log_file), "log_format": "<Date> <Time> <Level> <Content>", "algorithm": "drain"},
    )

    assert result["status"] == "success"
    assert result["total_templates_found"] > 0
    assert result["total_lines_parsed"] == 3

    # 2. Get templates
    templates_result = executor.execute("get_templates", {"limit": 5})

    assert templates_result["status"] == "success"
    templates = templates_result["templates"]
    assert len(templates) > 0

    # Find the error template
    error_template = None
    for t in templates:
        if "Connection failed" in t["EventTemplate"]:
            error_template = t
            break

    assert error_template is not None
    event_id = error_template["EventId"]

    # 3. Query parameters
    params_result = executor.execute("query_parameters", {"event_id": event_id})

    assert params_result["status"] == "success"
    assert params_result["event_id"] == event_id
    params = params_result["parameters"]
    assert len(params) == 2
    # The IP addresses should be extracted as parameters
    assert ["192.168.1.1"] in params or ["10.0.0.1"] in params
