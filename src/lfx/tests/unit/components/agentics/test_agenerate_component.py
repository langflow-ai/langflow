"""aGenerate builds synthetic rows from an example table or from a schema."""

from __future__ import annotations

import pytest
from lfx.components.agentics.agenerate_component import AgenerateComponent
from lfx.schema.dataframe import DataFrame

_EXAMPLES = [{"name": "Ada", "age": 36}, {"name": "Alan", "age": 41}]


def _agenerate(**inputs) -> AgenerateComponent:
    component = AgenerateComponent(_id="agenerate")
    component.set(instructions="", batch_size=2, **inputs)
    return component


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_llm")
class TestAgenerateComponent:
    async def test_should_append_generated_rows_to_the_example_table(self, fake_agentics):
        fake_agentics.generate = lambda atype, _n: [atype(name="Grace", age=85), atype(name="Linus", age=54)]
        component = _agenerate(source=DataFrame(_EXAMPLES))

        result = await component.aGenerate()

        assert result.to_dict(orient="records") == [
            *_EXAMPLES,
            {"name": "Grace", "age": 85},
            {"name": "Linus", "age": 54},
        ]
        [call] = fake_agentics.generate_calls
        assert call["n_instances"] == 2
        assert sorted(call["atype"].model_fields) == ["age", "name"]
        assert "Here are examples to take inspiration from" in call["instructions"]
        assert "Ada" in call["instructions"]

    async def test_should_keep_only_the_examples_when_the_generator_returns_nothing(self, fake_agentics):
        fake_agentics.generate = lambda _atype, _n: None
        component = _agenerate(source=DataFrame(_EXAMPLES))

        result = await component.aGenerate()

        assert result.to_dict(orient="records") == _EXAMPLES

    async def test_should_generate_from_the_schema_when_no_example_table_is_given(self, fake_agentics, fake_llm):
        fake_agentics.generate = lambda atype, _n: [atype(customer="Acme", tier="gold")]
        component = _agenerate(
            schema=[
                {"name": "customer", "description": "Customer name", "type": "str", "multiple": False},
                {"name": "tier", "description": "Loyalty tier", "type": "str", "multiple": False},
            ]
        )

        result = await component.aGenerate()

        assert result.to_dict(orient="records") == [{"customer": "Acme", "tier": "gold"}]
        [call] = fake_agentics.generate_calls
        assert call["atype"].__name__ == "GeneratedData"
        assert call["llm"] is fake_llm
        assert call["instructions"] == "Generate realistic synthetic data following the provided schema."
