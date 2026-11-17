"""Run automatic analysis and candidate checks in the normal worker process."""
from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from config import config
from pipeline_core.process_runner import ProcessRunner


class AgentRunner:
    def __init__(self) -> None:
        self.worker = ProcessRunner(timeout_seconds=config.agent_execution_timeout_seconds,
            memory_bytes=config.agent_memory_limit_mb * 1024**2)

    async def run(self, revision: Any, source: Path, parameters: dict,
                  directory: Path, cancel: threading.Event) -> dict:
        if cancel.is_set():
            raise ValueError('Chat cancelled')
        directory = directory.resolve()
        try:
            result = await self.worker.run(revision,source,parameters,directory,cancel)
            if cancel.is_set() or result.get('cancelled'):
                raise ValueError('Chat cancelled')
            if result.get('error') == 'Pipeline exceeded its execution deadline':
                raise ValueError('Temporary execution exceeded its deadline')
            events = directory/'output'/'events.jsonl'
            if events.is_file():
                result['execution_events'] = [json.loads(line) for line in events.read_text().splitlines()][-100:]
            return result
        finally:
            (directory/'input.csv').unlink(missing_ok=True)
            (directory/'request.json').unlink(missing_ok=True)
