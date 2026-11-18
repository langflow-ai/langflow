"""The extracted selector keeps existing runtime behavior before hydration."""

from types import SimpleNamespace

import pytest
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.base.models.provider_selection import raw_model_provider_names
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import ModelInput, StrInput


@pytest.mark.parametrize(
    ("parameters", "names", "expected"),
    [
        ({"model": {"provider": " OpenAI "}}, ["model"], ("OpenAI",)),
        ({"model": [{"provider": "OpenAI"}, {"provider": "Anthropic"}]}, ["model"], ("OpenAI",)),
        (
            {"model": [{"provider": "OpenAI"}], "provider": "Anthropic", "secondary": {"provider": "Ollama"}},
            ["model", "secondary"],
            ("Anthropic", "Ollama"),
        ),
        ({"model": [], "agent_llm": " OpenAI "}, ["model"], ("OpenAI",)),
        ({"model": "connect_other_models", "agent_llm": "Custom"}, ["model"], ()),
        ({"model": ["malformed"], "agent_llm": 123}, ["model"], ()),
        ({"model": {"provider": "OpenAI"}, "provider": "  "}, ["model"], ("OpenAI",)),
        ({"model": {"provider": "OpenAI"}, "provider": 123}, ["model"], ("OpenAI",)),
        ({"model": {"provider": "OpenAI"}, "secondary": {"provider": "OpenAI"}}, ["model", "secondary"], ("OpenAI",)),
    ],
)
def test_raw_provider_parser_preserves_runtime_selection(parameters, names, expected):
    assert raw_model_provider_names(names, parameters) == expected


@pytest.mark.parametrize("mode", ["standalone", "delegate", "none"])
def test_component_still_uses_typed_fields_and_legacy_identity_resolution(mode):
    component = SimpleNamespace(
        model_provider_policy_mode=mode,
        _inputs={
            "model": ModelInput(name="model"),
            "secondary": ModelInput(name="secondary"),
            "ignored": StrInput(name="ignored"),
        },
        _parameters={
            "model": {"provider": "OpenAI"},
            "secondary": [{"provider": "openai"}],
            "ignored": {"provider": "Anthropic"},
            "agent_llm": "Historical Local Provider",
        },
    )
    expected = () if mode == "none" else ("openai", resolve_provider_id("Historical Local Provider"))
    assert Component._selected_model_provider_policy_ids(component) == expected
