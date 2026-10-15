import importlib
import sys

import pytest

pytest.importorskip("lfx_bundles")


def test_codeagents_bundle_exposed_via_components_package():
    components = importlib.import_module("lfx.components")
    assert hasattr(components, "codeagents"), "codeagents bundle should be discoverable"


def test_codeagents_components_lazy_import():
    codeagents = importlib.import_module("lfx_bundles.codeagents")
    # Ensure dynamic imports map includes both components
    assert hasattr(codeagents, "CodeActAgentSmolagentsComponent")
    assert hasattr(codeagents, "OpenDsStarAgentComponent")


@pytest.mark.parametrize("class_name", ["CodeActAgentSmolagentsComponent", "OpenDsStarAgentComponent"])
def test_codeagents_without_opendsstar_explain_manual_install(monkeypatch, class_name):
    """Saved component classes still load; execution explains the explicit opt-in."""
    monkeypatch.setitem(sys.modules, "OpenDsStar", None)
    codeagents = importlib.import_module("lfx_bundles.codeagents")
    component = getattr(codeagents, class_name)()

    with pytest.raises(ImportError, match=r"uv pip install 'OpenDsStar==1\.0\.26' 'langchain-litellm==0\.5\.1'"):
        component.create_agent_runnable()
