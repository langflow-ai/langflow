"""Usage must be present in the final stored and published message."""

from unittest.mock import Mock

import pytest
from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from lfx.base.agents.events import AgentPausedError, ExceptionWithMessageError, process_agent_events
from lfx.base.agents.token_callback import TokenUsageCallbackHandler
from lfx.schema.message import Message
from lfx.schema.properties import Usage


async def _empty_stream():
    for event in ():
        yield event


@pytest.mark.parametrize("has_usage", [True, False])
@pytest.mark.parametrize("stored", [True, False])
async def test_final_persist_and_event_have_usage_without_a_second_write(has_usage, stored):
    usage = Usage(input_tokens=3, output_tokens=4, total_tokens=7) if has_usage else None
    persisted = []
    published = []

    async def store_and_publish(*, message, skip_db_update=False):
        if stored:
            message.id = "stored-id"
        snapshot = Message(**message.model_dump())
        if stored and not skip_db_update:
            persisted.append(snapshot)
        published.append(snapshot)
        return message

    result = await process_agent_events(
        _empty_stream(),
        Message(text="answer"),
        store_and_publish,
        get_final_usage=lambda: usage,
    )
    assert len(published) == 2
    assert len(persisted) == (2 if stored else 0)
    assert published[0].properties.state == "partial"
    assert published[0].properties.usage is None
    assert published[-1].properties.state == "complete"
    assert published[-1].properties.usage == usage
    assert published[-1].properties.usage == usage
    assert result.text == "answer"
    assert result.properties.usage == usage


async def test_usage_is_read_after_all_model_calls_complete():
    handler = TokenUsageCallbackHandler()

    async def models():
        for input_tokens, output_tokens in [(3, 4), (5, 6)]:
            output = AIMessage(
                content="answer",
                usage_metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            )
            handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=output)]]))
            yield {"event": "on_chat_model_end", "data": {"output": output}}

    persisted = []

    async def store(*, message, skip_db_update=False):
        message.id = "stored-id"
        if not skip_db_update:
            persisted.append(Message(**message.model_dump()))
        return message

    result = await process_agent_events(models(), Message(text=""), store, get_final_usage=handler.get_usage)
    assert len(persisted) == 2
    expected = Usage(input_tokens=8, output_tokens=10, total_tokens=18)
    assert persisted[-1].properties.usage == result.properties.usage == expected


async def test_interruption_does_not_publish_a_complete_message_or_read_final_usage():
    get_usage = Mock(return_value=Usage(input_tokens=3, output_tokens=4, total_tokens=7))
    snapshots = []
    request = {"action_requests": [{"name": "tool", "args": {}}]}

    async def store(*, message, **_kwargs):
        message.id = "stored-id"
        snapshots.append(Message(**message.model_dump()))
        return message

    async def pending():
        return request

    with pytest.raises(AgentPausedError) as caught:
        await process_agent_events(
            _empty_stream(), Message(text=""), store, get_pending_interrupt=pending, get_final_usage=get_usage
        )
    assert caught.value.request == request
    assert caught.value.agent_message.get_id() == "stored-id"
    assert len(snapshots) == 1
    assert snapshots[0].properties.state == "partial"
    get_usage.assert_not_called()


async def test_failure_keeps_partial_message_for_the_existing_cleanup_path():
    get_usage = Mock(return_value=Usage(input_tokens=3, output_tokens=4, total_tokens=7))
    snapshots = []

    async def failed_stream():
        error = "model failed"
        raise ValueError(error)
        yield

    async def store(*, message, **_kwargs):
        message.id = "stored-id"
        snapshots.append(Message(**message.model_dump()))
        return message

    with pytest.raises(ExceptionWithMessageError) as caught:
        await process_agent_events(failed_stream(), Message(text=""), store, get_final_usage=get_usage)
    assert caught.value.agent_message.get_id() == "stored-id"
    assert caught.value.message == "model failed"
    assert len(snapshots) == 1
    assert snapshots[0].properties.state == "partial"
    get_usage.assert_not_called()


async def test_first_complete_event_from_agent_finish_already_contains_final_usage():
    """Consumers can stop at the first complete event without losing token counts."""
    expected = Usage(input_tokens=3, output_tokens=4, total_tokens=7)
    published = []
    reads = []

    async def finished_stream():
        yield {"event": "on_chain_end", "data": {"output": AgentFinish(return_values={"output": "answer"}, log="")}}

    async def store(*, message, **_kwargs):
        message.id = "stored-id"
        published.append(Message(**message.model_dump()))
        return message

    def final_usage():
        assert all(message.properties.state == "partial" for message in published)
        reads.append(True)
        return expected

    result = await process_agent_events(finished_stream(), Message(text="answer"), store, get_final_usage=final_usage)
    complete = [message for message in published if message.properties.state == "complete"]
    assert reads == [True]
    assert len(published) == 2
    assert len(complete) == 1
    assert complete[0].properties.usage == expected
    assert result.properties.usage == expected
