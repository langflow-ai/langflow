from lfx.execution.partitioner import identity_partition
from lfx.execution.types import Unit


def test_identity_partition_returns_one_unit(simple_graph):
    units = identity_partition(simple_graph, inputs=[{"input_value": "hi"}], runtime_options={"session_id": "s1"})
    assert len(units) == 1
    [unit] = units
    assert isinstance(unit, Unit)
    assert unit.graph is simple_graph
    assert unit.inputs == [{"input_value": "hi"}]
    assert unit.runtime_options == {"session_id": "s1"}


def test_identity_partition_default_runtime_options(simple_graph):
    units = identity_partition(simple_graph, inputs=[])
    assert units[0].runtime_options == {}
