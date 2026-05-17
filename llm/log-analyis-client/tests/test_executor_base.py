from typing import Any

import pytest

from executors.base import BaseExecutor


class DummyExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "dummy"

    def capabilities(self) -> list[str]:
        return ["do_something"]

    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
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
