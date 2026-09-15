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


def test_pre_run_setup_survives_a_component_with_no_vertex(run_flow_component_cls):
    """A Run Flow component that is not attached to a vertex must still start.

    `_get_selected_flow_updated_at` read `getattr(self, "_vertex", {}).data`.
    `CustomComponent.__init__` always sets `_vertex`, to `None`, so that default
    could never apply, and `{}` has no `.data` either, so it would have raised
    the same `AttributeError` if it somehow had. `_pre_run_setup` calls this on
    its first line and `_build_results` calls `_pre_run_setup` before anything
    else, so the component died before doing any of its own work.
    """
    component = run_flow_component_cls(_id="run-flow-no-vertex")
    assert component._vertex is None  # the attribute is present, so the default never fires

    component._pre_run_setup()

    assert component._cached_flow_updated_at is None


def test_stored_updated_at_is_reachable_without_a_vertex(run_flow_component_cls):
    """The attribute fallback was dead code for exactly the case it was for.

    `_get_selected_flow_updated_at` falls back to
    `_attributes["flow_name_selected_updated_at"]`, but it raised on the line
    above before ever reaching it.
    """
    component = run_flow_component_cls(_id="run-flow-stored")
    component._attributes["flow_name_selected_updated_at"] = "2026-09-15T10:00:00Z"

    component._pre_run_setup()

    assert component._cached_flow_updated_at == "2026-09-15T10:00:00Z"


def test_vertex_metadata_still_wins_over_the_stored_value(run_flow_component_cls):
    """The vertex remains the first source when there is one."""
    component = run_flow_component_cls(_id="run-flow-with-vertex")
    component._attributes["flow_name_selected_updated_at"] = "2026-09-15T10:00:00Z"
    vertex = MagicMock(spec=Vertex)
    vertex.data = {
        "node": {"template": {"flow_name_selected": {"selected_metadata": {"updated_at": "2026-09-15T12:00:00Z"}}}}
    }
    component._vertex = vertex

    component._pre_run_setup()

    assert component._cached_flow_updated_at == "2026-09-15T12:00:00Z"
