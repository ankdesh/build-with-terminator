import pytest
from worker_base import WorkerBase
from typing import Dict, Any, List

class DummyWorker(WorkerBase):
    @property
    def name(self) -> str:
        return "dummy"

    def capabilities(self) -> List[str]:
        return ["do_something"]

    def execute(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if action == "do_something":
            return {"status": "success", "echo": args.get("msg")}
        raise ValueError("Unsupported")

def test_worker_base():
    worker = DummyWorker()
    assert worker.name == "dummy"
    assert "do_something" in worker.capabilities()
    
    result = worker.execute("do_something", {"msg": "hello"})
    assert result["status"] == "success"
    assert result["echo"] == "hello"
    
    with pytest.raises(ValueError):
        worker.execute("unknown", {})
