import pytest
from lfx.execution.executor import Executor
from lfx.execution.registry import ExecutorKindCollisionError, ExecutorNotFoundError, ExecutorRegistry


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


def test_register_replace_false_raises_on_collision():
    registry = ExecutorRegistry()
    first = _Stub()
    registry.register(first)
    with pytest.raises(ExecutorKindCollisionError, match="stub"):
        registry.register(_Stub(), replace=False)
    assert registry.get("stub") is first


def test_has_reflects_registration():
    registry = ExecutorRegistry()
    assert not registry.has("stub")
    registry.register(_Stub())
    assert registry.has("stub")
