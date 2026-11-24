from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.graph.vertex.base import VertexStates
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class TwoOutputSource(Component):
    display_name = "Two Output Source"
    name = "TwoOutputSource"

    inputs = [MessageTextInput(name="feedback", display_name="Feedback", required=False)]
    outputs = [
        Output(display_name="Item", name="item", method="item_output", group_outputs=True),
        Output(display_name="Done", name="done", method="done_output", group_outputs=True),
    ]

    def item_output(self) -> Message:
        return Message(text="item")

    def done_output(self) -> Message:
        return Message(text="done")


class PassThrough(Component):
    display_name = "Pass Through"
    name = "PassThrough"

    inputs = [MessageTextInput(name="input_value", display_name="Input", required=False)]
    outputs = [Output(display_name="Out", name="out", method="run")]

    def run(self) -> Message:
        return Message(text=str(self.input_value or ""))


def test_stopping_sibling_output_does_not_protect_branch_through_feedback_cycle():
    """A feedback edge back to the source must not make sibling outputs look shared."""
    graph = Graph()
    source = TwoOutputSource(_id="source")
    body = PassThrough(_id="body")
    feedback = PassThrough(_id="feedback")
    done = PassThrough(_id="done")

    for component, component_id in (
        (source, "source"),
        (body, "body"),
        (feedback, "feedback"),
        (done, "done"),
    ):
        graph.add_component(component, component_id)

    graph.add_component_edge("source", ("item", "input_value"), "body")
    graph.add_component_edge("body", ("out", "input_value"), "feedback")
    graph.add_component_edge("feedback", ("out", "feedback"), "source")
    graph.add_component_edge("source", ("done", "input_value"), "done")
    graph.prepare()

    graph.mark_branch("source", VertexStates.INACTIVE, output_name="done")

    assert graph.get_vertex("done").state == VertexStates.INACTIVE
