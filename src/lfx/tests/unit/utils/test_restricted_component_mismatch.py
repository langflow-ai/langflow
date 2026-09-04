"""Restricted-mode diagnosis for a saved component this server replaced with its own.

With ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` a node's stored code never runs: the build
executes this server's component of the same ``data.type`` instead. That keeps flows saved
before an upgrade runnable, but it is silent, so a node that is a *customized* copy of a
built-in is quietly rebuilt as the stock component and fails with whatever that component
complains about -- a customized Agent surfaces as "No model selected", naming neither the
customization nor the policy that discarded it.

These tests pin the diagnosis appended to such a failure, and the cases it must stay quiet for.
"""

import asyncio
from types import SimpleNamespace

import pytest
from lfx.interface.components import component_cache
from lfx.utils.flow_validation import (
    describe_restricted_component_mismatch,
    explain_restricted_component_mismatch,
)

SERVER_AGENT_CODE = "# Agent (this server)"

SERVER_AGENT_OUTPUTS = [
    {
        "name": "response",
        "display_name": "Response",
        "types": ["Message"],
        "method": "message_response",
        "allows_loop": False,
    }
]


def _registry() -> dict:
    """A one-component registry whose Agent declares a required, unfillable ``model`` input."""
    return {
        "models_and_agents": {
            "Agent": {
                "template": {
                    "code": {"value": SERVER_AGENT_CODE, "required": True, "show": True},
                    "model": {"required": True, "value": "", "show": True, "_input_type": "ModelInput"},
                    "system_prompt": {"required": False, "value": "", "show": True},
                },
                "outputs": SERVER_AGENT_OUTPUTS,
                "metadata": {"code_hash": "hash-agent"},
            }
        }
    }


def _saved_agent(*, template: dict | None = None) -> dict:
    return {
        "display_name": "Agent",
        "template": template
        if template is not None
        else {
            "code": {"value": SERVER_AGENT_CODE, "required": True, "show": True},
            "model": {"required": True, "value": "", "show": True, "_input_type": "ModelInput"},
            "system_prompt": {"required": False, "value": "", "show": True},
        },
        "outputs": SERVER_AGENT_OUTPUTS,
    }


def _customized_agent() -> dict:
    """A fork of the built-in Agent: same ``type``, its own provider inputs, no ``model``."""
    return _saved_agent(
        template={
            "code": {"value": SERVER_AGENT_CODE + "\n# customization\n", "required": True, "show": True},
            "provider": {"required": True, "value": "", "show": True, "_input_type": "DropdownInput"},
            "system_prompt": {"required": False, "value": "", "show": True},
        }
    )


def _restrict(monkeypatch, *, allow_custom=False, registry=_registry, ready=True) -> None:
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=allow_custom)),
    )
    monkeypatch.setattr(component_cache, "all_types_dict", registry() if registry else None)
    monkeypatch.setattr(component_cache, "all_types_ready", ready)


def test_customized_builtin_is_named_with_the_policy_that_replaced_it(monkeypatch):
    _restrict(monkeypatch)

    hint = describe_restricted_component_mismatch("Agent", _customized_agent())

    assert hint is not None
    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in hint
    assert '"Agent"' in hint
    assert "missing required input: model" in hint


def test_permissive_mode_says_nothing(monkeypatch):
    """With custom components allowed the node's own code runs, so nothing was replaced."""
    _restrict(monkeypatch, allow_custom=True)

    assert describe_restricted_component_mismatch("Agent", _customized_agent()) is None


def test_component_matching_this_server_says_nothing(monkeypatch):
    """A node this server's component can drive must not be blamed for an unrelated failure."""
    _restrict(monkeypatch)

    assert describe_restricted_component_mismatch("Agent", _saved_agent()) is None


def test_unknown_component_type_says_nothing(monkeypatch):
    """An unrecognized type never reaches a build -- ``check_flow_and_raise`` blocks it first."""
    _restrict(monkeypatch)

    assert describe_restricted_component_mismatch("TotallyCustom", _customized_agent()) is None


def test_registry_not_loaded_says_nothing(monkeypatch):
    _restrict(monkeypatch, registry=None, ready=False)

    assert describe_restricted_component_mismatch("Agent", _customized_agent()) is None


@pytest.mark.parametrize(("component_type", "node_info"), [(None, _customized_agent()), ("Agent", None), ("", {})])
def test_malformed_input_says_nothing(monkeypatch, component_type, node_info):
    _restrict(monkeypatch)

    assert describe_restricted_component_mismatch(component_type, node_info) is None


def test_breaking_outputs_are_reported_without_a_missing_input_clause(monkeypatch):
    """Not every mismatch is a missing input; the clause is dropped rather than left empty."""
    _restrict(monkeypatch)
    node_info = _saved_agent()
    node_info["outputs"] = [{"name": "renamed", "display_name": "Renamed", "types": ["Message"]}]

    hint = describe_restricted_component_mismatch("Agent", node_info)

    assert hint is not None
    assert "missing required input" not in hint


def test_explain_never_raises(monkeypatch):
    """The only caller is an error handler: a raising diagnosis would mask the real failure."""

    def _boom():
        msg = "registry exploded"
        raise RuntimeError(msg)

    monkeypatch.setattr("lfx.services.deps.get_settings_service", _boom)

    assert explain_restricted_component_mismatch("Agent", _customized_agent()) is None


def test_build_error_carries_the_diagnosis(monkeypatch):
    """The failure a user actually sees names the policy, not just the stock component's complaint."""
    from lfx.exceptions.component import ComponentBuildError
    from lfx.graph.vertex.base import Vertex

    _restrict(monkeypatch)

    async def _raise(**_kwargs):
        msg = "No model selected. Please select a language model from the available options."
        raise ValueError(msg)

    monkeypatch.setattr("lfx.interface.initialize.loading.get_instance_results", _raise)

    vertex = Vertex.__new__(Vertex)
    vertex.display_name = "Agent"
    vertex.data = {"type": "Agent", "node": _customized_agent()}
    vertex.graph = SimpleNamespace(flow_id=None)

    with pytest.raises(ComponentBuildError) as excinfo:
        asyncio.run(vertex._build_results(custom_component=None, custom_params={}, base_type="component"))

    message = str(excinfo.value)
    assert "No model selected" in message
    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in message
    assert "missing required input: model" in message
