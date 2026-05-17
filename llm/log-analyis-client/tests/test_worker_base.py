import pytest
from executors.base import BaseExecutor
from typing import Dict, Any, List

class DummyExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "dummy"

    def capabilities(self) -> List[str]:
        return ["do_something"]

    def execute(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if action == "do_something":
            return {"status": "success", "echo": args.get("msg")}
        raise ValueError("Unsupported")

def test_executor_base():
    executor = DummyExecutor()
    assert executor.name == "dummy"
    assert "do_something" in executor.capabilities()
    
    result = executor.execute("do_something", {"msg": "hello"})
    assert result["status"] == "success"
    assert result["echo"] == "hello"
    
    with pytest.raises(ValueError):
        executor.execute("unknown", {})
