"""Provider session collisions cannot read or clear another flow's memory."""

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import HumanMessage
from langflow.memory import LCBuiltinChatMemory
from lfx.memory.flow_context import (
    reset_current_flow_id,
    reset_current_message_owner_id,
    set_current_flow_id,
    set_current_message_owner_id,
)

pytestmark = pytest.mark.no_blockbuster


@contextmanager
def _executing(flow_id: UUID, owner_id: UUID):
    """Bind the flow and message owner a trigger dispatch gives the graph it runs."""
    flow_token = set_current_flow_id(flow_id)
    owner_token = set_current_message_owner_id(owner_id)
    try:
        yield
    finally:
        reset_current_message_owner_id(owner_token)
        reset_current_flow_id(flow_token)


async def test_provider_session_memory_is_scoped_for_reads_writes_and_clear(client):  # noqa: ARG001
    session_id = f"slack:shared:{uuid4()}"
    owner_id, first_flow, second_flow = uuid4(), uuid4(), uuid4()
    first = LCBuiltinChatMemory(str(first_flow), session_id, user_id=owner_id)
    second = LCBuiltinChatMemory(str(second_flow), session_id, user_id=owner_id)
    with _executing(first_flow, owner_id):
        await first.aadd_messages([HumanMessage(content="first flow")])
    with _executing(second_flow, owner_id):
        await second.aadd_messages([HumanMessage(content="second flow")])
    with _executing(first_flow, owner_id):
        assert [message.content for message in await first.aget_messages()] == ["first flow"]
    with _executing(second_flow, owner_id):
        assert [message.content for message in await second.aget_messages()] == ["second flow"]
    with _executing(first_flow, owner_id):
        await first.aclear()
        assert await first.aget_messages() == []
    with _executing(second_flow, owner_id):
        assert [message.content for message in await second.aget_messages()] == ["second flow"]


async def test_provider_session_memory_is_scoped_to_the_executing_owner(client):  # noqa: ARG001
    flow_id, session_id = uuid4(), f"slack:shared-owner:{uuid4()}"
    first_owner, second_owner = uuid4(), uuid4()
    first = LCBuiltinChatMemory(str(flow_id), session_id, user_id=first_owner)
    second = LCBuiltinChatMemory(str(flow_id), session_id, user_id=second_owner)
    with _executing(flow_id, first_owner):
        await first.aadd_messages([HumanMessage(content="first owner")])
    with _executing(flow_id, second_owner):
        await second.aadd_messages([HumanMessage(content="second owner")])
    with _executing(flow_id, first_owner):
        assert [message.content for message in await first.aget_messages()] == ["first owner"]
        await first.aclear()
    with _executing(flow_id, second_owner):
        assert [message.content for message in await second.aget_messages()] == ["second owner"]
