import sys
from importlib import import_module
from types import ModuleType
from unittest.mock import MagicMock, call, patch

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
    return vertex


def test_process_tweaks_on_graph_filters_undeclared_and_protected_fields():
    run_flow_module = _load_run_flow_module()
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

    with patch.object(run_flow_module, "logger") as mock_logger:
        result = run_flow_module.RunFlowBaseComponent._process_tweaks_on_graph(None, graph, tweaks)

    assert result is graph
    runnable.update_raw_params.assert_called_once_with({"param": "safe"}, overwrite=True)
    invalid_template.update_raw_params.assert_not_called()
    protected_only.update_raw_params.assert_not_called()
    assert mock_logger.warning.call_args_list == [
        call("Security: refusing to override protected field 'code' via tweaks."),
        call("Security: refusing to override protected field 'function_code' via tweaks."),
        call("Security: refusing to override protected field 'code' via tweaks."),
    ]
