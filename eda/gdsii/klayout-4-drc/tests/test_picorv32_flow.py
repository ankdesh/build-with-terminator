"""Check source identity, DRC accounting, and physical-scale checks for the case."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import klayout.db as kdb
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "flows/picorv32_asap7" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vendored_rtl_matches_upstream_git_blob():
    flow = load_module("flow")
    flow.source_hashes()
    content = (flow.HERE / "rtl/picorv32.v").read_bytes()
    blob = b"blob " + str(len(content)).encode() + b"\0" + content
    assert hashlib.sha1(blob).hexdigest() == "cc45fa998f1857b06a856ea59b931f6c37e06b34"


def test_gds_alone_is_an_incomplete_flow(tmp_path):
    flow = load_module("flow")
    results = tmp_path / "results/asap7/picorv32_autofix/baseline"
    results.mkdir(parents=True)
    (results / "6_final.gds").write_bytes(b"partial result")
    summary = flow.summarize(tmp_path, "baseline")
    assert set(summary["missing_artifacts"]) == {"def", "odb", "v", "sdc", "spef"}
    assert summary["public_drc"]["status"] == "not_run"


def test_drc_counts_items_instead_of_marker_values(tmp_path):
    flow = load_module("flow")
    reports = tmp_path / "reports/asap7/picorv32_autofix/baseline"
    reports.mkdir(parents=True)
    (reports / "6_drc.lyrdb").write_text(
        '<report-database><items>'
        '<item><category>width</category><values><value>a</value><value>b</value></values></item>'
        '<item><category>width</category><values><value>c</value></values></item>'
        '<item><category>spacing</category><values><value>d</value></values></item>'
        '</items></report-database>'
    )
    audit = flow.summarize(tmp_path, "baseline")["public_drc"]
    assert audit["status"] == "complete"
    assert audit["items"] == 3
    assert audit["categories"] == {"spacing": 1, "width": 2}
    assert flow.report_counts(reports / "6_drc.lyrdb") == {
        "items": 3, "categories": {"spacing": 1, "width": 2}}


def test_independent_audit_rejects_a_changed_baseline(tmp_path, monkeypatch):
    flow = load_module("flow")
    work = tmp_path / "runs/baseline"
    work.mkdir(parents=True)
    gds = work / "final.gds"
    gds.write_bytes(b"original baseline")
    original = flow.sha256(gds)
    (work / "run.json").write_text(json.dumps({
        "flow_exit_code": 0, "missing_artifacts": [], "final": {"gds": "final.gds"},
        "artifacts": {"final.gds": original}}))
    gds.write_bytes(b"changed baseline")
    monkeypatch.setattr(flow, "verified_toolchain", lambda root: None)
    with pytest.raises(ValueError, match="Baseline GDS changed"):
        flow.audit(SimpleNamespace(output=tmp_path, attempt="baseline"))


@pytest.mark.parametrize("scale,should_pass", [(1, True), (1000, False)])
def test_gds_def_scale_check_and_scalar_instance_count(tmp_path, scale, should_pass):
    inspector = load_module("inspect_gds")
    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("picorv32")
    master = layout.create_cell("example_master")
    master.shapes(layout.layer(19, 0)).insert(kdb.Box(0, 0, 100, 100))
    top.insert(kdb.CellInstArray(master.cell_index(), kdb.Trans()))
    for layer in (20, 30, 40):
        top.shapes(layout.layer(layer, 0)).insert(kdb.Box(0, 0, 1000 * scale, 1000 * scale))
    gds = tmp_path / "layout.gds"
    layout.write(str(gds))
    def_file = tmp_path / "layout.def"
    def_file.write_text("UNITS DISTANCE MICRONS 1000 ;\nDIEAREA ( 0 0 ) ( 1000 1000 ) ;\n")
    if should_pass:
        result = inspector.inspect(gds, def_file)
        assert result["status"] == "passed"
        assert result["direct_instance_count"] == 1
    else:
        with pytest.raises(ValueError, match="scale or bounds differ"):
            inspector.inspect(gds, def_file)
