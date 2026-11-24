from lfx.execution.types import RunComplete, StepResult, Unit


def test_unit_carries_graph_inputs_and_runtime_options():
    sentinel = object()
    unit = Unit(
        graph=sentinel,
        inputs=[{"input_value": "hi"}],
        runtime_options={"event_manager": None, "session_id": "s1"},
    )
    assert unit.graph is sentinel
    assert unit.inputs == [{"input_value": "hi"}]
    assert unit.runtime_options == {"event_manager": None, "session_id": "s1"}


def test_unit_runtime_options_defaults_to_empty_dict():
    unit = Unit(graph=object(), inputs=[])
    assert unit.runtime_options == {}


def test_run_complete_carries_outputs():
    rc = RunComplete(outputs=["a", "b"])
    assert rc.outputs == ["a", "b"]


def test_step_result_carries_payload():
    sr = StepResult(payload={"vertex_id": "x"})
    assert sr.payload == {"vertex_id": "x"}
