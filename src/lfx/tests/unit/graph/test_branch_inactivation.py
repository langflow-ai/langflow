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


def _shared_descendant() -> Graph:
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
    return graph


def test_shared_descendant_stays_inactive_until_every_source_releases_it():
    graph = _shared_descendant()

    graph.mark_branch("first", VertexStates.INACTIVE, output_name="done")
    graph.mark_branch("second", VertexStates.INACTIVE, output_name="done")
    graph.reset_inactivated_vertices("first")

    assert graph.get_vertex("victim").state == VertexStates.INACTIVE

    graph.reset_inactivated_vertices("second")

    assert graph.get_vertex("victim").state == VertexStates.ACTIVE


def test_start_does_not_override_a_stop_another_source_still_holds():
    graph = _shared_descendant()
    graph.mark_branch("first", VertexStates.INACTIVE, output_name="done")

    # "second" never stopped anything, so it has nothing of its own to release.
    graph.mark_branch("second", VertexStates.ACTIVE, output_name="done")

    assert graph.get_vertex("second_branch").state == VertexStates.ACTIVE
    assert graph.get_vertex("victim").state == VertexStates.INACTIVE
    assert "victim" in graph.inactivated_vertices

    graph.reset_inactivated_vertices("first")

    assert graph.get_vertex("victim").state == VertexStates.ACTIVE


def test_unowned_inactivation_keeps_legacy_release_alongside_owned_stops():
    graph = _parallel_branches()
    graph.mark_branch("stopper", VertexStates.INACTIVE, output_name="done")
    # Graphs cached or checkpointed before ownership was tracked carry inactive
    # vertices with no recorded source.
    graph.mark_vertex("sibling_output", VertexStates.INACTIVE)

    graph.reset_inactivated_vertices("sibling")

    assert graph.get_vertex("sibling_output").state == VertexStates.ACTIVE
    assert graph.get_vertex("victim").state == VertexStates.INACTIVE
    assert graph.inactivated_vertices == {"victim"}


def test_resorting_the_graph_drops_stale_branch_ownership():
    graph = _shared_descendant()
    graph.mark_branch("first", VertexStates.INACTIVE, output_name="done")

    graph.sort_vertices()

    assert graph.inactivated_vertices == set()
    assert graph.branch_inactivation_sources == {}
    # A stop left over from the previous run must not re-inactivate the branch.
    graph.mark_branch("second", VertexStates.ACTIVE, output_name="done")
    assert graph.get_vertex("victim").state == VertexStates.ACTIVE


def test_branch_ownership_survives_the_graph_cache_round_trip():
    graph = _parallel_branches()
    graph.mark_branch("stopper", VertexStates.INACTIVE, output_name="done")

    restored = Graph.__new__(Graph)
    restored.__setstate__(graph.__getstate__())

    assert restored.branch_inactivation_sources == {"stopper": {"victim"}}


def test_graph_cached_before_branch_ownership_loads_without_it():
    graph = _parallel_branches()
    state = graph.__getstate__()
    state.pop("branch_inactivation_sources")

    restored = Graph.__new__(Graph)
    restored.__setstate__(state)

    assert restored.branch_inactivation_sources == {}
