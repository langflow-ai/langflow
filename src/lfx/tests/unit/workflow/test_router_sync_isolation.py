"""The sync run path must honor the same request-scope isolation as the stream path.

No mocks: a real 3-node graph (ChatInput -> probe -> ChatOutput) where the probe
component reads the request-scope ContextVars mid-run. The serve registry stamps
``graph.context["no_env_fallback"]`` and ``graph.context["request_variables"]``;
``run_workflow_sync`` must activate both around the run and reset them after, exactly
like ``execute_graph_with_capture`` does on the stream path.
"""

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message
from lfx.schema.workflow import WorkflowRunRequest
from lfx.services.variable.request_scope import get_active_request_variables, is_env_fallback_disabled
from lfx.workflow.converters import parse_workflow_run_request
from lfx.workflow.router import run_workflow_sync

_FLOW_ID = "67ccd2be-17f0-4190-81ff-3bb2cf6508e6"


class _ScopeProbe(Component):
    """Records the live request-scope state at the moment the graph runs it."""

    display_name = "Scope Probe"
    inputs = [MessageTextInput(name="input_value", display_name="Input")]
    outputs = [Output(display_name="Output", name="output", method="probe")]

    observed: dict = {}

    def probe(self) -> Message:
        _ScopeProbe.observed = {
            "no_env_fallback": is_env_fallback_disabled(),
            "request_variables": get_active_request_variables(),
        }
        return Message(text=self.input_value)


def _probe_graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    probe = _ScopeProbe(_id="probe")
    chat_output = ChatOutput(_id="chat_output")
    probe.set(input_value=chat_input.message_response)
    chat_output.set(input_value=probe.probe)
    graph = Graph(chat_input, chat_output)
    graph.prepare()
    return graph


async def test_sync_run_activates_and_resets_request_scope_from_context():
    _ScopeProbe.observed = {}
    graph = _probe_graph()
    graph.context["no_env_fallback"] = True
    graph.context["request_variables"] = {"access_token": "secret"}

    parsed = parse_workflow_run_request(WorkflowRunRequest(flow_id=_FLOW_ID, input_value="hi", mode="sync"))
    await run_workflow_sync(graph, parsed, _FLOW_ID)

    # Live DURING the run: the sync path must have activated both ContextVars.
    assert _ScopeProbe.observed["no_env_fallback"] is True
    assert _ScopeProbe.observed["request_variables"] == {"access_token": "secret"}

    # Reset AFTER the run: no leak into the surrounding context.
    assert is_env_fallback_disabled() is False
    assert get_active_request_variables() is None


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
