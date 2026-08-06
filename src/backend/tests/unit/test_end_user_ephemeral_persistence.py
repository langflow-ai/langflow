"""Serving-plane anonymous runs are ephemeral: astore_message must not persist.

The end-user scoping marks an anonymous run's graph ``persist_messages = False``;
``get_instance_results`` binds that onto the ambient ``should_persist_messages``
flag per component execution, and ``astore_message`` honors it by returning the
message without writing a row. Identified/normal runs (the True default) persist
exactly as before.
"""

from uuid import uuid4

from langflow.memory import aget_messages, astore_message
from langflow.schema.message import Message
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.memory.flow_context import reset_messages_persist, set_messages_persist


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
