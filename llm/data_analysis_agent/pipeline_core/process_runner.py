"""Process isolation, resource limits, cancellation, and progress collection."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, cast

from pipeline_core.models import ProjectRevision


class WindowsJob:
    """Limit trusted application workers and kill them when their job closes."""

    def __init__(self, process: subprocess.Popen, memory_bytes: int) -> None:
        import ctypes
        from ctypes import wintypes
        windows_ctypes = cast(Any, ctypes)
        kernel = windows_ctypes.WinDLL("kernel32", use_last_error=True)

        class Basic(ctypes.Structure):
            _fields_ = [("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
                ("Flags", wintypes.DWORD), ("Minimum", ctypes.c_size_t), ("Maximum", ctypes.c_size_t),
                ("ActiveProcesses", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                ("Priority", wintypes.DWORD), ("Scheduling", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

        class Limits(ctypes.Structure):
            _fields_ = [("Basic", Basic), ("IO", Counters), ("ProcessMemory", ctypes.c_size_t),
                ("JobMemory", ctypes.c_size_t), ("PeakProcess", ctypes.c_size_t), ("PeakJob", ctypes.c_size_t)]

        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise windows_ctypes.WinError(windows_ctypes.get_last_error())
        limits = Limits()
        limits.Basic.Flags = 0x2000 | 0x100 | 0x8  # kill on close, memory, active process limit
        limits.Basic.ActiveProcesses = 1
        limits.ProcessMemory = memory_bytes
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(self.handle, int(cast(Any, process)._handle)):
            kernel.CloseHandle(self.handle)
            raise windows_ctypes.WinError(windows_ctypes.get_last_error())

    def close(self) -> None:
        self.kernel.CloseHandle(self.handle)


class ProcessRunner:
    """Run generated code outside the API process. Linux isolation is mandatory."""

    def __init__(self, timeout_seconds: int = 120, memory_bytes: int = 4 * 1024 ** 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.memory_bytes = memory_bytes

    async def run(self, revision: ProjectRevision, input_path: Path, parameters: dict[str, Any],
                  job_dir: Path, cancel: threading.Event, cache_dir: Path | None = None,
                  on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._run, revision, input_path, parameters, job_dir, cancel, cache_dir, on_event)

    def _run(self, revision: ProjectRevision, input_path: Path, parameters: dict[str, Any],
             job_dir: Path, cancel: threading.Event, cache_dir: Path | None,
             on_event: Callable[[dict[str, Any]], None] | None) -> dict[str, Any]:
        job_dir.mkdir(parents=True, exist_ok=True)
        output = job_dir / "output"
        output.mkdir(exist_ok=True)
        shutil.copyfile(input_path, job_dir / "input.csv")
        request = {"revision": revision.model_dump(), "input_path": "input.csv", "output_dir": "output",
            "parameters": parameters, "cache_dir": "cache" if cache_dir else None,
            "timeout_seconds": self.timeout_seconds, "memory_bytes": self.memory_bytes}
        (job_dir / "request.json").write_text(json.dumps(request))
        env = {"PATH": os.defpath, "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
            "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        if os.name == "nt":
            for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                if name in os.environ:
                    env[name] = os.environ[name]
            if cache_dir:
                shutil.copytree(cache_dir, job_dir / "cache", dirs_exist_ok=True)
            command = ([sys.executable, "--worker", str(job_dir / "request.json")] if getattr(sys, "frozen", False)
                       else [sys.executable, "-m", "pipeline_core.worker", str(job_dir / "request.json")])
        else:
            bwrap = shutil.which("bwrap")
            if not bwrap:
                return {"success": False, "error": "Bubblewrap is required for Linux execution. Install it and enable user namespaces."}
            core = job_dir / "core"
            shutil.copytree(Path(__file__).parent, core, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
            command = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                "--ro-bind", "/usr", "/usr", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--dir", "/app", "--ro-bind", str(core), "/app/pipeline_core",
                "--dir", "/work", "--ro-bind", str(job_dir / "request.json"), "/work/request.json",
                "--ro-bind", str(job_dir / "input.csv"), "/work/input.csv",
                "--bind", str(output), "/work/output", "--chdir", "/work"]
            for library in ("/lib", "/lib64", "/bin", "/etc/ld.so.cache"):
                if Path(library).exists():
                    command += ["--ro-bind", library, library]
            if cache_dir:
                command += ["--ro-bind", str(cache_dir), "/work/cache"]
            if sys.prefix != sys.base_prefix:
                command += ["--ro-bind", sys.prefix, "/runtime"]
                interpreter = "/runtime/bin/python"
            else:
                interpreter = sys.executable
            env["PYTHONPATH"] = "/app"
            command += ["--", interpreter, "-m", "pipeline_core.worker", "/work/request.json"]
        job = None
        process = None
        try:
            with (job_dir / "worker.log").open("wb") as stderr:
                process = subprocess.Popen(command, cwd=job_dir, env=env, stdout=stderr, stderr=stderr,
                    start_new_session=os.name != "nt")
                if os.name == "nt":
                    job = WindowsJob(process, self.memory_bytes)
                deadline = time.monotonic() + self.timeout_seconds
                offset = 0
                while process.poll() is None:
                    if cancel.is_set() or time.monotonic() > deadline:
                        if job:
                            job.close()
                            job = None
                        else:
                            import signal
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
                        return {"success": False, "cancelled": cancel.is_set(),
                            "error": "Run cancelled" if cancel.is_set() else "Pipeline exceeded its execution deadline"}
                    event_file = output / "events.jsonl"
                    if on_event and event_file.exists():
                        with event_file.open() as stream:
                            stream.seek(offset)
                            while True:
                                position = stream.tell()
                                line = stream.readline()
                                if not line or not line.endswith("\n"):
                                    stream.seek(position)
                                    break
                                try:
                                    on_event(json.loads(line))
                                except json.JSONDecodeError:
                                    continue
                            offset = stream.tell()
                    time.sleep(0.05)
            response = output / "response.json"
            if response.exists():
                return cast(dict[str, Any], json.loads(response.read_text()))
            diagnostic = (job_dir / "worker.log").read_text(errors="replace")[-4000:]
            return {"success": False, "error": f"Worker could not start or exited unexpectedly (code {process.returncode}). {diagnostic}"}
        except Exception as exc:
            return {"success": False, "error": f"Worker failure: {exc}"}
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if job:
                job.close()
