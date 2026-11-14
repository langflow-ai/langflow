"""Loop feedback must use the connected output of a multi-output component."""

import pytest
from lfx.base.flow_controls.loop_utils import extract_loop_output
from lfx.components.flow_controls.loop import LoopComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class _TwoOutputs(Component):
    """Expose distinguishable feedback outputs and an optional second dependency."""

    display_name = "Two Outputs"
    name = "TwoOutputs"
    inputs = [
        HandleInput(name="row", display_name="Row", input_types=["Data"]),
        HandleInput(name="dependency", display_name="Dependency", input_types=["Data"], required=False),
    ]
    outputs = [
        Output(name="first", display_name="First", method="build_first", group_outputs=True),
        Output(name="second", display_name="Second", method="build_second", group_outputs=True),
    ]

    def build_first(self) -> Data:
        """Return the first output with a recognizable prefix."""
        return Data(text=f"first:{self.row.text}")

    def build_second(self) -> Data:
        """Return the second output with a recognizable prefix."""
        return Data(text=f"second:{self.row.text}")


@pytest.mark.parametrize("output_name", ["first", "second"])
@pytest.mark.parametrize("done_connected", [False, True])
async def test_loop_aggregates_connected_feedback_output(output_name, done_connected):
    """Select the feedback edge output with and without a Done consumer."""
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


@pytest.mark.parametrize("done_connected", [False, True])
async def test_loop_builds_feedback_output_with_another_output_edge(done_connected):
    """A retained first-output edge must not suppress the second feedback output."""
    loop = LoopComponent(_id="loop")
    loop.set(data=DataFrame([Data(text="one"), Data(text="two")]))
    body = _TwoOutputs(_id="TwoOutputs-body")
    body.set(row=loop.item_output)
    observer = _TwoOutputs(_id="TwoOutputs-observer")
    observer.set(row=loop.item_output, dependency=body.build_first)
    loop.set(item=body.build_second)
    if done_connected:
        sink = LoopComponent(_id="sink")
        sink.set(data=loop.done_output)
        graph = Graph(loop, sink)
    else:
        graph = Graph(loop, observer)

    results = [result async for result in graph.async_start()]

    assert all(result.valid for result in results if hasattr(result, "valid"))
    assert [row.text for row in (await loop.done_output()).to_data_list()] == ["second:one", "second:two"]


async def test_extract_loop_output_rejects_missing_feedback_name():
    """A missing explicit name must not turn built output data into an empty row."""
    body = _TwoOutputs(_id="TwoOutputs-body", row=Data(text="one"))
    results = [result async for result in Graph(body, body).async_start()]

    with pytest.raises(ValueError, match="Loop feedback output 'removed' not found"):
        extract_loop_output(results, "TwoOutputs-body", "removed")


@pytest.mark.parametrize(
    ("output_name", "expected"),
    [(None, "first:one"), ("first", "first:one"), ("second", "second:one")],
)
async def test_extract_loop_output_preserves_named_and_two_argument_calls(output_name, expected):
    """Legacy two-argument callers keep the first-output fallback."""
    body = _TwoOutputs(_id="TwoOutputs-body", row=Data(text="one"))
    results = [result async for result in Graph(body, body).async_start()]

    if output_name is None:
        output = extract_loop_output(results, "TwoOutputs-body")
    else:
        output = extract_loop_output(results, "TwoOutputs-body", output_name)
    assert output.text == expected
