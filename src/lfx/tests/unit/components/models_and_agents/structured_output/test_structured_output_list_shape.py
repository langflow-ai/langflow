"""LE-2392: the Agent's structured output must be able to hold more than one record.

The Agent and the standalone Structured Output component read the SAME schema table
but built different models from it:

    Structured Output   ->  {objects: [ {country, capital}, ... ]}   a list
    Agent.json_response ->  {country, capital}                       exactly one

So asking an agent for "a list of South American countries and their capitals"
returned the whole list as text and a single record as structured output. The model
was not truncating: the schema it received declared ``country`` as a string, not an
array, so one record is all it could express. The Agent's own default
``format_instructions`` meanwhile tell it to "Extract ALL relevant instances that
match the schema", which the schema then forbids.

The reported schema is used verbatim below: two ``str`` fields with ``multiple``
false, which is what the editor writes by default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from lfx.components.models_and_agents.structured_output.structured_output_orchestrator import (
    orchestrate_structured_output,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

# Verbatim from the flow that reproduced the report.
REPORTED_SCHEMA = [
    {"name": "country", "description": "description of field", "type": "str", "multiple": "False"},
    {"name": "capital", "description": "description of field", "type": "str", "multiple": "False"},
]

COUNTRIES = [
    {"country": "Argentina", "capital": "Buenos Aires"},
    {"country": "Brasil", "capital": "Brasilia"},
    {"country": "Chile", "capital": "Santiago"},
    {"country": "Peru", "capital": "Lima"},
]


class _ListAwareLLM:
    """Fills whatever model it is handed, the way a capable provider would.

    If the schema can hold many records it returns many; if it can hold only one it
    returns one. That is what makes this test measure the SCHEMA rather than the stub.
    """

    def __init__(self) -> None:
        self.received_schema: dict[str, Any] | None = None

    def with_structured_output(self, model_cls: type[BaseModel]):
        outer = self

        class _Runnable:
            async def ainvoke(self, _messages: Any) -> Any:
                outer.received_schema = model_cls.model_json_schema()
                fields = model_cls.model_fields
                if len(fields) == 1:
                    (only_name, only_field) = next(iter(fields.items()))
                    annotation = str(only_field.annotation)
                    if annotation.startswith(("list", "typing.List")):
                        return model_cls(**{only_name: COUNTRIES})
                return model_cls(**COUNTRIES[0])

        return _Runnable()


async def _run(llm, *, prefer_native: bool):
    async def _fallback(_prompt: str) -> str:
        import json

        return json.dumps(COUNTRIES)

    return await orchestrate_structured_output(
        llm=llm,
        output_schema=REPORTED_SCHEMA,
        system_prompt="",
        format_instructions="",
        input_value="list the South American countries and their capitals",
        run_prompt_fallback=_fallback,
        prefer_native=prefer_native,
    )


def _records(data: dict) -> list[dict]:
    """Every record the payload carries, whichever shape it uses."""
    for key in ("results", "objects"):
        if isinstance(data.get(key), list):
            return data[key]
    return [data]


@pytest.mark.asyncio
async def test_native_path_can_return_more_than_one_record():
    llm = _ListAwareLLM()

    data = await _run(llm, prefer_native=True)

    records = _records(data.data)
    assert len(records) == len(COUNTRIES), f"structured output collapsed to {len(records)} record(s): {data.data}"
    assert {r["country"] for r in records} == {c["country"] for c in COUNTRIES}


@pytest.mark.asyncio
async def test_the_schema_handed_to_the_provider_accepts_a_list():
    """The provider must be OFFERED a shape that can hold many; otherwise one is correct."""
    llm = _ListAwareLLM()

    await _run(llm, prefer_native=True)

    schema = llm.received_schema
    assert schema is not None
    array_props = [name for name, prop in schema.get("properties", {}).items() if prop.get("type") == "array"]
    assert array_props, f"no array property offered to the provider: {list(schema.get('properties', {}))}"


@pytest.mark.asyncio
async def test_fallback_path_keeps_every_record():
    """The prompt fallback (agent with tools) must not drop records either."""

    class _NoNative:
        pass

    data = await _run(_NoNative(), prefer_native=False)

    records = _records(data.data)
    assert len(records) == len(COUNTRIES), f"fallback collapsed to {len(records)} record(s): {data.data}"


@pytest.mark.asyncio
async def test_fallback_preserves_a_record_field_named_objects():
    """A user field named ``objects`` must not be mistaken for the list envelope."""

    async def _fallback(_prompt: str) -> str:
        return '{"objects": ["alpha", "beta"]}'

    data = await orchestrate_structured_output(
        llm=object(),
        output_schema=[
            {"name": "objects", "description": "record values", "type": "str", "multiple": True},
        ],
        system_prompt="",
        format_instructions="",
        input_value="return the values",
        run_prompt_fallback=_fallback,
        prefer_native=False,
    )

    assert data.data == {"objects": ["alpha", "beta"]}


@pytest.mark.asyncio
async def test_a_single_record_keeps_its_flat_shape():
    """Back-compat: one record must still surface flat, not nested under a list key.

    Existing flows read fields straight off the payload; wrapping them would break
    every downstream component that already consumes this output.
    """

    class _SingleRecordLLM:
        def with_structured_output(self, model_cls: type[BaseModel]):
            class _Runnable:
                async def ainvoke(self, _messages: Any) -> Any:
                    fields = model_cls.model_fields
                    if len(fields) == 1:
                        (only_name, _) = next(iter(fields.items()))
                        return model_cls(**{only_name: [COUNTRIES[0]]})
                    return model_cls(**COUNTRIES[0])

            return _Runnable()

    data = await _run(_SingleRecordLLM(), prefer_native=True)

    assert data.data.get("country") == "Argentina", f"single record was nested: {data.data}"
    assert data.data.get("capital") == "Buenos Aires"
