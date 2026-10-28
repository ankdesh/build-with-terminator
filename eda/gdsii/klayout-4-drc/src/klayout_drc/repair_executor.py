"""Execute a candidate in a bounded, credential-free Bubblewrap worker."""
import ast
from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from .config import DEFAULT_TIMEOUT_SECONDS

EXEC_STATUS_SUCCESS = "success"
EXEC_STATUS_SYNTAX_ERROR = "syntax_error"
EXEC_STATUS_NONZERO_EXIT = "nonzero_exit"
EXEC_STATUS_TIMEOUT = "timeout"
EXEC_STATUS_MISSING_OUTPUT = "missing_output"
WORKER_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/tmp",
              "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}


@lru_cache(maxsize=1)
def sandbox_availability() -> str | None:
    executable = shutil.which("bwrap")
    if not executable:
        return "Bubblewrap is not installed. Candidate execution is blocked."
    try:
        command = [executable, "--unshare-all", "--unshare-user", "--disable-userns", "--die-with-parent",
                   "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                   "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
                   "--size", "16777216", "--tmpfs", "/tmp",
                   "--ro-bind", str(Path(__file__).with_name("worker_policy.py")), "/worker_policy.py"]
        runtime = Path(sys.prefix)
        if (runtime / "pyvenv.cfg").exists():
            command += ["--ro-bind", str(runtime), "/runtime"]
            python = "/runtime/bin/python"
        else:
            python = sys.executable
        command += ["--", python, "-I", "-c",
                    "import runpy; runpy.run_path('/worker_policy.py')['install'](); import klayout.db"]
        probe = subprocess.run(command, env=WORKER_ENV, capture_output=True, text=True, timeout=10)
        if probe.returncode:
            return f"Bubblewrap isolation unavailable: {probe.stderr.strip()}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Bubblewrap isolation unavailable: {exc}"
    return None


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    output_gds: Path | None
    error_message: str | None = None
    peak_rss_bytes: int | None = None


class RepairExecutor:
    def __init__(self, candidate_script, input_gds, output_gds,
                 timeout_seconds=None, python_bin=sys.executable,
                 memory_bytes=None, max_output_bytes=64*1024**2, max_log_bytes=1024**2):
        self.candidate_script = Path(candidate_script).resolve()
        self.input_gds = Path(input_gds).resolve()
        self.output_gds = Path(output_gds).absolute()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else int(os.environ.get("KLAYOUT_DRC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
        self.python_bin = Path(python_bin).absolute()
        self.memory_bytes = memory_bytes if memory_bytes is not None else int(os.environ.get("KLAYOUT_DRC_MEMORY_MB", 2048))*1024**2
        self.max_output_bytes = max_output_bytes
        self.max_log_bytes = max_log_bytes

    def _check_syntax(self):
        try:
            ast.parse(self.candidate_script.read_text(), filename=str(self.candidate_script))
        except (SyntaxError, OSError) as exc:
            return f"{type(exc).__name__}: {exc}"
        return None

    def _sandbox_command(self, output_dir):
        command = [shutil.which('bwrap'), '--unshare-all', '--unshare-user', '--die-with-parent', '--new-session',
                   '--cap-drop', 'ALL', '--disable-userns', '--proc', '/proc', '--dev', '/dev', '--size', '16777216', '--tmpfs', '/tmp']
        for directory in ('/usr', '/lib', '/lib64'):
            if Path(directory).exists():
                command += ['--ro-bind', directory, directory]
        if Path('/etc/ld.so.cache').exists():
            command += ['--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache']
        runtime = self.python_bin.parent.parent
        if (runtime / 'pyvenv.cfg').exists():
            command += ['--ro-bind', str(runtime), '/runtime']
            python = '/runtime/bin/python'
        else:
            python = str(self.python_bin.resolve())
            if not python.startswith('/usr/'):
                raise ValueError('Worker Python must be a venv or a system /usr runtime')
        command += ['--ro-bind', str(self.input_gds), '/input.gds',
                    '--ro-bind', str(self.candidate_script), '/candidate.py',
                    '--ro-bind', str(Path(__file__).with_name('worker_policy.py')), '/worker_policy.py',
                    '--bind', str(output_dir), '/output', '--chdir', '/output']
        # Set limits inside the new user/PID namespace, before loading candidate code.
        adapter = (
            "import resource,runpy,sys\n"
            f"resource.setrlimit(resource.RLIMIT_AS, ({self.memory_bytes}, {self.memory_bytes}))\n"
            f"resource.setrlimit(resource.RLIMIT_CPU, ({max(1,int(self.timeout_seconds))}, {max(1,int(self.timeout_seconds))}))\n"
            f"resource.setrlimit(resource.RLIMIT_FSIZE, ({self.max_output_bytes}, {self.max_output_bytes}))\n"
            "resource.setrlimit(resource.RLIMIT_NPROC, (64,64))\n"
            "resource.setrlimit(resource.RLIMIT_NOFILE, (64,64))\n"
            "runpy.run_path('/worker_policy.py')['install']()\n"
            "sys.argv=['/candidate.py','/input.gds','/output/patched.gds']\n"
            "mod=runpy.run_path('/candidate.py',run_name='__main__')\n"
            "from pathlib import Path\n"
            "if not Path('/output/patched.gds').exists() and callable(mod.get('fix_layout')):\n"
            "    mod['fix_layout']('/input.gds','/output/patched.gds')\n"
        )
        return command + ['--', python, '-I', '-c', adapter]

    def execute(self):
        syntax = self._check_syntax()
        if syntax:
            return ExecutionResult('syntax_error', 1, 0., '', syntax, None, syntax)
        blocked = sandbox_availability()
        if blocked:
            return ExecutionResult('blocked', None, 0., '', blocked, None, blocked)
        if self.output_gds.resolve() in (self.input_gds, self.candidate_script):
            return ExecutionResult('nonzero_exit', None, 0., '', '', None, 'Output aliases an immutable input')
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='drc-worker-') as tmp:
            scratch = Path(tmp)
            output = scratch / 'output'; output.mkdir()
            stdout_path, stderr_path = scratch/'stdout', scratch/'stderr'
            reason, status = None, None
            peak_rss = None
            proc = None
            try:
                with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
                    proc = subprocess.Popen(self._sandbox_command(output), env=WORKER_ENV,
                                            stdout=stdout, stderr=stderr, start_new_session=True)
                    while proc.poll() is None:
                        measured = self._process_tree_rss(proc.pid)
                        if measured is not None:
                            peak_rss = max(peak_rss or 0, measured)
                        if time.monotonic()-start > self.timeout_seconds:
                            reason, status = 'Candidate timeout: exceeded wall-time limit', 'timeout'
                        elif stdout_path.stat().st_size + stderr_path.stat().st_size > self.max_log_bytes:
                            reason, status = 'Candidate exceeded log limit', 'nonzero_exit'
                        elif self._output_usage(output) > self.max_output_bytes:
                            reason, status = 'Candidate exceeded output limit', 'nonzero_exit'
                        if reason:
                            os.killpg(proc.pid, signal.SIGKILL); break
                        time.sleep(.02)
                    proc.wait()
                    # bwrap --die-with-parent owns its PID namespace. Kill remaining host group too.
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                out = stdout_path.read_bytes()[:self.max_log_bytes].decode(errors='replace')
                err = stderr_path.read_bytes()[:self.max_log_bytes].decode(errors='replace')
                candidate = output/'patched.gds'
                if reason:
                    pass
                elif proc.returncode:
                    status = 'blocked' if err.startswith('bwrap:') else 'nonzero_exit'
                    reason = f'Worker exited with code {proc.returncode}: {err.strip()}'
                elif candidate.is_symlink() or not candidate.is_file() or not candidate.stat().st_size:
                    status, reason = 'missing_output', 'Worker did not produce a regular, nonempty patched.gds'
                elif self._output_usage(output) > self.max_output_bytes or stdout_path.stat().st_size + stderr_path.stat().st_size > self.max_log_bytes:
                    status, reason = 'nonzero_exit', 'Candidate exceeded output/log limit'
                else:
                    self.output_gds.parent.mkdir(parents=True, exist_ok=True)
                    if self.output_gds.exists() or self.output_gds.is_symlink():
                        self.output_gds.unlink()
                    shutil.copyfile(candidate, self.output_gds)
                    status = 'success'
                return ExecutionResult(status, proc.returncode, time.monotonic()-start, out, err,
                                       self.output_gds if status == 'success' else None, reason, peak_rss)
            except (OSError, ValueError) as exc:
                return ExecutionResult('blocked' if proc is None else 'nonzero_exit', None,
                                       time.monotonic()-start, '', str(exc), None, str(exc))
            finally:
                if proc is not None and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()

    def _output_usage(self, directory):
        total = 0
        for count, path in enumerate(directory.rglob('*')):
            if count >= 1024:
                return self.max_output_bytes + 1
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
        return total

    @staticmethod
    def _process_tree_rss(pid):
        """Sample host-visible worker RSS. The maximum is a sampled lower bound."""
        pending, seen, total = [pid], set(), 0
        measured = False
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            try:
                status = Path(f'/proc/{current}/status').read_text()
                line = next((line for line in status.splitlines() if line.startswith('VmRSS:')), None)
                if line:
                    total += int(line.split()[1])*1024; measured = True
                children = Path(f'/proc/{current}/task/{current}/children').read_text()
                pending.extend(map(int, children.split()))
            except (OSError, ValueError):
                pass
        return total if measured else None
