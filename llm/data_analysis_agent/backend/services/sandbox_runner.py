"""Linux isolated execution for automatic analysis and candidate checks."""
from __future__ import annotations
import asyncio
import functools
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any
from config import config


@functools.lru_cache(maxsize=1)
def sandbox_available() -> bool:
    if sys.platform != 'linux' or not shutil.which('bwrap'): return False
    try:
        return subprocess.run(['bwrap','--ro-bind','/','/','--unshare-net','--unshare-pid','--die-with-parent','--','/usr/bin/true'],
            capture_output=True,timeout=3,check=False).returncode == 0
    except (OSError,subprocess.TimeoutExpired): return False


class SandboxRunner:
    async def run(self, revision: Any, source: Path, parameters: dict, directory: Path, cancel: threading.Event) -> dict:
        return await asyncio.to_thread(self._run,revision,source,parameters,directory,cancel)

    def _run(self, revision: Any, source: Path, parameters: dict, directory: Path, cancel: threading.Event) -> dict:
        if not sandbox_available():
            raise ValueError('Automatic Python is unavailable. Install bubblewrap and permit Linux user/network namespaces.')
        directory = directory.resolve(); directory.mkdir(parents=True,exist_ok=True)
        output = directory/'output'; output.mkdir(exist_ok=True)
        # The worker sees only an immutable snapshot, not the project store.
        snapshot = directory/'input.csv'; shutil.copyfile(source,snapshot)
        request = {'partial':True,'revision':revision.model_dump(),'input_path':'/input.csv','output_dir':'/output',
            'parameters':parameters,'timeout_seconds':config.agent_execution_timeout_seconds,
            'memory_bytes':config.agent_memory_limit_mb*1024**2}
        request_file = directory/'request.json'; request_file.write_text(json.dumps(request))
        command = ['bwrap','--unshare-user','--unshare-net','--unshare-pid','--unshare-ipc','--unshare-uts',
            '--die-with-parent','--cap-drop','ALL','--clearenv']
        for name in ['/usr','/lib','/lib64']:
            if Path(name).exists(): command += ['--ro-bind',name,name]
        if Path('/etc/ld.so.cache').exists(): command += ['--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache']
        environment_root = Path(sys.prefix).resolve()
        if not str(environment_root).startswith('/usr'):
            command += ['--ro-bind',str(environment_root),str(environment_root)]
        runtime = Path(__file__).resolve().parents[2]/'pipeline_core'
        command += ['--dir','/runtime','--ro-bind',str(runtime),'/runtime/pipeline_core',
            '--ro-bind',str(snapshot),'/input.csv','--ro-bind',str(request_file),'/request.json',
            '--bind',str(output),'/output','--tmpfs','/tmp','--proc','/proc','--dev','/dev','--chdir','/output']
        for name,value in {'PATH':'/usr/bin','HOME':'/nonexistent','PYTHONPATH':'/runtime',
            'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','PYTHONIOENCODING':'utf-8',
            'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}.items():
            command += ['--setenv',name,value]
        command += ['--',sys.executable,'-m','pipeline_core.worker','/request.json']
        with (directory/'worker.log').open('wb') as log:
            process = subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
            try:
                deadline = time.monotonic()+config.agent_execution_timeout_seconds
                while process.poll() is None:
                    if cancel.is_set() or time.monotonic()>deadline:
                        raise ValueError('Chat cancelled' if cancel.is_set() else 'Temporary execution exceeded its deadline')
                    time.sleep(.05)
                response = output/'response.json'
                if not response.exists():
                    raise ValueError('Isolated worker failed: '+(directory/'worker.log').read_text(errors='replace')[-3000:])
                result = dict(json.loads(response.read_text()))
                events = output/'events.jsonl'
                if events.is_file():
                    result['execution_events'] = [json.loads(line) for line in events.read_text().splitlines()][-100:]
                return result
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL)
                    process.wait(timeout=5)
                snapshot.unlink(missing_ok=True)
                request_file.unlink(missing_ok=True)
