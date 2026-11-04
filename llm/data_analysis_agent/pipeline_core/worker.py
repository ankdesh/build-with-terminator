"""Worker entrypoint. Contains no model client or builder configuration."""

import contextlib
import io
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from pipeline_core.engine import PipelineEngine
from pipeline_core.models import ProjectRevision


class BoundedLog(io.TextIOBase):
    def __init__(self) -> None:
        self.remaining = 64000
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        if self.remaining:
            self.parts.append(text[:self.remaining])
        self.remaining = max(0, self.remaining - len(text))
        return len(text)


def watch_parent(parent_pid: int) -> None:
    """Stop this worker process group if its owning service exits."""
    import signal
    while True:
        if os.getppid() != parent_pid:
            os.killpg(os.getpgrp(), signal.SIGKILL)
            return
        time.sleep(0.25)


def main(request_file: str) -> int:
    request = json.loads(Path(request_file).read_text())
    output = Path(request["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        threading.Thread(target=watch_parent, args=(request.get("parent_pid", os.getppid()),), daemon=True).start()
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (request["memory_bytes"], request["memory_bytes"]))
        resource.setrlimit(resource.RLIMIT_CPU, (request["timeout_seconds"], request["timeout_seconds"] + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024 * 1024, 512 * 1024 * 1024))
    log = BoundedLog()
    def notify(event: dict) -> None:
        with (output / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")

    try:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            revision = ProjectRevision.model_validate(request["revision"])
            result = PipelineEngine().execute(revision, Path(request["input_path"]), request["parameters"],
                output, Path(request["cache_dir"]) if request.get("cache_dir") else None, notify)
        response = {"success": True, "result": result, "stdout": "".join(log.parts)}
        code = 0
    except Exception as exc:
        response = {"success": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-16000:]}
        code = 1
    (output / "response.json").write_text(json.dumps(response, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
