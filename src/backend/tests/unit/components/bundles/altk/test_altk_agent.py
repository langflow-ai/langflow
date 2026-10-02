"""Retired ALTK nodes remain inspectable without installing the former SDK."""

import importlib
import sys
from importlib.abc import MetaPathFinder

import pytest
from lfx.components.altk.altk_agent import ALTKAgentComponent


class RejectALTKImports(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002 - import hook interface
        if fullname == "altk" or fullname.startswith("altk."):
            pytest.fail(f"Retired integration attempted to import {fullname}")


def test_discovery_without_altk_sdk(monkeypatch):
    for name in list(sys.modules):
        if name == "altk" or name.startswith("altk."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [RejectALTKImports(), *sys.meta_path])
    for name in (
        "lfx.base.agents.altk_base_agent",
        "lfx.base.agents.altk_tool_wrappers",
        "lfx.components.altk.altk_agent",
    ):
        module = importlib.import_module(name)
        importlib.reload(module)
    from lfx.components.altk import ALTKAgentComponent as DiscoveredComponent

    component = DiscoveredComponent()
    assert component.name == "ALTK Agent"
    assert type(component).__name__ == "ALTKAgentComponent"
    assert "retired" in component.description.lower()
    assert component.legacy is True
    assert component.replacement == ["models_and_agents.Agent"]
    assert not any(name == "altk" or name.startswith("altk.") for name in sys.modules)


def test_saved_node_preserves_configuration_and_connections():
    component = ALTKAgentComponent(
        input_value="Existing input",
        agent_llm="OpenAI",
        tools=[],
        verbose=False,
        enable_tool_validation=False,
        enable_post_tool_reflection=True,
        response_processing_size_threshold=400,
    )
    assert component.input_value == "Existing input"
    assert component.response_processing_size_threshold == 400
    assert component.enable_tool_validation is False
    assert component.enable_post_tool_reflection is True
    input_names = {field.name for field in component.inputs}
    assert {"agent_llm", "tools", "input_value", "verbose", "enable_tool_validation"} <= input_names
    assert [(output.name, output.method) for output in component.outputs] == [("response", "message_response")]


@pytest.mark.parametrize(("validation", "reflection"), [(True, True), (False, False)])
async def test_execution_reports_retirement_before_loading_model(validation, reflection):
    component = ALTKAgentComponent(
        agent_llm="OpenAI",
        api_key="",
        enable_tool_validation=validation,
        enable_post_tool_reflection=reflection,
    )
    with pytest.raises(RuntimeError, match=r"ALTK.*retired.*1\.13\.0.*Agent"):
        await component.message_response()


async def test_direct_execution_entrypoints_report_retirement():
    component = ALTKAgentComponent()
    with pytest.raises(RuntimeError, match="retired"):
        component.create_agent_runnable()
    with pytest.raises(RuntimeError, match="retired"):
        await component.run_agent(None)
    with pytest.raises(RuntimeError, match="retired"):
        await component.json_response()
