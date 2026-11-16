from uuid import uuid4

import pytest
from langchain_core.messages import AIMessageChunk
from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message


@pytest.mark.asyncio
@pytest.mark.parametrize("async_stream", [False, True])
@pytest.mark.parametrize("content_blocks", [False, True])
async def test_stream_extracts_text_and_usage(async_stream, content_blocks):
    component = Component()
    tokens = []

    class EventManager:
        def on_message(self, data):
            pass

        def on_token(self, data):
            tokens.append(data)

    component.set_event_manager(EventManager())
    message = Message(id=uuid4(), text="", sender="Machine")
    chunks = [
        AIMessageChunk(content=[] if content_blocks else ""),
        AIMessageChunk(
            content=[{"type": "reasoning_content", "reasoning_content": {"text": "private reasoning"}}]
            if content_blocks
            else ""
        ),
        AIMessageChunk(content=[{"type": "text", "text": "po", "index": 0}] if content_blocks else "po"),
        AIMessageChunk(content=["n", {"type": "text", "text": "g", "index": 0}] if content_blocks else "ng"),
        AIMessageChunk(
            content=[] if content_blocks else "",
            usage_metadata={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
        ),
    ]

    async def generate():
        for chunk in chunks:
            yield chunk

    iterator = generate() if async_stream else iter(chunks)
    text, usage = await component._stream_message(iterator, message)

    assert text == "pong"
    assert [token["chunk"] for token in tokens] == ["", "", "po", "ng", ""]
    assert all(token["id"] == str(message.id) for token in tokens)
    assert usage.input_tokens == 4
    assert usage.output_tokens == 2
    assert usage.total_tokens == 6
