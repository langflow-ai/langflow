import pytest
from lfx.execution.executor import Executor
from lfx.execution.registry import ExecutorNotFoundError, ExecutorRegistry


class _Stub(Executor):
    kind = "stub"

    async def execute(self, unit):  # noqa: ARG002
        return
        yield


def test_register_and_get_by_kind():
    registry = ExecutorRegistry()
    registry.register(_Stub())
    assert registry.get("stub").kind == "stub"


def test_get_unknown_raises():
    with pytest.raises(ExecutorNotFoundError, match="nope"):
        ExecutorRegistry().get("nope")


def test_register_replaces_same_kind():
    registry = ExecutorRegistry()
    a = _Stub()
    b = _Stub()
    registry.register(a)
    registry.register(b)
    assert registry.get("stub") is b
