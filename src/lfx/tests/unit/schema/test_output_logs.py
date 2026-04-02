import pandas as pd

from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.custom.custom_component.component import Component
from lfx.schema.dataframe import Table
from lfx.schema.message import Message
from lfx.schema.schema import build_output_logs


class _DummyComponent(CustomComponent):
    pass


def test_build_output_logs_table_not_overridden_by_message_status():
    """Regression: when a message output is built first, component.status becomes truthy.

    build_output_logs must still read per-output results so a Table output stays tabular.
    """

    component = _DummyComponent()
    component.status = Message(text="stored")  # simulate "message output happened" state

    table = Table([{"a": 1}, {"a": 2}])

    component.set_results({"message": Message(text="hi"), "table": table})

    # Simulate the pre-fix failure mode: artifacts/raw for table mistakenly becomes a Message.
    component.set_artifacts({"message": {"raw": Message(text="hi")}, "table": {"raw": Message(text="hi")}})

    vertex = type("VertexLike", (), {"outputs": [{"name": "message"}, {"name": "table"}]})()

    logs = build_output_logs(vertex, (component,))

    assert logs["message"]["type"] in {"message", "text"}
    assert logs["table"]["type"] == "array"
    assert logs["table"]["message"] == [{"a": 1}, {"a": 2}]


def test_component_extract_data_does_not_fallback_to_status_for_dataframe():
    component = Component.__new__(Component)
    component.status = Message(text="stored")

    df = pd.DataFrame([{"x": 1}])
    assert component.extract_data(df) is df
