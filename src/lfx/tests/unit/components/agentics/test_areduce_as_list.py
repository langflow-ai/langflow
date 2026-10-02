"""aReduce 'As List' must keep the items of every batch, not just the first one."""

from __future__ import annotations

import pytest
from lfx.components.agentics.areduce_component import AreduceComponent
from lfx.schema.dataframe import DataFrame

_SCHEMA = [
    {"name": "total_orders", "description": "Total orders", "type": "int", "multiple": False},
    {"name": "top_product", "description": "Top product", "type": "str", "multiple": False},
]


def _areduce(*, return_multiple_instances: bool) -> AreduceComponent:
    component = AreduceComponent(_id="areduce")
    component.set(
        source=DataFrame([{"order_id": str(i), "product": f"Widget {i % 4}"} for i in range(5)]),
        schema=_SCHEMA,
        instructions="Summarize orders per product.",
        return_multiple_instances=return_multiple_instances,
    )
    return component


def _list_state(target, items: list[dict]):
    """Build one ``ListOfTarget`` output state, the shape aReduce produces per batch with As List on."""
    item_type = target.atype.model_fields["items"].annotation.__args__[0]
    return target.atype(items=[item_type(**item) for item in items])


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_llm")
class TestAreduceAsList:
    async def test_should_collect_items_from_all_batches_not_just_the_first(self, fake_agentics):
        # Arrange: inputs beyond areduce_batch_size come back as one ListOfTarget state per batch.
        fake_agentics.transduce = lambda target, _source: [
            _list_state(
                target,
                [{"total_orders": 100, "top_product": "Widget A"}, {"total_orders": 50, "top_product": "Widget B"}],
            ),
            _list_state(
                target,
                [{"total_orders": 25, "top_product": "Widget C"}, {"total_orders": 10, "top_product": "Widget D"}],
            ),
        ]
        component = _areduce(return_multiple_instances=True)

        # Act
        result = await component.aReduce()

        # Assert: flattening only output[0].items would silently drop Widget C and D.
        assert result.to_dict(orient="records") == [
            {"total_orders": 100, "top_product": "Widget A"},
            {"total_orders": 50, "top_product": "Widget B"},
            {"total_orders": 25, "top_product": "Widget C"},
            {"total_orders": 10, "top_product": "Widget D"},
        ]
        [(target, _source)] = fake_agentics.transductions
        assert target.transduction_type == "areduce"
        assert target.instructions.endswith("Summarize orders per product.")

    async def test_should_flatten_a_single_batch(self, fake_agentics):
        fake_agentics.transduce = lambda target, _source: [
            _list_state(
                target,
                [
                    {"total_orders": 42, "top_product": "Electronics"},
                    {"total_orders": 15, "top_product": "Books"},
                    {"total_orders": 8, "top_product": "Clothing"},
                ],
            )
        ]
        component = _areduce(return_multiple_instances=True)

        result = await component.aReduce()

        assert result["top_product"].tolist() == ["Electronics", "Books", "Clothing"]

    async def test_should_return_the_aggregate_row_when_as_list_is_off(self, fake_agentics):
        fake_agentics.transduce = lambda target, _source: [target.atype(total_orders=5, top_product="Widget 1")]
        component = _areduce(return_multiple_instances=False)

        result = await component.aReduce()

        assert result.to_dict(orient="records") == [{"total_orders": 5, "top_product": "Widget 1"}]
        [(target, _source)] = fake_agentics.transductions
        assert target.instructions == "Summarize orders per product."
