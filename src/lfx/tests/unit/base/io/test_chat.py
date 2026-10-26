from types import SimpleNamespace

import pytest
from lfx.base.io.chat import _extract_model_name
from lfx.components.input_output.chat_output import ChatOutput
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.custom.custom_component.component import Component


class TestExtractModelName:
    def test_should_return_string_when_input_is_string(self):
        assert _extract_model_name("gpt-4o-mini") == "gpt-4o-mini"

    def test_should_return_name_when_input_is_model_input_list(self):
        model_input = [{"name": "gpt-4o-mini", "icon": "OpenAI", "provider": "OpenAI"}]
        assert _extract_model_name(model_input) == "gpt-4o-mini"

    def test_should_return_name_when_input_is_dict(self):
        model_dict = {"name": "claude-3", "provider": "Anthropic"}
        assert _extract_model_name(model_dict) == "claude-3"

    def test_should_return_none_when_input_is_empty_list(self):
        assert _extract_model_name([]) is None

    def test_should_return_none_when_input_is_none(self):
        assert _extract_model_name(None) is None

    def test_should_return_none_when_list_has_no_name_key(self):
        assert _extract_model_name([{"provider": "OpenAI"}]) is None

    def test_should_return_none_when_dict_has_no_name_key(self):
        assert _extract_model_name({"provider": "OpenAI"}) is None

    def test_should_return_none_when_input_is_integer(self):
        assert _extract_model_name(123) is None


@pytest.mark.parametrize(
    ("mode", "decision_model", "evidence", "expected"),
    [
        ("Decision Model", [{"name": "jev-latest"}], {"result": {"model": "jev-1.13.0"}}, "jev-1.13.0"),
        ("Decision Model", [{"name": "jev-latest"}], {"reason": "evaluation_error"}, "jev-latest"),
        ("Language Model", [{"name": "jev-latest"}], {"result": {"model": "jev-1.13.0"}}, "gpt-4o-mini"),
        ("Decision Model", [], None, "Smart Router"),
    ],
)
def test_chat_output_attributes_the_active_router_model(mode, decision_model, evidence, expected):
    router = SmartRouterComponent()
    router.set(
        routing_mode=mode, model=[{"name": "gpt-4o-mini"}], decision_model=decision_model, enable_else_output=True
    )
    router._decision_evidence = evidence
    output = ChatOutput()
    output.set_vertex(
        SimpleNamespace(
            incoming_edges=[SimpleNamespace(source_id="router")],
            graph=SimpleNamespace(get_vertex=lambda _: SimpleNamespace(custom_component=router)),
        )
    )

    assert output.get_properties_from_source_component() == (
        expected,
        router.icon,
        router.display_name,
        router.get_id(),
    )


@pytest.mark.parametrize("name", ["SmartRouter", "OtherModelComponent"])
def test_chat_output_preserves_sources_without_decision_fields(name):
    class LegacySource(Component):
        display_name = "Legacy source"
        icon = "route"
        model = [{"name": "gpt-4o-mini"}]

    source = LegacySource()
    source.name = name
    assert not hasattr(source, "routing_mode")
    assert not hasattr(source, "_decision_evidence")
    output = ChatOutput()
    output.set_vertex(
        SimpleNamespace(
            incoming_edges=[SimpleNamespace(source_id="source")],
            graph=SimpleNamespace(get_vertex=lambda _: SimpleNamespace(custom_component=source)),
        )
    )

    assert output.get_properties_from_source_component() == (
        "gpt-4o-mini",
        source.icon,
        source.display_name,
        source.get_id(),
    )


@pytest.mark.parametrize("provider_returned_model", [False, True])
def test_chat_output_masks_router_secrets_in_model_attribution(provider_returned_model):
    secret = "synthetic-secret-must-not-persist"  # noqa: S105
    router = SmartRouterComponent()
    router.set(routing_mode="Decision Model", decision_model=[{"name": secret}])
    router.set_attributes({"api_key": secret})
    router._decision_evidence = {"result": {"model": secret}} if provider_returned_model else None
    output = ChatOutput()
    output.set_vertex(
        SimpleNamespace(
            incoming_edges=[SimpleNamespace(source_id="router")],
            graph=SimpleNamespace(get_vertex=lambda _: SimpleNamespace(custom_component=router)),
        )
    )

    assert output.get_properties_from_source_component()[0] == "**********"
    if provider_returned_model:
        assert router._decision_evidence["result"]["model"] == secret
