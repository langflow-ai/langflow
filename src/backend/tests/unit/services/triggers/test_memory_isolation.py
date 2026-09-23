"""Provider session collisions cannot read or clear another flow's memory."""

from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langflow.memory import LCBuiltinChatMemory

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("explicit_owner", [False, True])
async def test_provider_session_memory_is_scoped_for_reads_writes_and_clear(client, explicit_owner):  # noqa: ARG001
    session_id = f"slack:shared:{uuid4()}"
    owner_id = uuid4() if explicit_owner else None
    first = LCBuiltinChatMemory(str(uuid4()), session_id, user_id=owner_id)
    second = LCBuiltinChatMemory(str(uuid4()), session_id, user_id=owner_id)
    await first.aadd_messages([HumanMessage(content="first flow")])
    await second.aadd_messages([HumanMessage(content="second flow")])
    assert [message.content for message in await first.aget_messages()] == ["first flow"]
    assert [message.content for message in await second.aget_messages()] == ["second flow"]
    await first.aclear()
    assert await first.aget_messages() == []
    assert [message.content for message in await second.aget_messages()] == ["second flow"]


async def test_provider_session_memory_is_scoped_to_the_executing_owner(client):  # noqa: ARG001
    flow_id, session_id = str(uuid4()), f"slack:shared-owner:{uuid4()}"
    first = LCBuiltinChatMemory(flow_id, session_id, user_id=uuid4())
    second = LCBuiltinChatMemory(flow_id, session_id, user_id=uuid4())
    await first.aadd_messages([HumanMessage(content="first owner")])
    await second.aadd_messages([HumanMessage(content="second owner")])
    assert [message.content for message in await first.aget_messages()] == ["first owner"]
    await first.aclear()
    assert [message.content for message in await second.aget_messages()] == ["second owner"]
