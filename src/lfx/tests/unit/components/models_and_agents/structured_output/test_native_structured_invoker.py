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

    async def ainvoke(self, messages: Any) -> Any:
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
