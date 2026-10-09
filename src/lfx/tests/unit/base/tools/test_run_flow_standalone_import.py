"""Run Flow must import when langflow is not installed.

``lfx serve`` and ``lfx run`` ship without langflow. Run Flow is the component that composes
one flow out of others, so a module-level langflow import makes multi-flow projects impossible
to run on the standalone runtime: the import fails before the component can be registered.

These tests block ``langflow`` at the import system level rather than relying on it being absent
from the environment, so they prove the property whether or not langflow happens to be installed
(``LFX_TEST_ALLOW_LANGFLOW=1`` installs it).
"""

import builtins
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

MODULES_UNDER_TEST = [
    "lfx.base.tools.run_flow",
    "lfx.components.flow_controls.run_flow",
]


class _BlockLangflow:
    """Make ``import langflow`` raise, as it does on a standalone lfx install."""

    def find_module(self, fullname, path=None):  # noqa: ARG002
        return self if fullname == "langflow" or fullname.startswith("langflow.") else None

    def load_module(self, fullname):
        msg = f"No module named {fullname!r}"
        raise ModuleNotFoundError(msg, name=fullname)

    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002
        if fullname == "langflow" or fullname.startswith("langflow."):
            msg = f"No module named {fullname!r}"
            raise ModuleNotFoundError(msg, name=fullname)


@pytest.fixture
def langflow_blocked():
    """Purge langflow and the modules under test, then refuse any langflow import."""
    purged = {
        name: module
        for name, module in sys.modules.items()
        if name == "langflow" or name.startswith("langflow.") or name in MODULES_UNDER_TEST
    }
    for name in purged:
        del sys.modules[name]

    blocker = _BlockLangflow()
    sys.meta_path.insert(0, blocker)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "langflow" or name.startswith("langflow."):
            msg = f"No module named {name!r}"
            raise ModuleNotFoundError(msg, name=name)
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    try:
        yield
    finally:
        builtins.__import__ = real_import
        sys.meta_path.remove(blocker)
        for name in MODULES_UNDER_TEST:
            sys.modules.pop(name, None)
        sys.modules.update(purged)


@pytest.mark.usefixtures("langflow_blocked")
@pytest.mark.parametrize("module_name", MODULES_UNDER_TEST)
def test_run_flow_imports_without_langflow(module_name):
    """The module imports on a standalone lfx install."""
    assert importlib.import_module(module_name) is not None


@pytest.mark.usefixtures("langflow_blocked")
def test_get_graph_runs_without_the_langflow_provider_policy():
    """The provider policy is langflow-only, so standalone lfx runs without one.

    ``scoped_model_provider_policy_for_target_flow`` scopes model provider credentials per
    target flow using langflow's database. Standalone lfx has no database, so the guard has
    nothing to scope and the run proceeds unscoped rather than failing.
    """
    module = importlib.import_module("lfx.base.tools.run_flow")

    policy = module._model_provider_policy(user_id=None, flow_id=None, flow_name="anything")

    # An async context manager that yields and does nothing.
    assert hasattr(policy, "__aenter__")
    assert hasattr(policy, "__aexit__")


@pytest.mark.usefixtures("langflow_blocked")
async def test_standalone_caller_has_no_admin_exemption():
    module = importlib.import_module("lfx.base.tools.run_flow")

    assert await module.get_user_is_superuser("11111111-1111-1111-1111-111111111111") is False


@pytest.mark.usefixtures("langflow_blocked")
async def test_standalone_sibling_graph_still_passes_component_policy(tmp_path, monkeypatch):
    from lfx.graph.graph.base import Graph
    from lfx.utils.flow_validation import CustomComponentValidationError

    module = importlib.import_module("lfx.base.tools.run_flow")
    (tmp_path / "child.json").write_text(json.dumps({"data": {"nodes": [], "edges": []}}))
    component = module.RunFlowBaseComponent()
    component.cache_flow = False
    parent = Graph()
    parent.context["project_dir"] = str(tmp_path)
    component._vertex = SimpleNamespace(graph=parent)

    graph = await component.get_graph(flow_name_selected="child")
    assert isinstance(graph, Graph)

    async def deny_build(payload, *, is_superuser):
        assert payload == {"nodes": [], "edges": []}
        assert is_superuser is False
        msg = "restricted by component policy"
        raise CustomComponentValidationError(msg)

    monkeypatch.setattr(module, "custom_component_admin_only_enabled", lambda: True)
    monkeypatch.setattr(module, "prepare_flow_build_for_user", deny_build)
    with pytest.raises(CustomComponentValidationError, match="restricted by component policy"):
        await component.get_graph(flow_name_selected="child")
