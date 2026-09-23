"""Regression tests: ambient flow-scope defaults ``aget_messages`` by ``flow_id`` (issue #13059).

Langflow executes the *frozen* component ``code`` embedded in each saved flow, not the installed
library version (``lfx.interface.initialize.loading.instantiate_class`` -> ``eval_custom_component_code``).
A flow saved before PR #13087 therefore carries the old ``retrieve_messages`` that calls
``aget_messages`` WITHOUT ``flow_id`` and leaks chat history across flows on a colliding
``session_id`` — even when running on a patched server.

The engine binds the executing graph's flow and owner to ContextVars. Frozen code that
omits those parameters can still read its own history, while missing or conflicting
scope cannot fall back to a cross-tenant query.
"""

import json
from importlib.resources import files
from typing import cast
from uuid import uuid4

import pytest
from langflow.memory import (
    LCBuiltinChatMemory,
    aadd_messages,
    adelete_messages,
    aget_messages,
    astore_message,
    aupdate_messages,
    delete_message,
)
from langflow.schema.message import Message
from lfx.components.deactivated.store_message import StoreMessageComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.custom.eval import eval_custom_component_code
from lfx.graph.graph.base import Graph
from lfx.memory.flow_context import (
    derive_message_owner_uuid,
    reset_current_flow_id,
    reset_current_message_executor_id,
    reset_current_message_owner_id,
    set_current_flow_id,
    set_current_message_executor_id,
    set_current_message_owner_id,
)
from lfx.schema.data import Data


async def _store(session_id: str, flow_id, user_id, text: str) -> None:
    msg = Message(text=text, sender="User", sender_name="User", session_id=session_id)
    await aadd_messages([msg], flow_id=flow_id, user_id=user_id)


async def test_aget_messages_defaults_flow_id_from_context(client):  # noqa: ARG001
    """The reproduction: two flows share a session_id; the ambient scope isolates them.

    Simulates old frozen code calling ``aget_messages(session_id=...)`` with no flow_id while
    Flow B's graph is executing. The ambient flow scope must prevent Flow A's row from leaking.
    """
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059"
    await _store(session_id, flow_a, user_id, "secret from A")
    await _store(session_id, flow_b, user_id, "hello from B")

    token = set_current_flow_id(flow_b)
    owner_token = set_current_message_owner_id(user_id)
    try:
        scoped = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)
        reset_current_message_owner_id(owner_token)

    assert [m.text for m in scoped] == ["hello from B"]


async def test_explicit_flow_id_cannot_override_context(client):  # noqa: ARG001
    """A component cannot use a supplied flow ID to read another flow's history."""
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-explicit"
    await _store(session_id, flow_a, user_id, "secret from A")
    await _store(session_id, flow_b, user_id, "hello from B")

    token = set_current_flow_id(flow_b)
    owner_token = set_current_message_owner_id(user_id)
    try:
        a_msgs = await aget_messages(session_id=session_id, flow_id=flow_a)
        b_msgs = await aget_messages(session_id=session_id, flow_id=flow_b)
    finally:
        reset_current_flow_id(token)
        reset_current_message_owner_id(owner_token)

    assert a_msgs == []
    assert [m.text for m in b_msgs] == ["hello from B"]


async def test_no_context_requires_explicit_flow_and_owner(client):  # noqa: ARG001
    """Trusted service reads must supply both predicates outside a graph run."""
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-legacy"
    await _store(session_id, flow_a, user_id, "secret from A")
    await _store(session_id, flow_b, user_id, "hello from B")

    unscoped = await aget_messages(session_id=session_id)
    scoped = await aget_messages(session_id=session_id, flow_id=flow_a, user_id=user_id)

    assert unscoped == []
    assert [m.text for m in scoped] == ["secret from A"]


async def test_context_accepts_string_flow_id(client):  # noqa: ARG001
    """``graph.flow_id`` is commonly a ``str``; the default path must coerce it, not crash.

    ``MessageTable.flow_id`` is UUID-typed; on SQLite comparing it to a raw string makes the
    ``Uuid`` bind processor call ``value.hex`` and raise. The default must coerce str -> UUID.
    """
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-str"
    await _store(session_id, flow_a, user_id, "secret from A")
    await _store(session_id, flow_b, user_id, "hello from B")

    token = set_current_flow_id(str(flow_b))
    owner_token = set_current_message_owner_id(user_id)
    try:
        scoped = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)
        reset_current_message_owner_id(owner_token)

    assert [m.text for m in scoped] == ["hello from B"]


async def test_invalid_context_flow_id_fails_closed(client):  # noqa: ARG001
    """A synthetic graph ID must not turn a session lookup into a global read."""
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-badctx"
    await _store(session_id, flow_a, user_id, "secret from A")
    await _store(session_id, flow_b, user_id, "hello from B")

    token = set_current_flow_id("not-a-uuid")
    owner_token = set_current_message_owner_id(user_id)
    try:
        result = await aget_messages(session_id=session_id)
    finally:
        reset_current_flow_id(token)
        reset_current_message_owner_id(owner_token)

    assert result == []


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
    """A graph with no ``flow_id`` must fail closed, not inherit the outer scope.

    If an outer flow is executing (ambient scope bound) and a nested graph without ``flow_id``
    runs a legacy memory component, neither graph may supply the missing flow scope.
    """
    flow_a = uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-shadow"
    await _store(session_id, flow_a, user_id, "SECRET_FROM_A")
    await _store(session_id, uuid4(), user_id, "hello from B")

    probe = _OldStyleMemory(_id="old_memory_shadow")
    probe.set(session_id=session_id, n_messages=100, order="Ascending")
    chat_output = ChatOutput(_id="chat_output_shadow")
    chat_output.set(input_value=probe.retrieve_messages_as_text)

    graph = Graph(probe, chat_output, user_id=str(user_id))  # no flow_id
    outer_token = set_current_flow_id(flow_a)  # simulate an outer flow still bound
    try:
        async for _ in graph.async_start():
            pass
    finally:
        reset_current_flow_id(outer_token)

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    text = rendered.text if hasattr(rendered, "text") else str(rendered)
    assert "SECRET_FROM_A" not in text
    assert "hello from B" not in text


async def test_graph_without_flow_id_keeps_chat_input_ephemeral(client):  # noqa: ARG001
    """Ad hoc graphs can render Chat Input without creating unscoped history."""
    session_id = "ad-hoc-chat-input"
    user_id = uuid4()
    chat_input = ChatInput(_id="ad_hoc_input")
    chat_input.set(input_value="ad hoc hello", session_id=session_id)
    chat_output = ChatOutput(_id="ad_hoc_output")
    chat_output.set(input_value=chat_input.message_response, session_id=session_id)
    graph = Graph(chat_input, chat_output, user_id=str(user_id))

    async for _ in graph.async_start():
        pass

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    assert rendered.text == "ad hoc hello"
    assert await aget_messages(session_id=session_id) == []


async def test_graph_execution_binds_flow_scope_end_to_end(client):  # noqa: ARG001
    """End-to-end: running Flow B's graph must not surface Flow A's message via unscoped frozen code.

    This is the real reproduction path — ``get_instance_results`` binds ``graph.flow_id`` so the
    old-style component's unscoped ``aget_messages`` call is defaulted to Flow B's scope.
    """
    flow_a, flow_b = uuid4(), uuid4()
    user_id = uuid4()
    session_id = "shared-session-13059-e2e"
    await _store(session_id, flow_a, user_id, "SECRET_FROM_A")
    await _store(session_id, flow_b, user_id, "hello from B")

    probe = _OldStyleMemory(_id="old_memory")
    probe.set(session_id=session_id, n_messages=100, order="Ascending")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=probe.retrieve_messages_as_text)

    graph = Graph(probe, chat_output, flow_id=str(flow_b), user_id=str(user_id))
    async for _ in graph.async_start():
        pass

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    text = rendered.text if hasattr(rendered, "text") else str(rendered)
    assert "SECRET_FROM_A" not in text, "Flow A's message leaked into Flow B's graph run"
    assert "hello from B" in text


@pytest.mark.parametrize("by_context", [False, True])
async def test_delete_scopes_colliding_session_or_context_to_flow_and_owner(client, by_context):  # noqa: ARG001
    victim_flow, attacker_flow = uuid4(), uuid4()
    victim_owner, attacker_owner = uuid4(), uuid4()
    session_id = f"shared-delete-{by_context}"
    context_id = f"shared-context-{by_context}"
    for flow_id, owner_id, text in (
        (victim_flow, victim_owner, "victim"),
        (attacker_flow, attacker_owner, "attacker"),
    ):
        message = Message(text=text, sender="User", sender_name="User", session_id=session_id, context_id=context_id)
        await aadd_messages(message, flow_id=flow_id, user_id=owner_id)

    selector = {"context_id": context_id} if by_context else {"session_id": session_id}
    with pytest.raises(ValueError, match="flow and message owner"):
        await adelete_messages(**selector)
    await adelete_messages(**selector, flow_id=attacker_flow, user_id=attacker_owner)

    victim = await aget_messages(session_id=session_id, flow_id=victim_flow, user_id=victim_owner)
    attacker = await aget_messages(session_id=session_id, flow_id=attacker_flow, user_id=attacker_owner)
    assert [message.text for message in victim] == ["victim"]
    assert attacker == []


async def test_graph_scope_refuses_supplied_foreign_read_and_delete(client):  # noqa: ARG001
    victim_flow, attacker_flow = uuid4(), uuid4()
    victim_owner, attacker_owner = uuid4(), uuid4()
    session_id = "shared-ambient-delete"
    await _store(session_id, victim_flow, victim_owner, "victim")
    await _store(session_id, attacker_flow, attacker_owner, "attacker")

    flow_token = set_current_flow_id(attacker_flow)
    owner_token = set_current_message_owner_id(attacker_owner)
    try:
        assert await aget_messages(session_id=session_id, flow_id=victim_flow, user_id=victim_owner) == []
        with pytest.raises(ValueError, match="flow and message owner"):
            await adelete_messages(session_id, flow_id=victim_flow, user_id=victim_owner)
        await adelete_messages(session_id)
    finally:
        reset_current_flow_id(flow_token)
        reset_current_message_owner_id(owner_token)

    victim = await aget_messages(session_id=session_id, flow_id=victim_flow, user_id=victim_owner)
    attacker = await aget_messages(session_id=session_id, flow_id=attacker_flow, user_id=attacker_owner)
    assert [message.text for message in victim] == ["victim"]
    assert attacker == []


async def test_legacy_chat_memory_requires_matching_ambient_scope(client):  # noqa: ARG001
    victim_flow, own_flow = uuid4(), uuid4()
    victim_owner, own_owner = uuid4(), uuid4()
    session_id = "shared-legacy-memory"
    await _store(session_id, victim_flow, victim_owner, "victim")
    await _store(session_id, own_flow, own_owner, "own")
    memory = LCBuiltinChatMemory(flow_id=str(own_flow), session_id=session_id)

    with pytest.raises(ValueError, match="executing flow and message owner"):
        await memory.aget_messages()

    flow_token = set_current_flow_id(own_flow)
    owner_token = set_current_message_owner_id(own_owner)
    try:
        messages = await memory.aget_messages()
        assert [message.content for message in messages] == ["own"]
        assert [message.content for message in memory.messages] == ["own"]
        foreign = LCBuiltinChatMemory(flow_id=str(victim_flow), session_id=session_id)
        with pytest.raises(ValueError, match="executing flow and message owner"):
            await foreign.aclear()
        with pytest.raises(ValueError, match="executing flow and message owner"):
            foreign.clear()
        memory.clear()
        await _store(session_id, own_flow, own_owner, "own again")
        await memory.aclear()
    finally:
        reset_current_flow_id(flow_token)
        reset_current_message_owner_id(owner_token)

    victim = await aget_messages(session_id=session_id, flow_id=victim_flow, user_id=victim_owner)
    assert [message.text for message in victim] == ["victim"]


async def test_frozen_memory_uses_serving_end_user_owner(client):  # noqa: ARG001
    flow_id, service_user = uuid4(), uuid4()
    alice_owner = derive_message_owner_uuid("alice")
    bob_owner = derive_message_owner_uuid("bob")
    session_id = "shared-end-user-memory"
    await _store(session_id, flow_id, alice_owner, "alice private history")
    await _store(session_id, flow_id, bob_owner, "bob private history")

    probe = _OldStyleMemory(_id="end_user_memory")
    probe.set(session_id=session_id, n_messages=100, order="Ascending")
    chat_output = ChatOutput(_id="end_user_chat_output")
    chat_output.set(input_value=probe.retrieve_messages_as_text)
    graph = Graph(probe, chat_output, flow_id=str(flow_id), user_id=str(service_user))
    graph.end_user_id = "alice"
    async for _ in graph.async_start():
        pass

    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    text = rendered.text if hasattr(rendered, "text") else str(rendered)
    assert "alice private history" in text
    assert "bob private history" not in text


async def test_frozen_message_store_readback_uses_serving_end_user(client):  # noqa: ARG001
    """The indexed legacy source still passes graph.user_id, not graph.end_user_id."""
    index = json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())
    code = next(
        entries["StoreMessage"]["template"]["code"]["value"]
        for _, entries in index["entries"]
        if "StoreMessage" in entries
    )
    assert "user_id_scope = graph_user_id" in code
    frozen_class = eval_custom_component_code(code)

    flow_id, executor_id = uuid4(), uuid4()
    session_id = "shared-frozen-store"
    chat_input = ChatInput(_id="frozen_store_input")
    chat_input.set(input_value="alice stored text", should_store_message=False)
    component = frozen_class(_id="frozen_store", _code=code)
    component.set(message=chat_input.message_response, session_id=session_id, sender="User", sender_name="User")
    graph = Graph(chat_input, component, flow_id=str(flow_id), user_id=str(executor_id))
    graph.end_user_id = "alice"

    async for _ in graph.async_start():
        pass

    owner_id = derive_message_owner_uuid("alice")
    stored = await aget_messages(session_id=session_id, flow_id=flow_id, user_id=owner_id)
    executor_rows = await aget_messages(session_id=session_id, flow_id=flow_id, user_id=executor_id)
    assert [message.text for message in stored] == ["alice stored text"]
    assert executor_rows == []


async def test_deactivated_message_store_fills_missing_owner_from_graph(client):  # noqa: ARG001
    """Older saved code calls astore_message without user_id, then aget_messages()."""
    flow_id, executor_id = uuid4(), uuid4()
    owner_id = derive_message_owner_uuid("alice")
    session_id = "shared-deactivated-store"
    message = Message(text="alice deactivated text", sender="User", sender_name="User", session_id=session_id)
    component = StoreMessageComponent()

    flow_token = set_current_flow_id(flow_id)
    owner_token = set_current_message_owner_id(owner_id)
    executor_token = set_current_message_executor_id(executor_id)
    try:
        await component.build(message)
        assert [stored.text for stored in component.status] == ["alice deactivated text"]
    finally:
        reset_current_flow_id(flow_token)
        reset_current_message_owner_id(owner_token)
        reset_current_message_executor_id(executor_token)

    stored = await aget_messages(session_id=session_id, flow_id=flow_id, user_id=owner_id)
    assert [row.text for row in stored] == ["alice deactivated text"]


@pytest.mark.parametrize("frozen", [False, True])
async def test_nested_chat_output_copies_child_message_into_parent_scope(client, frozen):  # noqa: ARG001
    """Saved Chat Output source overwrites flow_id but keeps the child row's ID."""
    child_flow, parent_flow, owner_id = uuid4(), uuid4(), uuid4()
    session_id = f"nested-output-{frozen}"
    child = (
        await aadd_messages(
            Message(text="child reply", sender="Machine", sender_name="AI", session_id=session_id),
            flow_id=child_flow,
            user_id=owner_id,
        )
    )[0]

    if frozen:
        index = json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())
        code = next(
            entries["ChatOutput"]["template"]["code"]["value"]
            for _, entries in index["entries"]
            if "ChatOutput" in entries
        )
        assert "message.flow_id = self.graph.flow_id" in code
        output_class = eval_custom_component_code(code)
    else:
        code = None
        output_class = ChatOutput

    output = output_class(_id=f"parent_output_{frozen}", _code=code)
    output.set(input_value=child, session_id=session_id)
    graph = Graph(output, output, flow_id=str(parent_flow), user_id=str(owner_id))
    async for _ in graph.async_start():
        pass

    child_rows = await aget_messages(session_id=session_id, flow_id=child_flow, user_id=owner_id)
    parent_rows = await aget_messages(session_id=session_id, flow_id=parent_flow, user_id=owner_id)
    assert [(row.id, row.text) for row in child_rows] == [(child.id, "child reply")]
    assert [row.text for row in parent_rows] == ["child reply"]
    assert parent_rows[0].id != child.id


async def test_graph_write_rejects_foreign_flow_and_owner(client):  # noqa: ARG001
    flow_id, executor_id, owner_id = uuid4(), uuid4(), uuid4()
    message = Message(text="blocked", sender="User", sender_name="User", session_id="foreign-write")
    flow_token = set_current_flow_id(flow_id)
    owner_token = set_current_message_owner_id(owner_id)
    executor_token = set_current_message_executor_id(executor_id)
    try:
        with pytest.raises(ValueError, match="valid matching flow and message owner"):
            await astore_message(message, flow_id=uuid4(), user_id=owner_id)
        with pytest.raises(ValueError, match="valid matching flow and message owner"):
            await aadd_messages(message, flow_id=flow_id, user_id=uuid4())
    finally:
        reset_current_flow_id(flow_token)
        reset_current_message_owner_id(owner_token)
        reset_current_message_executor_id(executor_token)

    assert await aget_messages(session_id="foreign-write", flow_id=flow_id, user_id=owner_id) == []


@pytest.mark.parametrize("foreign_dimension", ["flow", "owner"])
async def test_graph_id_operations_cannot_modify_foreign_messages(client, foreign_dimension):  # noqa: ARG001
    own_flow, own_owner = uuid4(), uuid4()
    foreign_flow = uuid4() if foreign_dimension == "flow" else own_flow
    foreign_owner = uuid4() if foreign_dimension == "owner" else own_owner
    session_id = f"id-scope-{foreign_dimension}"

    own = (
        await aadd_messages(
            Message(text="own", sender="User", sender_name="User", session_id=session_id),
            flow_id=own_flow,
            user_id=own_owner,
        )
    )[0]
    foreign = (
        await aadd_messages(
            Message(text="foreign", sender="User", sender_name="User", session_id=session_id),
            flow_id=foreign_flow,
            user_id=foreign_owner,
        )
    )[0]

    flow_token = set_current_flow_id(own_flow)
    owner_token = set_current_message_owner_id(own_owner)
    try:
        foreign.text = "overwritten"
        with pytest.raises(ValueError, match="not found"):
            await aupdate_messages(foreign)
        if foreign_dimension == "flow":
            copied = await astore_message(foreign, flow_id=own_flow, user_id=own_owner)
            assert len(copied) == 1
            assert copied[0].id != foreign.id
        else:
            with pytest.raises(ValueError, match="not found"):
                await astore_message(foreign, flow_id=own_flow, user_id=own_owner)
        unknown = Message(text="unknown", sender="User", sender_name="User", session_id=session_id)
        unknown.id = uuid4()
        with pytest.raises(ValueError, match="not found"):
            await astore_message(unknown, flow_id=own_flow, user_id=own_owner)
        await delete_message(str(foreign.id))

        own.flow_id = uuid4()
        with pytest.raises(ValueError, match="Message scope does not match"):
            await aupdate_messages(own)
        own.flow_id = own_flow
        own.text = "updated own"
        updated = await aupdate_messages(own)
        assert [message.text for message in updated] == ["updated own"]
        await delete_message(str(own.id))
    finally:
        reset_current_flow_id(flow_token)
        reset_current_message_owner_id(owner_token)

    own_rows = await aget_messages(session_id=session_id, flow_id=own_flow, user_id=own_owner)
    foreign_rows = await aget_messages(session_id=session_id, flow_id=foreign_flow, user_id=foreign_owner)
    assert [message.text for message in own_rows] == (["overwritten"] if foreign_dimension == "flow" else [])
    assert [message.text for message in foreign_rows] == ["foreign"]
