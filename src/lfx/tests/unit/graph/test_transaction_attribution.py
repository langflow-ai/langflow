"""Transaction rows carry the run's message owner and session, so a data subject erase can find them."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from lfx.graph.utils import log_transaction
from lfx.memory.flow_context import derive_message_owner_uuid


class _RecordingTransactionService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    async def log_transaction(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _LegacyTransactionService:
    """A service built before attribution existed: it rejects the new keyword arguments."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    async def log_transaction(self, flow_id, vertex_id, inputs, outputs, status, target_id=None, error=None) -> None:  # noqa: ARG002
        self.calls.append({"flow_id": flow_id, "vertex_id": vertex_id})


def _vertex(**graph_attrs) -> SimpleNamespace:
    graph = SimpleNamespace(flow_id="flow-1", persist_messages=True, **graph_attrs)
    return SimpleNamespace(id="v1", params={"input_value": "my email is alice@example.com"}, graph=graph)


@pytest.fixture
def use_service(monkeypatch):
    def install(service):
        monkeypatch.setattr("lfx.services.deps.get_transaction_service", lambda: service)
        return service

    return install


async def test_should_stamp_the_end_user_owner_and_session_when_the_run_has_an_end_user(use_service):
    service = use_service(_RecordingTransactionService())
    vertex = _vertex(end_user_id="alice", user_id=str(uuid4()), session_id="alice::s1")

    await log_transaction("flow-1", vertex, status="success")

    assert service.calls[0]["user_id"] == derive_message_owner_uuid("alice")
    assert service.calls[0]["session_id"] == "alice::s1"


async def test_should_stamp_the_executing_user_when_the_run_has_no_end_user(use_service):
    service = use_service(_RecordingTransactionService())
    builder = uuid4()

    await log_transaction("flow-1", _vertex(user_id=str(builder), session_id="flow-1"), status="success")

    assert service.calls[0]["user_id"] == builder
    assert service.calls[0]["session_id"] == "flow-1"


async def test_should_still_log_when_the_service_predates_attribution(use_service):
    service = use_service(_LegacyTransactionService())
    vertex = _vertex(end_user_id="alice", user_id=str(uuid4()), session_id="alice::s1")

    await log_transaction("flow-1", vertex, status="success")

    assert service.calls == [{"flow_id": "flow-1", "vertex_id": "v1"}]
