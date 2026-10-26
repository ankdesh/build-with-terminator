"""Exercise the declared CSV limit with a known-result isolated pipeline."""

import argparse
import asyncio
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def benchmark(size_mb: int) -> None:
    from pipeline_core.models import ProjectRevision
    from pipeline_core.process_runner import ProcessRunner
    with tempfile.TemporaryDirectory(prefix="wps-benchmark-") as temporary:
        root = Path(temporary)
        source = root / "large.csv"
        rows = 0
        with source.open("w") as stream:
            stream.write("zone,value\n")
            while stream.tell() < size_mb * 1024 * 1024 - 120:
                stream.write(f"{'A' * 64},{rows}\n")
                rows += 1
        revision = ProjectRevision.model_validate({
            "title": "Capacity reference", "input_contract": {"columns": [
                {"name": "zone", "dtype": "string"}, {"name": "value", "dtype": "integer"}]},
            "steps": [
                {"id": "clean", "title": "Preserve input", "stage": "cleanup", "function": "clean",
                    "inputs": ["data"], "outputs": ["cleaned"],
                    "code": "def clean(inputs, parameters, context):\n    return {'cleaned': inputs['data'].copy()}\n"},
                {"id": "analyze", "title": "Known sum and full export", "stage": "analysis", "function": "analyze",
                    "inputs": ["cleaned"], "outputs": ["total", "records"],
                    "code": "def analyze(inputs, parameters, context):\n    df = inputs['cleaned']\n    return {'total': int(df['value'].sum()), 'records': df}\n"},
            ],
            "dashboard": {"title": "Capacity reference", "widgets": [
                {"id": "total", "kind": "metric", "title": "Known sum", "output": "total"},
                {"id": "records", "kind": "table", "title": "Full records", "output": "records"},
            ]},
        })
        start = time.monotonic()
        response = await ProcessRunner().run(revision, source, {}, root / "job", threading.Event())
        elapsed = time.monotonic() - start
        if not response["success"]:
            raise RuntimeError(response)
        result = response["result"]
        assert result["outputs"]["total"]["value"] == rows * (rows - 1) // 2
        assert len(result["outputs"]["records"]["rows"]) == min(rows, 500)
        with (root / "job/output/records.csv").open() as stream:
            assert sum(1 for _ in stream) == rows + 1
        print(f"Known-result CSV benchmark passed: {source.stat().st_size / 1024 ** 2:.2f} MiB, {rows:,} rows, {elapsed:.2f} seconds, full CSV export verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size-mb", type=int, default=100, choices=range(1, 101))
    args = parser.parse_args()
    asyncio.run(benchmark(args.size_mb))


if __name__ == "__main__":
    main()
