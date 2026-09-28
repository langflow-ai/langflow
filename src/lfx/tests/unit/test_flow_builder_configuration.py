"""Configuration regressions using the component templates shipped to the Assistant."""

from copy import deepcopy

import pytest
from lfx.graph.flow_builder import add_component, configure_component, empty_flow
from lfx.graph.flow_builder.builder import load_local_registry
from lfx.mcp.registry import describe_component


def component_flow(component_type):
    flow = empty_flow()
    component_id = add_component(flow, component_type, load_local_registry())["id"]
    return flow, component_id, flow["data"]["nodes"][0]["data"]["node"]["template"]


@pytest.mark.parametrize("component_type", ["Agent", "LanguageModelComponent"])
@pytest.mark.parametrize("saved_minimum", [None, 1])
def test_token_limit_can_be_reset_to_zero(component_type, saved_minimum):
    flow, component_id, template = component_flow(component_type)
    if saved_minimum is not None:
        template["max_tokens"]["range_spec"]["min"] = saved_minimum
    configure_component(flow, component_id, {"max_tokens": 100})
    configure_component(flow, component_id, {"max_tokens": 0})
    assert template["max_tokens"]["value"] == 0

    before = deepcopy(flow)
    with pytest.raises(ValueError, match="max_tokens"):
        configure_component(flow, component_id, {"max_tokens": -1})
    assert flow == before


@pytest.mark.parametrize("previous", [None, 2])
def test_duration_can_be_reconfigured_after_clearing_or_using_days(previous):
    flow, component_id, template = component_flow("HumanInput")
    configure_component(flow, component_id, {"timeout": previous})
    configure_component(flow, component_id, {"timeout": {"unit": "Hours", "value": 2}})
    assert template["timeout"]["value"] == {"unit": "Hours", "value": 2}


@pytest.mark.parametrize("method", ["Rules only", "Rules + AI"])
@pytest.mark.parametrize("separate_calls", [False, True])
def test_guardrail_choices_follow_the_selected_method(method, separate_calls):
    flow, component_id, template = component_flow("GuardrailValidatorV2")
    if separate_calls:
        configure_component(flow, component_id, {"checking_method": method})
        params = {"enabled_guardrails": ["Scope"]}
    else:
        # The dependency occurs after its selection in the request.
        params = {"enabled_guardrails": ["Scope"], "checking_method": method}
    configure_component(flow, component_id, params)
    assert template["enabled_guardrails"]["value"] == ["Scope"]
    assert "Scope" in template["enabled_guardrails"]["options"]


@pytest.mark.parametrize("selection", [["Scope"], ["not a guardrail"]])
def test_invalid_guardrail_configuration_is_atomic(selection):
    flow, component_id, _ = component_flow("GuardrailValidatorV2")
    before = deepcopy(flow)
    params = {"input_text": "changed", "enabled_guardrails": selection}
    before_params = deepcopy(params)
    with pytest.raises(ValueError, match="enabled_guardrails"):
        configure_component(flow, component_id, params)
    assert flow == before
    assert params == before_params


def test_repeating_a_selection_does_not_bypass_its_new_mode_constraints():
    flow, component_id, template = component_flow("GuardrailValidatorV2")
    configure_component(flow, component_id, {"checking_method": "Rules only", "enabled_guardrails": ["Scope"]})
    before = deepcopy(flow)
    with pytest.raises(ValueError, match="enabled_guardrails"):
        configure_component(flow, component_id, {"checking_method": "AI checks", "enabled_guardrails": ["Scope"]})
    assert flow == before
    configure_component(flow, component_id, {"checking_method": "AI checks", "enabled_guardrails": ["PII"]})
    assert "Scope" not in template["enabled_guardrails"]["options"]


def test_discovery_exposes_conditional_choices():
    described = describe_component(load_local_registry(), "GuardrailValidatorV2")
    field = next(field for field in described["fields"] if field["name"] == "enabled_guardrails")
    assert field["conditional_options"]
    assert any("Scope" in rule["options"] for rule in field["conditional_options"])


@pytest.mark.parametrize("method", ["AI checks", "Rules only", "Rules + AI"])
@pytest.mark.parametrize("direction", ["input", "output"])
def test_configured_guardrail_options_match_runtime_template_refresh(method, direction):
    from lfx.components.llm_operations.guardrails_v2 import GuardrailsV2Component

    flow, component_id, template = component_flow("GuardrailValidatorV2")
    configure_component(flow, component_id, {"checking_method": method, "direction": direction})
    runtime_template = GuardrailsV2Component._configure_fields(deepcopy(template))
    assert template["enabled_guardrails"]["options"] == runtime_template["enabled_guardrails"]["options"]


def test_conditional_choices_do_not_allow_scalars_or_unknown_options():
    flow, component_id, _ = component_flow("GuardrailValidatorV2")
    configure_component(flow, component_id, {"checking_method": "Rules only"})
    before = deepcopy(flow)
    for selection in ("Scope", ["not a guardrail"]):
        with pytest.raises(ValueError, match="enabled_guardrails"):
            configure_component(flow, component_id, {"enabled_guardrails": selection})
        assert flow == before


def test_conditional_choices_can_require_an_empty_selection():
    flow = empty_flow()
    template = {
        "mode": {"type": "str", "options": ["on", "off"], "value": "on"},
        "choices": {
            "type": "str",
            "list": True,
            "options": ["a"],
            "value": ["a"],
            "conditional_options": [
                {"when": {"mode": "off"}, "options": []},
                {"when": {}, "options": ["a"]},
            ],
        },
    }
    component_id = add_component(flow, "Example", {"Example": {"template": template}})["id"]
    before = deepcopy(flow)
    with pytest.raises(ValueError, match="choices"):
        configure_component(flow, component_id, {"mode": "off", "choices": ["a"]})
    assert flow == before
    configure_component(flow, component_id, {"mode": "off", "choices": []})
    fields = flow["data"]["nodes"][0]["data"]["node"]["template"]
    assert fields["choices"]["options"] == []
    assert fields["choices"]["value"] == []
    configure_component(flow, component_id, {"mode": "on", "choices": ["a"]})
    assert fields["choices"]["value"] == ["a"]
