import sys
from copy import deepcopy
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


@pytest.fixture
def run_flow_component_cls():
    """The concrete component, importable without langflow installed.

    `lfx.base.tools.run_flow` imports from `langflow.helpers.flow` at module
    level, and this suite deliberately runs with langflow absent (see
    `tests/conftest.py`). `_load_run_flow_module` above imports under
    `patch.dict`, which on exit also removes the freshly imported lfx module
    from `sys.modules`; the class is then unusable, because
    `Component.set_class_code` resolves its source through
    `inspect.getfile(type(self))`. So stub, import, and remove only the stubs.
    """
    flow_module = ModuleType("langflow.helpers.flow")
    flow_module.get_flow_by_id_or_name = MagicMock()
    flow_module.scoped_model_provider_policy_for_target_flow = MagicMock()
    stubs = {
        "langflow": ModuleType("langflow"),
        "langflow.helpers": ModuleType("langflow.helpers"),
        "langflow.helpers.flow": flow_module,
    }
    added = {name: module for name, module in stubs.items() if name not in sys.modules}
    sys.modules.update(added)
    try:
        yield import_module("lfx.components.flow_controls.run_flow").RunFlowComponent
    finally:
        for name in added:
            sys.modules.pop(name, None)


def _with_flow_output(component_cls):
    """A component carrying one selected-flow output, the way `map_outputs` leaves it."""
    from lfx.template.field.base import Output

    component = component_cls(_id="run-flow-copy")
    component._outputs_map["TextOutput-1~text"] = Output(
        name="TextOutput-1~text", display_name="text", method=None, types=["Message"]
    )
    component.map_outputs()
    return component, "_resolve_flow_output__TextOutput_1__text"


def test_a_copy_keeps_the_flow_output_methods(run_flow_component_cls):
    """A copied Run Flow component must answer with its own resolver.

    `ComponentToolkit` copies the component on every tool call, to keep
    concurrent calls from sharing state. The flow output methods are registered
    on the instance and `Component.__deepcopy__` rebuilds the component instead
    of copying its `__dict__`, so the copy used to have none of them.
    """
    component, method_name = _with_flow_output(run_flow_component_cls)
    original_method = getattr(component, method_name)

    copy = deepcopy(component)

    assert method_name in copy.__dict__
    assert getattr(copy, method_name).__self__ is copy
    assert original_method.__self__ is component


def test_tool_arguments_reach_the_method_that_runs(run_flow_component_cls):
    """The tool's arguments and the method that reads them must be the same object.

    The tool wrapper resolves the output method as
    `getattr(comp, method_name, output_method)`, where `comp` is the copy and
    `output_method` is bound to the component the toolkit was built from. With
    the resolver missing from the copy that default took over, so the flow ran
    against the original, which never received the call's arguments, and the
    tool answered with empty content.
    """
    component, method_name = _with_flow_output(run_flow_component_cls)
    output_method = getattr(component, method_name)

    copy = deepcopy(component)
    running_method = getattr(copy, method_name, output_method)
    copy.set(flow_tweak_data={"TextInput-1~input_value": "hello"})

    assert running_method.__self__._attributes["flow_tweak_data"] == {"TextInput-1~input_value": "hello"}
