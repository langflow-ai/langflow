"""Regression tests: ambient flow-scope defaults ``aget_messages`` by ``flow_id`` (issue #13059).

Langflow executes the *frozen* component ``code`` embedded in each saved flow, not the installed
library version (``lfx.interface.initialize.loading.instantiate_class`` -> ``eval_custom_component_code``).
A flow saved before PR #13087 therefore carries the old ``retrieve_messages`` that calls
``aget_messages`` WITHOUT ``flow_id`` and leaks chat history across flows on a colliding
``session_id`` — even when running on a patched server.

Defense-in-depth: the engine binds the executing graph's ``flow_id`` to a ContextVar so
``aget_messages`` can default the scope. This closes the leak for old frozen flows without:
- touching frozen code (impossible),
- changing callers that pass ``flow_id`` explicitly (the default only applies when it is ``None``),
- changing callers outside a graph run (the ContextVar is unset -> identical to today).
"""

from typing import cast
from uuid import uuid4

from langflow.memory import aadd_messages, aget_messages
from langflow.schema.message import Message
from lfx.components.input_output import ChatOutput
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.graph.graph.base import Graph
from lfx.memory.flow_context import reset_current_flow_id, set_current_flow_id
from lfx.schema.data import Data


async def _store(session_id: str, flow_id, text: str) -> None:
    msg = Message(text=text, sender="User", sender_name="User", session_id=session_id)
    await aadd_messages([msg], flow_id=flow_id)


async def test_aget_messages_defaults_flow_id_from_context(client):  # noqa: ARG001
    """The reproduction: two flows share a session_id; the ambient scope isolates them.

    Simulates old frozen code calling ``aget_messages(session_id=...)`` with no flow_id while
    Flow B's graph is executing. The ambient flow scope must prevent Flow A's row from leaking.
    """
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059"
    await _store(session_id, flow_a, "secret from A")
    await _store(session_id, flow_b, "hello from B")

    token = set_current_flow_id(flow_b)
    try:
        scoped = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)

    assert [m.text for m in scoped] == ["hello from B"]


async def test_explicit_flow_id_overrides_context(client):  # noqa: ARG001
    """An explicitly-passed flow_id must win over the ambient context (no silent override)."""
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059-explicit"
    await _store(session_id, flow_a, "secret from A")
    await _store(session_id, flow_b, "hello from B")

    token = set_current_flow_id(flow_b)
    try:
        a_msgs = await aget_messages(session_id=session_id, flow_id=flow_a)
    finally:
        reset_current_flow_id(token)

    assert [m.text for m in a_msgs] == ["secret from A"]


async def test_no_context_preserves_legacy_unscoped(client):  # noqa: ARG001
    """With no ambient scope and no explicit flow_id, behavior is unchanged (both rows)."""
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059-legacy"
    await _store(session_id, flow_a, "secret from A")
    await _store(session_id, flow_b, "hello from B")

    unscoped = await aget_messages(session_id=session_id)

    assert len(unscoped) == 2


async def test_context_accepts_string_flow_id(client):  # noqa: ARG001
    """``graph.flow_id`` is commonly a ``str``; the default path must coerce it, not crash.

    ``MessageTable.flow_id`` is UUID-typed; on SQLite comparing it to a raw string makes the
    ``Uuid`` bind processor call ``value.hex`` and raise. The default must coerce str -> UUID.
    """
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059-str"
    await _store(session_id, flow_a, "secret from A")
    await _store(session_id, flow_b, "hello from B")

    token = set_current_flow_id(str(flow_b))
    try:
        scoped = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)

    assert [m.text for m in scoped] == ["hello from B"]


async def test_invalid_context_flow_id_degrades_to_unscoped(client):  # noqa: ARG001
    """A non-UUID ambient flow_id (synthetic/test graphs) must degrade, never crash retrieval."""
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059-badctx"
    await _store(session_id, flow_a, "secret from A")
    await _store(session_id, flow_b, "hello from B")

    token = set_current_flow_id("not-a-uuid")
    try:
        result = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)

    assert len(result) == 2


class _OldStyleMemory(MemoryComponent):
    """Simulates a flow saved before PR #13087: its frozen ``retrieve_messages`` omits ``flow_id``.

    We cannot recreate frozen bytes in a unit test, so we reproduce the one behavior that matters:
    the internal-memory retrieve calls ``aget_messages`` with no ``flow_id``. The engine's ambient
    flow scope must still isolate it.
    """

    name = "OldStyleMemory"

    async def retrieve_messages(self) -> Data:
        from langflow.memory import aget_messages as backend_aget_messages

        stored = await backend_aget_messages(session_id=self.session_id, order="DESC")
        return cast("Data", list(reversed(stored)))


async def test_graph_without_flow_id_shadows_outer_scope(client):  # noqa: ARG001
    """A graph with no ``flow_id`` must run unscoped, not inherit an outer flow's ambient scope.

    If an outer flow is executing (ambient scope bound) and a nested graph without ``flow_id``
    runs a legacy memory component, the documented fallback is legacy *unscoped* retrieval —
    inheriting the outer flow's scope would silently attribute the messages to the wrong flow.
    """
    flow_a = uuid4()
    session_id = "shared-session-13059-shadow"
    await _store(session_id, flow_a, "SECRET_FROM_A")
    await _store(session_id, uuid4(), "hello from B")

    probe = _OldStyleMemory(_id="old_memory_shadow")
    probe.set(session_id=session_id, n_messages=100, order="Ascending")
    chat_output = ChatOutput(_id="chat_output_shadow")
    chat_output.set(input_value=probe.retrieve_messages_as_text)

    graph = Graph(probe, chat_output)  # no flow_id
    outer_token = set_current_flow_id(flow_a)  # simulate an outer flow still bound
    try:
        async for _ in graph.async_start():
            pass
    finally:
        reset_current_flow_id(outer_token)

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    text = rendered.text if hasattr(rendered, "text") else str(rendered)
    assert "SECRET_FROM_A" in text, "unscoped legacy retrieval must include Flow A's message"
    assert "hello from B" in text, "outer flow scope leaked into the flow_id-less graph run"


async def test_graph_execution_binds_flow_scope_end_to_end(client):  # noqa: ARG001
    """End-to-end: running Flow B's graph must not surface Flow A's message via unscoped frozen code.

    This is the real reproduction path — ``get_instance_results`` binds ``graph.flow_id`` so the
    old-style component's unscoped ``aget_messages`` call is defaulted to Flow B's scope.
    """
    flow_a, flow_b = uuid4(), uuid4()
    session_id = "shared-session-13059-e2e"
    await _store(session_id, flow_a, "SECRET_FROM_A")
    await _store(session_id, flow_b, "hello from B")

    probe = _OldStyleMemory(_id="old_memory")
    probe.set(session_id=session_id, n_messages=100, order="Ascending")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=probe.retrieve_messages_as_text)

    graph = Graph(probe, chat_output, flow_id=str(flow_b))
    async for _ in graph.async_start():
        pass

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    text = rendered.text if hasattr(rendered, "text") else str(rendered)
    assert "SECRET_FROM_A" not in text, "Flow A's message leaked into Flow B's graph run"
    assert "hello from B" in text
