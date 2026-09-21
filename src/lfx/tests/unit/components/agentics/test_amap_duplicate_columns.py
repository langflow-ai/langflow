"""aMap must not crash with duplicate columns when Keep Source Columns is on and the table was already mapped."""

from __future__ import annotations

import pytest
from lfx.components.agentics.amap_component import AMapComponent
from lfx.schema.dataframe import DataFrame

_SCHEMA = [
    {"name": "full_name", "description": "Full name", "type": "str", "multiple": False},
    {"name": "age_group", "description": "Age group", "type": "str", "multiple": False},
]

_GENERATED = [
    {"full_name": "Alice Updated", "age_group": "young_adult"},
    {"full_name": "Bob Updated", "age_group": "elderly"},
]


def _amap(source_rows: list[dict], *, append_to_input_columns: bool = True) -> AMapComponent:
    component = AMapComponent(_id="amap")
    component.set(
        source=DataFrame(source_rows),
        schema=_SCHEMA,
        instructions="",
        return_multiple_instances=False,
        append_to_input_columns=append_to_input_columns,
    )
    return component


def _script_llm(fake_agentics) -> None:
    fake_agentics.transduce = lambda target, _source: [target.atype(**row) for row in _GENERATED]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_llm")
class TestAMapDuplicateColumns:
    async def test_should_replace_overlapping_source_columns_with_generated_values(self, fake_agentics):
        # Arrange: a table that was already processed by aMap, so it holds the schema's columns.
        _script_llm(fake_agentics)
        component = _amap(
            [
                {"customer_id": "1", "email": "a@test.com", "full_name": "Alice Smith", "age_group": "adult"},
                {"customer_id": "2", "email": "b@test.com", "full_name": "Bob Jones", "age_group": "senior"},
            ]
        )

        # Act: without the overlap dedup, merge_states raises "got multiple values for keyword argument".
        result = await component.aMap()

        # Assert: one column per name, source-only columns kept, overlapping columns regenerated.
        assert sorted(result.columns) == ["age_group", "customer_id", "email", "full_name"]
        assert result.sort_values("customer_id").to_dict(orient="records") == [
            {"customer_id": "1", "email": "a@test.com", "full_name": "Alice Updated", "age_group": "young_adult"},
            {"customer_id": "2", "email": "b@test.com", "full_name": "Bob Updated", "age_group": "elderly"},
        ]

    async def test_should_append_generated_columns_when_source_has_no_overlap(self, fake_agentics, fake_llm):
        _script_llm(fake_agentics)
        component = _amap([{"customer_id": "1"}, {"customer_id": "2"}])

        result = await component.aMap()

        assert sorted(result.columns) == ["age_group", "customer_id", "full_name"]
        assert result["full_name"].tolist() == ["Alice Updated", "Bob Updated"]
        [(target, _source)] = fake_agentics.transductions
        assert target.transduction_type == "amap"
        assert target.llm is fake_llm

    async def test_should_return_only_generated_columns_when_keep_source_columns_is_off(self, fake_agentics):
        _script_llm(fake_agentics)
        component = _amap(
            [{"customer_id": "1", "full_name": "Alice Smith"}, {"customer_id": "2", "full_name": "Bob Jones"}],
            append_to_input_columns=False,
        )

        result = await component.aMap()

        assert sorted(result.columns) == ["age_group", "full_name"]
        assert result["full_name"].tolist() == ["Alice Updated", "Bob Updated"]
