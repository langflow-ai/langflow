"""Regression tests for CugaAgent session_id fallback (cuga_agent.py).

The agent's ``message_response`` builds an internal ``Message`` with
``session_id=self.graph.session_id or str(uuid.uuid4())``. The fallback exists
because some flows (notably ``lfx run`` without --session-id, before run_flow
auto-generates one) had a graph with an empty session_id, which crashed
``astore_message`` validation. The ``str(...)`` wrap matches the rest of the
file (every other ``uuid.uuid4()`` is wrapped) and the codebase's expectation
that Message.session_id renders as a hex string in logs / persistence.

These tests halt the agent's execution at the Message construction site so we
can verify the constructed kwargs without mocking the rest of the agent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# CugaComponent's class body looks up MODELS_METADATA["OpenAI"], so it can only be
# imported when an OpenAI provider is registered (depends on optional deps in the env).
# Skip the whole module if the import side-effect fails.
try:
    from lfx.components.cuga import cuga_agent
except Exception as exc:
    pytest.skip(f"cuga_agent module not importable in this env: {exc}", allow_module_level=True)


class _Halt(Exception):  # noqa: N818
    """Sentinel raised by the patched Message constructor to stop further execution."""


@pytest.fixture
def captured_message_kwargs():
    """Patch cuga_agent.Message to capture constructor kwargs and halt execution."""
    captured: dict = {}

    def fake_message(*_args, **kwargs):
        captured.update(kwargs)
        raise _Halt

    with patch.object(cuga_agent, "Message", side_effect=fake_message):
        yield captured


def _make_agent(*, graph_session_id):
    """Build a minimally-initialized CugaComponent that reaches Message construction."""
    agent = cuga_agent.CugaComponent.__new__(cuga_agent.CugaComponent)
    agent.input_value = "hello"
    # ``graph`` is a read-only property on Component (-> self._vertex.graph),
    # so wire the underlying _vertex instead of trying to assign graph directly.
    agent._vertex = SimpleNamespace(graph=SimpleNamespace(session_id=graph_session_id))
    agent.is_connected_to_chat_output = MagicMock(return_value=True)
    agent.get_agent_requirements = AsyncMock(return_value=(MagicMock(), [], []))
    return agent


@pytest.mark.asyncio
async def test_session_id_falls_back_to_string_uuid_when_graph_session_id_empty(captured_message_kwargs):
    """Empty graph.session_id must produce a non-empty string session_id (not a UUID object)."""
    agent = _make_agent(graph_session_id="")

    with pytest.raises(_Halt):
        await agent.message_response()

    assert "session_id" in captured_message_kwargs
    session_id = captured_message_kwargs["session_id"]
    assert isinstance(session_id, str), (
        f"Expected str (use `str(uuid.uuid4())` not bare `uuid.uuid4()`), got {type(session_id).__name__}"
    )
    assert session_id, "Generated session_id should be non-empty"


@pytest.mark.asyncio
async def test_session_id_falls_back_when_graph_session_id_none(captured_message_kwargs):
    """None graph.session_id is also covered by the `or` fallback."""
    agent = _make_agent(graph_session_id=None)

    with pytest.raises(_Halt):
        await agent.message_response()

    session_id = captured_message_kwargs["session_id"]
    assert isinstance(session_id, str)
    assert session_id


@pytest.mark.asyncio
async def test_session_id_preserved_when_graph_session_id_set(captured_message_kwargs):
    """Explicit graph.session_id wins over the auto-generated fallback."""
    agent = _make_agent(graph_session_id="caller-supplied")

    with pytest.raises(_Halt):
        await agent.message_response()

    assert captured_message_kwargs["session_id"] == "caller-supplied"
