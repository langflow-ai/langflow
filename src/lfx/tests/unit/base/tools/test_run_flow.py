import sys
from importlib import import_module
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from lfx.graph.graph.base import Graph
from lfx.graph.vertex.base import Vertex


def _load_run_flow_module():
    langflow_flow_module = ModuleType("langflow.helpers.flow")
    langflow_flow_module.get_flow_by_id_or_name = MagicMock()
    with patch.dict(
        sys.modules,
        {
            "langflow": ModuleType("langflow"),
            "langflow.helpers": ModuleType("langflow.helpers"),
            "langflow.helpers.flow": langflow_flow_module,
        },
    ):
        return import_module("lfx.base.tools.run_flow")


def _vertex(vertex_id, component_type, template):
    vertex = MagicMock(spec=Vertex)
    vertex.id = vertex_id
    vertex.data = {"type": component_type, "node": {"template": template}}
    # A real Vertex carries these; the shared helper writes the accepted value to
    # params as well as through update_raw_params.
    vertex.params = {}
    vertex.load_from_db_fields = []
    return vertex


def test_process_tweaks_on_graph_filters_undeclared_and_protected_fields():
    """The Run Flow component now uses the shared graph-level helper.

    The private copy it used to carry applied the protected-field floor but not
    the deployment tweak policy, so `off` and `declared` were silently ignored
    for tweaks routed into a sub-flow. The shared helper enforces both, and
    reports refusals instead of dropping them.
    """
    from lfx.exceptions.tweaks import TweakRefusedError
    from lfx.processing.process import process_tweaks_on_graph

    graph = MagicMock(spec=Graph)
    runnable = _vertex(
        "runnable",
        "PythonFunction",
        {
            "param": {"type": "str"},
            "code": {"type": "code"},
            "function_code": {"type": "str"},
            "malformed": "not-a-field",
        },
    )
    invalid_template = _vertex("invalid-template", "TextInput", [])
    protected_only = _vertex("protected-only", "PythonFunction", {"code": {"type": "code"}})
    graph.vertices = [runnable, invalid_template, protected_only]

    tweaks = {
        "runnable": {
            "param": "safe",
            "code": "blocked",
            "function_code": "blocked",
            "malformed": "ignored",
            "undeclared": "ignored",
        },
        "invalid-template": {"param": "ignored"},
        "protected-only": {"code": "blocked"},
    }

    with pytest.raises(TweakRefusedError) as exc:
        process_tweaks_on_graph(graph, tweaks)

    # The floor refuses the code fields, and the refusal is now reported rather
    # than logged and dropped.
    assert exc.value.refused == ["code", "function_code"]

    # Nothing is applied when anything is refused. The graph here is cached and
    # reused by the Run Flow component, so a half-applied payload would survive
    # into later runs of the same sub-flow.
    runnable.update_raw_params.assert_not_called()
    invalid_template.update_raw_params.assert_not_called()
    protected_only.update_raw_params.assert_not_called()
