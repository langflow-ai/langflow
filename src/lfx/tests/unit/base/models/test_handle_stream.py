"""Tests for LCModelComponent._handle_stream session_id handling.

When a streaming LLM is wired to ChatOutput, the streaming path tries to persist
a placeholder Message via send_message. With no session_id (e.g. ``lfx run`` with
NoopSession and no ``--session-id``), astore_message rejects the empty value.
The fallback in _handle_stream invokes the model non-streamingly so the run can
still complete.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.base.models.model import LCModelComponent


class _StreamableProbe(LCModelComponent):
    """Minimal LCModelComponent subclass usable without going through Component init."""

    display_name = "Probe"
    description = "test"

    def build_model(self):  # pragma: no cover - abstract stub
        raise NotImplementedError


def _make_probe(*, connected: bool, session_id, event_manager=None):
    probe = _StreamableProbe.__new__(_StreamableProbe)
    probe.is_connected_to_chat_output = MagicMock(return_value=connected)
    # ``graph`` is a read-only property on Component (-> self._vertex.graph),
    # so wire the underlying _vertex instead of trying to assign graph directly.
    probe._vertex = SimpleNamespace(graph=SimpleNamespace(session_id=session_id, flow_id=None))
    probe.icon = "brain"
    probe._id = "probe-1"
    probe._event_manager = event_manager
    probe.send_message = AsyncMock()
    probe._build_source = MagicMock(return_value=None)
    return probe


@pytest.mark.asyncio
async def test_handle_stream_falls_back_to_invoke_when_no_session_id():
    """Empty graph.session_id must not call send_message; falls back to ainvoke."""
    probe = _make_probe(connected=True, session_id="", event_manager=MagicMock())
    runnable = SimpleNamespace(
        astream=MagicMock(),
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="hi from invoke")),
    )

    lf_message, result, ai_message = await probe._handle_stream(runnable, "input")

    runnable.ainvoke.assert_awaited_once_with("input")
    runnable.astream.assert_not_called()
    probe.send_message.assert_not_awaited()
    assert lf_message is None
    assert result == "hi from invoke"
    assert isinstance(result, str)
    assert ai_message is not None


@pytest.mark.asyncio
async def test_handle_stream_falls_back_to_invoke_when_no_event_manager():
    """Without an event_manager (e.g. lfx run) the chunk iterator would never be drained.

    The fallback prevents send_message from storing a Message whose text is an unconsumed
    AsyncIterator, which previously surfaced as an empty result downstream.
    """
    probe = _make_probe(connected=True, session_id="sess-123", event_manager=None)
    runnable = SimpleNamespace(
        astream=MagicMock(),
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="batched")),
    )

    lf_message, result, ai_message = await probe._handle_stream(runnable, "input")

    runnable.ainvoke.assert_awaited_once_with("input")
    runnable.astream.assert_not_called()
    probe.send_message.assert_not_awaited()
    assert lf_message is None
    assert result == "batched"
    # Lock in that the fallback returns plain text, not the unconsumed AsyncIterator
    # that astream would have produced — the original bug surfaced as empty downstream
    # text because the iterator was stored verbatim.
    assert isinstance(result, str)
    assert ai_message is not None


@pytest.mark.asyncio
async def test_handle_stream_uses_send_message_when_session_id_and_event_manager_present():
    """Both session_id and event_manager present -> original streaming + persistence path."""
    probe = _make_probe(connected=True, session_id="sess-123", event_manager=MagicMock())
    probe.send_message.return_value = SimpleNamespace(text="streamed text")
    runnable = SimpleNamespace(astream=MagicMock(), ainvoke=AsyncMock())

    lf_message, result, ai_message = await probe._handle_stream(runnable, "input")

    probe.send_message.assert_awaited_once()
    runnable.ainvoke.assert_not_awaited()
    assert lf_message is not None
    assert result == "streamed text"
    assert ai_message is None


@pytest.mark.asyncio
async def test_handle_stream_invokes_directly_when_not_connected_to_chat_output():
    """Pre-existing branch: not connected -> ainvoke regardless of session_id."""
    probe = _make_probe(connected=False, session_id="sess-123", event_manager=MagicMock())
    runnable = SimpleNamespace(
        astream=MagicMock(),
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="direct")),
    )

    lf_message, result, _ = await probe._handle_stream(runnable, "input")

    runnable.ainvoke.assert_awaited_once_with("input")
    probe.send_message.assert_not_awaited()
    assert lf_message is None
    assert result == "direct"
