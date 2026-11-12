"""Tests for invoke_with_native_structured_output — uses llm.with_structured_output() directly."""

from __future__ import annotations

from typing import Any

import pytest
from lfx.components.models_and_agents.structured_output.native_structured_invoker import (
    invoke_with_native_structured_output,
)
from pydantic import BaseModel


class _Person(BaseModel):
    name: str
    age: int


class _StructuredRunnable:
    """Stub for what llm.with_structured_output(model) returns — exposes ainvoke."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.last_input: Any = None

    async def ainvoke(self, messages: Any, **_kwargs) -> Any:
        self.last_input = messages
        return self._payload


class _NativeLLMStub:
    """Stub LLM that supports with_structured_output."""

    def __init__(self, payload: Any) -> None:
        self._runnable = _StructuredRunnable(payload)
        self.requested_schema: type[BaseModel] | None = None

    def with_structured_output(self, schema: type[BaseModel]) -> _StructuredRunnable:
        self.requested_schema = schema
        return self._runnable


async def test_agent_native_structured_output_keeps_tracing_callbacks(monkeypatch):
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.runnables import RunnableLambda
    from lfx.components.models_and_agents.agent import AgentComponent

    class _StructuredChatModel(FakeListChatModel):
        def with_structured_output(self, schema, **_kwargs):
            return self | RunnableLambda(lambda message: schema.model_validate_json(message.content))

    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.model_runs = []

        def on_chat_model_start(self, _serialized, _messages, *, run_id, **_kwargs):
            self.model_runs.append(run_id)

    llm = _StructuredChatModel(responses=['{"objects": [{"name": "Alice", "age": 30}]}'])
    callback = _RecordingCallback()

    async def _requirements(_self):
        return llm, [], []

    monkeypatch.setattr(AgentComponent, "get_agent_requirements", _requirements)
    monkeypatch.setattr(AgentComponent, "get_langchain_callbacks", lambda _self: [callback])
    agent = AgentComponent()
    agent.input_value = "Alice is 30 years old."
    agent.system_prompt = "Extract people."
    agent.output_schema = [
        {"name": "name", "type": "str", "multiple": False},
        {"name": "age", "type": "int", "multiple": False},
    ]

    result = await agent.json_response()

    assert result.data == {"name": "Alice", "age": 30}
    assert len(callback.model_runs) == 1


@pytest.mark.unit
class TestInvokeWithNativeStructuredOutput:
    async def test_should_return_validated_dict_when_llm_returns_basemodel_instance(self):
        llm = _NativeLLMStub(payload=_Person(name="Alice", age=30))

        result = await invoke_with_native_structured_output(
            llm=llm,
            model_cls=_Person,
            system_prompt="You extract people.",
            input_value="Alice is 30 years old.",
        )

        assert result == {"name": "Alice", "age": 30}
        assert llm.requested_schema is _Person

    async def test_should_return_dict_unchanged_when_llm_returns_plain_dict(self):
        llm = _NativeLLMStub(payload={"name": "Bob", "age": 25})

        result = await invoke_with_native_structured_output(
            llm=llm,
            model_cls=_Person,
            system_prompt="prompt",
            input_value="text",
        )

        assert result == {"name": "Bob", "age": 25}

    async def test_should_return_list_of_dicts_when_llm_returns_list_of_basemodels(self):
        llm = _NativeLLMStub(payload=[_Person(name="A", age=1), _Person(name="B", age=2)])

        result = await invoke_with_native_structured_output(
            llm=llm,
            model_cls=_Person,
            system_prompt="prompt",
            input_value="text",
        )

        assert result == [{"name": "A", "age": 1}, {"name": "B", "age": 2}]

    async def test_should_serialize_list_field_when_schema_field_is_multiple(self):
        from lfx.helpers.base_model import build_model_from_schema

        schema = [
            {"name": "tags", "type": "str", "description": "tags", "multiple": True},
        ]
        model_cls = build_model_from_schema(schema)
        llm = _NativeLLMStub(payload=model_cls(tags=["python", "tdd", "pydantic"]))

        result = await invoke_with_native_structured_output(
            llm=llm,
            model_cls=model_cls,
            system_prompt="extract tags",
            input_value="The post mentioned python, tdd and pydantic.",
        )

        assert result == {"tags": ["python", "tdd", "pydantic"]}

    async def test_should_raise_type_error_when_llm_returns_unsupported_type(self):
        llm = _NativeLLMStub(payload="this is a string, not structured")

        with pytest.raises(TypeError, match="unsupported type"):
            await invoke_with_native_structured_output(
                llm=llm,
                model_cls=_Person,
                system_prompt="",
                input_value="text",
            )
