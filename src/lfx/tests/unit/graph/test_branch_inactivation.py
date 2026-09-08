from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.graph.vertex.base import VertexStates
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class Source(Component):
    display_name = "Source"
    name = "Source"
    outputs = [Output(display_name="Done", name="done", method="run")]

    def run(self) -> Message:
        return Message(text="done")


class Sink(Component):
    display_name = "Sink"
    name = "Sink"
    inputs = [MessageTextInput(name="input_value", display_name="Input", required=False)]
    outputs = [Output(display_name="Out", name="out", method="run")]

    def run(self) -> Message:
        return Message(text=str(self.input_value or ""))


def _parallel_branches() -> Graph:
    graph = Graph()
    for component_id, component in (
        ("stopper", Source(_id="stopper")),
        ("sibling", Source(_id="sibling")),
        ("victim", Sink(_id="victim")),
        ("sibling_output", Sink(_id="sibling_output")),
    ):
        graph.add_component(component, component_id)
    graph.add_component_edge("stopper", ("done", "input_value"), "victim")
    graph.add_component_edge("sibling", ("done", "input_value"), "sibling_output")
    graph.prepare()
    return graph


def test_completed_sibling_does_not_reset_another_sources_stopped_branch():
    graph = _parallel_branches()

    graph.mark_branch("stopper", VertexStates.INACTIVE, output_name="done")
    graph.reset_inactivated_vertices("sibling")

    assert graph.get_vertex("victim").state == VertexStates.INACTIVE
    assert graph.inactivated_vertices == {"victim"}

    graph.reset_inactivated_vertices("stopper")

    assert graph.get_vertex("victim").state == VertexStates.ACTIVE
    assert graph.inactivated_vertices == set()


def test_start_releases_the_sources_branch_ownership():
    graph = _parallel_branches()
    graph.mark_branch("stopper", VertexStates.INACTIVE, output_name="done")

    graph.mark_branch("stopper", VertexStates.ACTIVE, output_name="done")

    assert graph.get_vertex("victim").state == VertexStates.ACTIVE
    assert graph.inactivated_vertices == set()
    assert graph.branch_inactivation_sources == {}


def test_shared_descendant_stays_inactive_until_every_source_releases_it():
    graph = Graph()
    for component_id, component in (
        ("first", Source(_id="first")),
        ("second", Source(_id="second")),
        ("first_branch", Sink(_id="first_branch")),
        ("second_branch", Sink(_id="second_branch")),
        ("merge", Sink(_id="merge")),
        ("victim", Sink(_id="victim")),
    ):
        graph.add_component(component, component_id)
    graph.add_component_edge("first", ("done", "input_value"), "first_branch")
    graph.add_component_edge("second", ("done", "input_value"), "second_branch")
    graph.add_component_edge("first_branch", ("out", "input_value"), "merge")
    graph.add_component_edge("second_branch", ("out", "input_value"), "merge")
    graph.add_component_edge("merge", ("out", "input_value"), "victim")
    graph.prepare()

    graph.mark_branch("first", VertexStates.INACTIVE, output_name="done")
    graph.mark_branch("second", VertexStates.INACTIVE, output_name="done")
    graph.reset_inactivated_vertices("first")

    assert graph.get_vertex("victim").state == VertexStates.INACTIVE

    graph.reset_inactivated_vertices("second")

    assert graph.get_vertex("victim").state == VertexStates.ACTIVE
