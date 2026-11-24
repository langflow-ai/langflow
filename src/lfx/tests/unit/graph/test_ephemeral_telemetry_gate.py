"""Ephemeral (anonymous serving) runs must not persist execution telemetry.

Transaction rows store component inputs/outputs verbatim, so the serving-plane
no-persist contract covers them alongside chat messages. ``log_transaction``
reads the decision off the vertex's graph (the per-component ContextVar binding
is already out of scope at its call sites).
"""

from types import SimpleNamespace

import pytest
from lfx.graph.utils import log_transaction


class _RecordingTransactionService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    async def log_transaction(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _vertex(*, persist_messages: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id="v1",
        params={"input_value": "remember me"},
        graph=SimpleNamespace(flow_id="flow-1", persist_messages=persist_messages),
    )


@pytest.fixture
def transaction_service(monkeypatch) -> _RecordingTransactionService:
    service = _RecordingTransactionService()
    monkeypatch.setattr("lfx.services.deps.get_transaction_service", lambda: service)
    return service


async def test_log_transaction_skipped_for_ephemeral_graph(transaction_service):
    await log_transaction("flow-1", _vertex(persist_messages=False), status="success")
    assert transaction_service.calls == []


async def test_log_transaction_written_for_persisting_graph(transaction_service):
    # Guards the fixture wiring: the same call with persistence on does log.
    await log_transaction("flow-1", _vertex(persist_messages=True), status="success")
    assert len(transaction_service.calls) == 1
    assert transaction_service.calls[0]["vertex_id"] == "v1"


async def test_log_transaction_defaults_to_persisting_without_graph(transaction_service):
    # A vertex with no graph (standalone / placeholder execution) keeps the
    # legacy behavior: telemetry is written.
    vertex = SimpleNamespace(id="v1", params={}, graph=None)
    await log_transaction("flow-1", vertex, status="success")
    assert len(transaction_service.calls) == 1
