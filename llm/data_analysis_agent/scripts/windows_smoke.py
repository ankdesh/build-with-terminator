"""Test the real frozen launcher and worker without Python on the child's PATH."""

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This smoke test requires Windows")
    from backend.services.project_store import ProjectStore
    from backend.services.export_service import ExportService
    from examples.electric_dashboard import revision
    from pipeline_core.engine import PipelineEngine, fingerprint
    from pipeline_core.models import RunRecord, now
    import pandas as pd
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store = ProjectStore(root / "builder")
        project = store.create("Release smoke test")
        source = root / "data.csv"
        pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=40, freq="h"), "zone": ["A"] * 40,
            "kwh": [float(n + 10) for n in range(40)]}).to_csv(source, index=False)
        store.save_dataset(project["id"], source, "release.csv", {}, "")
        draft = revision()
        store.save_revision(project["id"], draft)
        record = RunRecord(revision_id=draft.revision_id, dataset_name="release.csv", input_hash=fingerprint(source), parameters=draft.default_parameters())
        store.put_run(project["id"], record)
        result = PipelineEngine().execute(draft, source, {}, store.run_dir(project["id"], record.run_id) / "output")
        record.status, record.finished_at, record.result = "succeeded", now(), result
        store.put_run(project["id"], record)
        store.accept(project["id"], record.run_id, True)
        archive = ExportService(store, ROOT / "dist/windows-x64.zip").export(project["id"])
        package = root / "package"
        with zipfile.ZipFile(archive) as stream:
            stream.extractall(package)
        environment = dict(os.environ)
        environment["PATH"] = os.environ["SYSTEMROOT"] + "\\System32"
        environment.pop("OPENAI_API_KEY", None)
        environment.pop("PYTHONPATH", None)
        subprocess.run([str(package / "WPSAnalysis.exe"), "--verify"], cwd=package, env=environment, check=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen([str(package / "WPSAnalysis.exe"), "--headless", "--port", str(port), "--state-dir", str(root / "state")], cwd=package, env=environment)
        base = f"http://127.0.0.1:{port}"

        def post(path: str, payload: dict) -> dict:
            request = urllib.request.Request(base + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)

        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1) as response:
                        assert json.load(response)["model_required"] is False
                    break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError("Frozen runtime exited before startup")
                    time.sleep(.2)
            else:
                raise RuntimeError("Frozen runtime did not start")
            response = post("/api/runtime/run", {"parameters": {}})
            assert response["run"]["status"] == "succeeded", response
            assert response["run"]["result"]["outputs"]["total"]["value"] == result["outputs"]["total"]["value"]
            response = post("/api/runtime/run", {"parameters": {"price": 2}})
            assert response["run"]["result"]["outputs"]["cost"]["value"] == result["outputs"]["total"]["value"] * 2
            with urllib.request.urlopen(base + "/api/runtime/tables/zones") as response:
                assert "zone,kwh" in response.read().decode()
            try:
                urllib.request.urlopen(base + "/api/projects")
                raise AssertionError("Offline runtime exposed builder routes")
            except urllib.error.HTTPError as error:
                assert error.code == 404
            print("Frozen Windows runtime startup, workers, controls, and full CSV export passed")
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
