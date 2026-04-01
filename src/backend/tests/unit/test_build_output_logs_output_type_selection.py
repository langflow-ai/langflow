from types import SimpleNamespace

from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.schema.schema import build_output_logs


def test_build_output_logs_prefers_results_for_table_outputs_when_status_is_set():
    component = MemoryComponent()

    stored_message = Message(
        text="hello",
        sender="User",
        sender_name="User",
        session_id="session",
        context_id="context",
    )
    table = DataFrame([stored_message])

    # Simulate what happens during a multi-output build:
    # - a Message output causes Component.extract_data() to set component.status
    # - artifacts for DataFrame/Table may contain pandas internals (via `.data`)
    component._results = {
        "messages_text": Message(text="User: hello"),
        "dataframe": table,
    }
    component._artifacts = {
        "messages_text": {"raw": "User: hello"},
        # In current pandas versions DataFrame/Table doesn't expose `.data`, so the
        # artifact raw extraction falls back to `component.status` (string), causing
        # Message and Table outputs to look identical unless we prefer results.
        "dataframe": {"raw": "User: hello"},
    }
    component.status = "User: hello"

    vertex = SimpleNamespace(
        outputs=[
            {"name": "messages_text", "types": ["Message"]},
            {"name": "dataframe", "types": ["Table"]},
        ]
    )

    logs = build_output_logs(vertex, (component, None))

    assert logs["messages_text"]["type"] == "text"
    assert isinstance(logs["messages_text"]["message"], str)

    assert logs["dataframe"]["type"] == "array"
    assert isinstance(logs["dataframe"]["message"], list)
    assert len(logs["dataframe"]["message"]) > 0
    assert isinstance(logs["dataframe"]["message"][0], dict)
