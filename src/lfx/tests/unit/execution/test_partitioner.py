from lfx.components.input_output import ChatInput, ChatOutput
from lfx.execution.partitioner import identity_partition
from lfx.execution.types import Unit
from lfx.graph import Graph


def _simple_graph():
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(input_value="test", _id="chat_output")
    chat_output.set(sender_name=chat_input.message_response)
    return Graph(chat_input, chat_output)


def test_identity_partition_returns_one_unit():
    graph = _simple_graph()
    units = identity_partition(graph, inputs=[{"input_value": "hi"}], runtime_options={"session_id": "s1"})
    assert len(units) == 1
    [unit] = units
    assert isinstance(unit, Unit)
    assert unit.graph is graph
    assert unit.inputs == [{"input_value": "hi"}]
    assert unit.runtime_options == {"session_id": "s1"}


def test_identity_partition_default_runtime_options():
    units = identity_partition(_simple_graph(), inputs=[])
    assert units[0].runtime_options == {}
