"""Real Graph/Vertex/ChatOutput propagation of zero/partial/total-only response usage."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage
from lfx.schema.properties import Usage
from lfx.schema.token_usage import extract_usage_from_message


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            Usage(input_tokens=0, output_tokens=0, total_tokens=0),
        ),
        ({"total_tokens": 13}, Usage(input_tokens=None, output_tokens=None, total_tokens=13)),
        ({"input_tokens": 3}, Usage(input_tokens=3, output_tokens=None, total_tokens=3)),
        ({}, None),
        ({"input_tokens": None, "output_tokens": None, "total_tokens": None}, None),
    ],
)
def test_preferred_metadata_preserves_zero_and_unknown(metadata, expected):
    assert extract_usage_from_message(SimpleNamespace(usage_metadata=metadata, response_metadata={})) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        (
            [
                SimpleNamespace(content="first", usage_metadata={"total_tokens": 9}, response_metadata={}),
                SimpleNamespace(content="second", usage_metadata={"total_tokens": 4}, response_metadata={}),
            ],
            Usage(input_tokens=None, output_tokens=None, total_tokens=13),
        ),
        (
            [
                AIMessage(content="first", usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}),
                AIMessage(content="second", usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}),
            ],
            Usage(input_tokens=0, output_tokens=0, total_tokens=0),
        ),
        (
            [
                SimpleNamespace(content="first", usage_metadata={"input_tokens": 3}, response_metadata={}),
                SimpleNamespace(content="second", usage_metadata={"input_tokens": 5}, response_metadata={}),
            ],
            Usage(input_tokens=8, output_tokens=None, total_tokens=8),
        ),
        ([AIMessage(content="first"), AIMessage(content="second")], None),
    ],
)
async def test_real_graph_final_message_event_and_persistence_keep_usage(monkeypatch, responses, expected):
    from lfx.base.models import unified_models
    from lfx.components.input_output.chat_output import ChatOutput
    from lfx.components.llm_operations import batch_run
    from lfx.custom.custom_component.component import Component
    from lfx.graph import Graph
    from lfx.schema.dataframe import DataFrame
    from lfx.schema.message import Message

    model = SimpleNamespace(abatch=AsyncMock(return_value=responses), with_config=Mock())
    model.with_config.return_value = model
    factory = AsyncMock(return_value=model)
    monkeypatch.setattr(batch_run, "aget_llm", factory)
    monkeypatch.setattr(unified_models, "aget_llm", factory)
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy",
        AsyncMock(return_value=SimpleNamespace(require=Mock())),
    )
    monkeypatch.setattr(Component, "get_project_name", Mock(return_value=None))
    monkeypatch.setattr(Component, "get_langchain_callbacks", Mock(return_value=[]))
    batch = batch_run.BatchRunComponent(
        _id="batch", model=[{"name": "test-model", "provider": "OpenAI", "metadata": {}}]
    )
    batch.set(
        df=DataFrame([{"text": "one"}, {"text": "two"}]),
        column_name="text",
        output_column_name="model_response",
        system_message="",
        enable_metadata=False,
    )
    output = ChatOutput(_id="chat-output", session_id="test-session", should_store_message=True)
    output.set(input_value=batch.run_batch)
    stored = []
    updated = []
    events = []

    async def store(_self, message, **_kwargs):
        message.id = "test-id"
        stored.append(Message(**message.model_dump()))
        return message

    async def update(_self, message):
        updated.append(Message(**message.model_dump()))
        return message

    async def event(_self, message, **_kwargs):
        events.append(Message(**message.model_dump()))

    monkeypatch.setattr(Component, "send_message", store)
    monkeypatch.setattr(Component, "_update_stored_message", update)
    monkeypatch.setattr(Component, "_send_message_event", event)
    graph = Graph(batch, output, flow_id="11111111-1111-1111-1111-111111111111")
    await graph.arun(inputs=[{}], session_id="test-session")
    batch_vertex = graph.get_vertex(batch._id)
    assert batch_vertex.result.token_usage == expected
    final_message = graph.get_vertex(output._id).result.results["message"]
    assert final_message.properties.usage == expected
    assert stored
    if expected is not None:
        assert updated[-1].properties.usage == expected
        assert events[-1].properties.usage == expected
    else:
        assert updated == []
        assert events == []
