"""Regression tests for LoopComponent input/output type metadata.

Covers the bug where the Loop's ``data`` handle only declared
``input_types=["DataFrame", "Table"]`` even though the component is
documented to iterate over ``Data`` or ``Message`` objects (and ships a
``_convert_message_to_data`` helper). The missing types caused any
Message/Data-producing component (ChatInput, Agent, ...) to be rejected at
connect time, which made agent-assisted flow builders retry until they hit
the LangGraph recursion limit. See issue #13636.
"""

from lfx.components.flow_controls.loop import LoopComponent
from lfx.graph.edge.base import types_compatible
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


def _data_input(loop: LoopComponent):
    return next(i for i in loop.inputs if i.name == "data")


def _output(loop: LoopComponent, name: str):
    return next(o for o in loop.outputs if o.name == name)


def test_data_input_accepts_data_and_message():
    """The data handle must accept Data and Message alongside DataFrame/Table."""
    loop = LoopComponent()
    input_types = _data_input(loop).input_types
    assert "DataFrame" in input_types
    assert "Table" in input_types
    assert "Data" in input_types
    assert "Message" in input_types


def test_outputs_declare_types():
    """Both outputs must advertise their types so agents can plan downstream."""
    loop = LoopComponent()
    assert _output(loop, "item").types == ["Data"]
    assert _output(loop, "done").types == ["DataFrame", "Table"]


def test_message_outputs_are_connectable_to_loop():
    """A Message- or Data-producing output must be compatible with Loop.data.

    This is the connect-time check that previously failed and triggered the
    agent-builder retry loop.
    """
    loop_input = _data_input(LoopComponent()).input_types
    # ChatInput / Agent emit Message; Agent.structured_response emits Data/JSON.
    assert types_compatible(["Message"], loop_input)
    assert types_compatible(["Data", "JSON"], loop_input)
    assert types_compatible(["JSON"], loop_input)
    assert types_compatible(["DataFrame"], loop_input)


def test_validate_data_converts_message_to_clean_data():
    """A Message input is converted to a Data carrying just its payload.

    Message subclasses Data, so without the explicit conversion it would be
    accepted verbatim as a single Data object holding the whole message
    envelope (sender, session_id, timestamp, ...) instead of the payload.
    """
    loop = LoopComponent()
    validated = loop._validate_data(Message(text="hello world"))

    assert isinstance(validated, list)
    assert len(validated) == 1
    assert isinstance(validated[0], Data)
    assert validated[0].data == {"text": "hello world"}


def test_validate_data_still_handles_dataframe():
    """The existing DataFrame path is preserved."""
    loop = LoopComponent()
    validated = loop._validate_data(DataFrame([Data(text="a"), Data(text="b")]))

    assert isinstance(validated, list)
    assert len(validated) == 2
    assert all(isinstance(item, Data) for item in validated)
