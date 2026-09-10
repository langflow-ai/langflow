"""Serving-plane anonymous runs are ephemeral: astore_message must not persist.

The end-user scoping marks an anonymous run's graph ``persist_messages = False``;
``get_instance_results`` binds that onto the ambient ``should_persist_messages``
flag per component execution, and ``astore_message`` honors it by returning the
message without writing a row. Identified/normal runs (the True default) persist
exactly as before.
"""

from uuid import uuid4

import pytest
from langflow.api.v2.workflow import _parse_persisted_workflow_request
from langflow.memory import aget_messages, astore_message
from langflow.schema.message import Message
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.memory.flow_context import reset_messages_persist, set_messages_persist
from lfx.schema.workflow import WorkflowRunRequest


def _msg(session_id: str) -> Message:
    return Message(text="remember me", sender="User", sender_name="User", session_id=session_id)


async def test_astore_message_persists_by_default(client):  # noqa: ARG001
    session_id = f"persist-{uuid4()}"
    await astore_message(_msg(session_id))
    stored = await aget_messages(session_id=session_id)
    assert [m.text for m in stored] == ["remember me"]


async def test_astore_message_skips_write_when_not_persisting(client):  # noqa: ARG001
    session_id = f"ephemeral-{uuid4()}"
    token = set_messages_persist(persist=False)
    try:
        returned = await astore_message(_msg(session_id))
    finally:
        reset_messages_persist(token)

    # The caller still gets its message back (in-run behavior unchanged)...
    assert [m.text for m in returned] == ["remember me"]
    # ...but nothing was persisted.
    assert await aget_messages(session_id=session_id) == []


async def test_flag_resets_after_run(client):  # noqa: ARG001
    session_id = f"reset-{uuid4()}"
    token = set_messages_persist(persist=False)
    reset_messages_persist(token)
    # Back to the default: persistence works again.
    await astore_message(_msg(session_id))
    assert len(await aget_messages(session_id=session_id)) == 1


async def test_anonymous_graph_run_persists_nothing_end_to_end(client):  # noqa: ARG001
    """A graph marked non-persisting runs ChatInput->ChatOutput but writes no memory."""
    session_id = f"anon-e2e-{uuid4()}"
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi there")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)

    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()))
    graph.session_id = session_id
    graph.persist_messages = False  # anonymous / ephemeral

    async for _ in graph.async_start():
        pass

    # ChatInput/ChatOutput default should_store_message=True, but the ephemeral
    # flag must have suppressed every write.
    assert await aget_messages(session_id=session_id) == []


async def test_nested_default_graph_cannot_reenable_persistence(client):  # noqa: ARG001
    """The binding is monotonically restrictive (review B3).

    Nested graphs built with ``Graph.from_payload`` (Run Flow, Sub Flow, Flow as
    Tool, A2A) default ``persist_messages = True``. Under an ephemeral outer run
    that default must not overwrite the ambient no-persist decision — modeled here
    by running a default-persisting graph inside an outer ephemeral binding.
    """
    session_id = f"nested-anon-{uuid4()}"
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi there")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)

    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()))
    graph.session_id = session_id
    # NOTE: graph.persist_messages stays at its True default, like a nested
    # Graph.from_payload graph inside an anonymous outer run.

    token = set_messages_persist(persist=False)  # the outer run's decision
    try:
        async for _ in graph.async_start():
            pass
    finally:
        reset_messages_persist(token)

    assert await aget_messages(session_id=session_id) == []


async def test_memory_component_store_does_not_crash_on_ephemeral_run(client):  # noqa: ARG001
    """Memory component (store mode) must degrade gracefully, not crash.

    Its store path does a write-then-read-back and raises when the read-back is
    empty — which is exactly what an ephemeral run produces. The component must
    return the in-run message instead of crashing the flow.
    """
    from lfx.components.models_and_agents.memory import MemoryComponent

    session_id = f"memcomp-anon-{uuid4()}"
    component = MemoryComponent(_id="memory")
    component.set(
        mode="Store",
        message="remember me",
        session_id=session_id,
        sender="User",
        sender_name="User",
    )

    token = set_messages_persist(persist=False)
    try:
        stored = await component.store_message()
    finally:
        reset_messages_persist(token)

    assert stored.text == "remember me"
    assert await aget_messages(session_id=session_id) == []


async def test_update_stored_message_is_noop_on_ephemeral_run(client):  # noqa: ARG001
    """Streaming finalization must not require a DB row on ephemeral runs.

    ``_update_stored_message`` is called at the end of token streaming; on an
    ephemeral run the message was never stored (no id), so the update must be a
    no-op instead of raising "Message with id None not found".
    """
    component = ChatOutput(_id="chat_output")
    message = _msg(f"ephemeral-update-{uuid4()}")

    token = set_messages_persist(persist=False)
    try:
        result = await component._update_stored_message(message)
    finally:
        reset_messages_persist(token)

    assert result.text == "remember me"


async def test_send_message_skip_db_update_allows_ephemeral_unstored(client, monkeypatch):  # noqa: ARG001
    """Agent token streaming uses send_message(skip_db_update=True) per chunk.

    Ephemeral messages never have an id, so the "must already have an ID" guard
    must not fire when persistence is off — otherwise any anonymous run with an
    Agent component crashes mid-stream.
    """
    component = ChatOutput(_id="chat_output")
    monkeypatch.setattr(component, "_should_skip_message", lambda _msg: False)
    message = _msg(f"ephemeral-skipdb-{uuid4()}")

    token = set_messages_persist(persist=False)
    try:
        result = await component.send_message(message, skip_db_update=True)
    finally:
        reset_messages_persist(token)

    assert result.text == "remember me"
    assert not result.has_id()


# --- background / resume round-trip -------------------------------------------
# The background and HITL-resume paths persist the request and re-parse it on the
# worker. persist_messages is an internal decision, not a client wire field, so it
# must survive that round-trip or an anonymous background run would wrongly persist.


def _bg_request(session_id: str, **extra) -> dict:
    return {
        "flow_id": str(uuid4()),
        "mode": "background",
        "input_value": "hi",
        "session_id": session_id,
        **extra,
    }


def test_workflow_run_request_forbids_persist_messages_extra():
    # Guards why the pop is required: WorkflowRunRequest rejects the internal field.
    with pytest.raises(Exception, match=r"persist_messages|extra"):
        WorkflowRunRequest(**_bg_request("s", persist_messages=False))


def test_background_reparse_preserves_anonymous_no_persist():
    parsed = _parse_persisted_workflow_request(_bg_request("anon-1", persist_messages=False))
    assert parsed.persist_messages is False
    assert parsed.session_id == "anon-1"


def test_background_reparse_preserves_identified_merged_session():
    parsed = _parse_persisted_workflow_request(_bg_request("alice::chat-1", persist_messages=True))
    assert parsed.session_id == "alice::chat-1"
    assert parsed.persist_messages is True


def test_background_reparse_defaults_persist_true_for_legacy_rows():
    # A persisted request written before the field existed must default to persist.
    parsed = _parse_persisted_workflow_request(_bg_request("s"))
    assert parsed.persist_messages is True


def test_workflow_run_request_forbids_end_user_id_extra():
    # Guards why the pop is required: end_user_id is internal, not a wire field.
    with pytest.raises(Exception, match=r"end_user_id|extra"):
        WorkflowRunRequest(**_bg_request("s", end_user_id="alice"))


def test_background_reparse_carries_end_user_id():
    # An identified background/resume run must keep its end user on the worker so
    # memory stamps the end user, not the SID.
    parsed = _parse_persisted_workflow_request(_bg_request("alice::chat-1", end_user_id="alice"))
    assert parsed.end_user_id == "alice"
    assert parsed.session_id == "alice::chat-1"


def test_background_reparse_defaults_end_user_id_none_for_legacy_rows():
    # A persisted request written before the field existed must default to no end user.
    parsed = _parse_persisted_workflow_request(_bg_request("s"))
    assert parsed.end_user_id is None


async def test_identified_graph_run_persists_end_to_end(client):  # noqa: ARG001
    """The same graph with the default (persist=True) does write memory."""
    session_id = f"ident-e2e-{uuid4()}"
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi there")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)

    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()))
    graph.session_id = session_id
    # persist_messages defaults True

    async for _ in graph.async_start():
        pass

    assert len(await aget_messages(session_id=session_id)) >= 1


async def test_identified_run_stamps_message_owner_with_end_user(client):  # noqa: ARG001
    """On the serving plane the stored message.user_id is the END USER, not the SID.

    Write and read both resolve through resolve_message_owner_id, so a run whose graph
    carries end_user_id stamps messages to the end user: querying by the end-user id
    returns them, and querying by the service-account id (SID) returns nothing.
    """
    sid, uid = uuid4(), uuid4()
    session_id = f"uid-stamp-{uuid4()}"
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi there")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)

    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()), user_id=str(sid))
    graph.session_id = session_id
    graph.end_user_id = str(uid)  # serving-plane end user wins over the SID

    async for _ in graph.async_start():
        pass

    assert len(await aget_messages(session_id=session_id, user_id=uid)) >= 1
    assert await aget_messages(session_id=session_id, user_id=sid) == []


async def test_non_uuid_end_user_stamps_derived_owner_end_to_end(client):  # noqa: ARG001
    """A non-UUID end-user id maps to a stable derived UUID for message.user_id.

    The UUID-typed column cannot hold "alice", so the write derives a stable uuid5;
    the read resolves the same derivation, so retrieval by the derived id returns the
    rows (per-user separation preserved) while the SID sees nothing.
    """
    from lfx.memory.flow_context import derive_message_owner_uuid

    sid = uuid4()
    session_id = f"uid-derive-{uuid4()}"
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="hi there")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)

    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()), user_id=str(sid))
    graph.session_id = session_id
    graph.end_user_id = "alice"  # opaque, non-UUID gateway id

    async for _ in graph.async_start():
        pass

    assert len(await aget_messages(session_id=session_id, user_id=derive_message_owner_uuid("alice"))) >= 1
    assert await aget_messages(session_id=session_id, user_id=sid) == []
