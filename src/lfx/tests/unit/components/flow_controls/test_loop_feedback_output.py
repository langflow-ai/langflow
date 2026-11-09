"""Loop feedback must use the connected output of a multi-output component."""

import pytest
from lfx.components.flow_controls.loop import LoopComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class _TwoOutputs(Component):
    display_name = "Two Outputs"
    name = "TwoOutputs"
    inputs = [HandleInput(name="row", display_name="Row", input_types=["Data"])]
    outputs = [
        Output(name="first", display_name="First", method="build_first", group_outputs=True),
        Output(name="second", display_name="Second", method="build_second", group_outputs=True),
    ]

    def build_first(self) -> Data:
        return Data(text=f"first:{self.row.text}")

    def build_second(self) -> Data:
        return Data(text=f"second:{self.row.text}")


@pytest.mark.asyncio
@pytest.mark.parametrize("output_name", ["first", "second"])
@pytest.mark.parametrize("done_connected", [False, True])
async def test_loop_aggregates_connected_feedback_output(output_name, done_connected):
    loop = LoopComponent(_id="loop")
    loop.set(data=DataFrame([Data(text="one"), Data(text="two")]))
    body = _TwoOutputs(_id="TwoOutputs-body")
    body.set(row=loop.item_output)
    loop.set(item=getattr(body, f"build_{output_name}"))
    if done_connected:
        sink = LoopComponent(_id="sink")
        sink.set(data=loop.done_output)
        graph = Graph(loop, sink)
    else:
        graph = Graph(loop, body)

    results = [result async for result in graph.async_start()]
    assert all(result.valid for result in results if hasattr(result, "valid"))
    assert [row.text for row in (await loop.done_output()).to_data_list()] == [
        f"{output_name}:one",
        f"{output_name}:two",
    ]
