"""Regression tests for LoopComponent input/output type metadata.

Covers the bug where the Loop's ``data`` handle only declared
``input_types=["DataFrame", "Table"]`` even though the component is
documented to iterate over ``Data`` or ``Message`` objects (and ships a
``_convert_message_to_data`` helper). The missing types caused any
Message/Data-producing component (ChatInput, Agent, ...) to be rejected at
connect time, which made agent-assisted flow builders retry until they hit
the LangGraph recursion limit. See issue #13636.

Also covers normalization of mixed-type lists in ``_validate_data`` so a
``[Message, DataFrame, Data]`` input still yields a homogeneous ``list[Data]``
instead of being rejected by ``validate_data_input``.
"""

import pytest
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
    # Must be a plain Data, not the Message passed through verbatim (Message
    # subclasses Data, so the isinstance check above is not enough on its own).
    assert not isinstance(validated[0], Message)
    assert validated[0].data == {"text": "hello world"}


def test_validate_data_still_handles_dataframe():
    """The existing DataFrame path is preserved (expanded to its rows)."""
    loop = LoopComponent()
    validated = loop._validate_data(DataFrame([Data(text="a"), Data(text="b")]))

    assert isinstance(validated, list)
    assert len(validated) == 2
    assert all(isinstance(item, Data) for item in validated)


def test_validate_data_still_handles_single_data():
    """A single Data input yields a one-item list."""
    loop = LoopComponent()
    single = Data(text="single")
    validated = loop._validate_data(single)

    assert validated == [single]


def test_validate_data_handles_list_of_messages():
    """A list of Message objects is converted item-by-item to clean Data."""
    loop = LoopComponent()
    validated = loop._validate_data([Message(text="m1"), Message(text="m2")])

    assert len(validated) == 2
    assert all(isinstance(item, Data) for item in validated)
    assert [d.data for d in validated] == [{"text": "m1"}, {"text": "m2"}]


def test_validate_data_normalizes_mixed_list():
    """A mixed [Message, DataFrame, Data] list yields a flat list[Data].

    Regression for the CodeRabbit review on #13646: converting only the
    Message items produced ``[Data, DataFrame, Data]``, which
    ``validate_data_input`` rejects because DataFrame is not a Data subclass.
    DataFrame items must be expanded to their rows so the list stays
    homogeneous.
    """
    loop = LoopComponent()
    mixed = [
        Message(text="m"),
        DataFrame([Data(text="r1"), Data(text="r2")]),
        Data(text="d"),
    ]
    validated = loop._validate_data(mixed)

    assert len(validated) == 4
    assert all(isinstance(item, Data) for item in validated)
    assert [d.data for d in validated] == [
        {"text": "m"},
        {"text": "r1"},
        {"text": "r2"},
        {"text": "d"},
    ]


def test_validate_data_rejects_invalid_input():
    """Invalid input types still raise a clear TypeError."""
    loop = LoopComponent()
    with pytest.raises(TypeError, match="must be a DataFrame"):
        loop._validate_data("not data")


def test_validate_data_rejects_list_with_non_coercible_item():
    """A list containing a non-Data/Message/DataFrame item is still rejected.

    The list branch only coerces Message and DataFrame items; anything else
    falls through unchanged and must be caught by validate_data_input so the
    documented contract (every item resolves to Data) is preserved.
    """
    loop = LoopComponent()
    with pytest.raises(TypeError, match="must be a DataFrame"):
        loop._validate_data([Data(text="ok"), "bad"])
