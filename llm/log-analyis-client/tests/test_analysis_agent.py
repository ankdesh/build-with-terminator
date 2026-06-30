import os
import tempfile
import yaml
from analysis_agent import AnalysisAgent


def test_resolve_template():
    agent = AnalysisAgent(log_path="dummy.log", query="count errors")
    template = [
        {"action": "parse_templates", "query": "{{ query }}", "file": "{{ log_file }}"},
        {"action": "execute_python", "inputs": {"df_query": "{{ query }}"}}
    ]
    resolved = agent._resolve_template(template, "count errors")
    assert len(resolved) == 2
    assert resolved[0]["query"] == "count errors"
    assert resolved[0]["file"] == os.path.abspath("dummy.log")
    assert resolved[1]["inputs"]["df_query"] == "count errors"


def test_list_templates():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a dummy templates directory
        templates_dir = os.path.join(tmp_dir, "workflow_templates")
        os.makedirs(templates_dir)
        
        # Write a dummy template
        template_content = [{"action": "get_stats", "executor": "stats"}]
        with open(os.path.join(templates_dir, "dummy_template.yaml"), "w") as f:
            yaml.dump(template_content, f)

        # Instantiate AnalysisAgent and override templates_dir
        agent = AnalysisAgent(log_path="dummy.log", query="count errors")
        agent.templates_dir = templates_dir
        
        templates = agent._list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "dummy_template.yaml"
        assert templates[0]["content"] == template_content
