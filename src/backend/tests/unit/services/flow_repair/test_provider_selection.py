"""Provider selections are read from trusted declarations without hydration."""

import copy

import pytest
from langflow.services.flow_repair.policy import _component_providers
from lfx.inputs.inputs import DropdownInput, ModelInput, StrInput
from lfx.upgrade.checker import build_registry_lookup


def delegated_fixture(kind="LanguageModelComponent", *, selection=None, override=None):
    model = ModelInput(name="model", required=True).to_dict()
    entry = {
        "metadata": {"model_provider_policy_mode": "delegate"},
        "template": {"model": model, "provider": StrInput(name="provider", load_from_db=False).to_dict()},
    }
    info = copy.deepcopy(entry)
    info["template"]["model"]["value"] = (
        [{"provider": "OpenAI", "name": "fixture-model"}] if selection is None else selection
    )
    info["template"]["provider"]["value"] = override
    node = {"id": f"{kind}-1", "data": {"type": kind, "node": info}}
    return {"nodes": [node], "edges": []}, build_registry_lookup({"models": {kind: entry}})


@pytest.mark.parametrize("kind", ["LanguageModelComponent", "EmbeddingModelComponent"])
def test_delegated_selected_provider_is_collected(kind):
    graph, registry = delegated_fixture(kind)

    assert _component_providers(graph, registry) == {"openai"}


@pytest.mark.parametrize(
    "selection",
    [
        {"provider": "openai", "name": "fixture"},
        [{"provider": "OpenAI", "name": "fixture"}],
        [{"provider": "OpenAI"}, {"provider": "Anthropic"}],
    ],
)
def test_mapping_and_list_selections_follow_the_runtime_first_selection(selection):
    graph, registry = delegated_fixture(selection=selection)
    assert _component_providers(graph, registry) == {"openai"}


def test_every_trusted_model_field_is_checked_and_override_is_canonical_only():
    graph, registry = delegated_fixture(override="Anthropic")
    declaration = ModelInput(name="embedding_model", model_type="embedding").to_dict()
    registry["LanguageModelComponent"]["template"]["embedding_model"] = declaration
    saved = copy.deepcopy(declaration)
    saved["value"] = [{"provider": "Ollama", "name": "fixture"}]
    graph["nodes"][0]["data"]["node"]["template"]["embedding_model"] = saved

    assert _component_providers(graph, registry) == {"anthropic", "ollama"}


@pytest.mark.parametrize(
    "selection",
    [
        "connect_other_models",
        "runtime-model-name",
        [],
        {},
        [{"provider": "not-registered-anywhere"}],
        [{"provider": None}],
        [{"provider": 123}],
        [{"provider": "OpenAI"}, "bad entry"],
    ],
)
def test_unknown_malformed_and_dynamic_selections_are_unverifiable(selection):
    from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError

    graph, registry = delegated_fixture(selection=selection)
    with pytest.raises(ProviderSelectionUnverifiableError):
        _component_providers(graph, registry)


@pytest.mark.parametrize("field", ["model", "provider"])
def test_global_variable_selections_are_never_resolved(field):
    from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError

    graph, registry = delegated_fixture(override="Anthropic")
    graph["nodes"][0]["data"]["node"]["template"][field]["load_from_db"] = True
    with pytest.raises(ProviderSelectionUnverifiableError):
        _component_providers(graph, registry)


def test_saved_input_metadata_cannot_hide_a_trusted_model_field():
    graph, registry = delegated_fixture()
    graph["nodes"][0]["data"]["node"]["template"]["model"].update(_input_type="StrInput", type="str")
    assert _component_providers(graph, registry) == {"openai"}


@pytest.mark.parametrize("legacy", ["OpenAI", "openai", "Anthropic"])
def test_legacy_agent_selector_uses_known_provider_aliases(legacy):
    graph, registry = delegated_fixture()
    registry["LanguageModelComponent"]["template"].pop("model")
    saved = graph["nodes"][0]["data"]["node"]["template"]
    saved.pop("model")
    saved["agent_llm"] = DropdownInput(name="agent_llm", value=legacy).to_dict()
    assert _component_providers(graph, registry) == {legacy.casefold()}


@pytest.mark.parametrize("legacy", ["Custom", "Unknown Legacy Provider", 123])
def test_unresolved_legacy_agent_selection_is_manual(legacy):
    from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError

    graph, registry = delegated_fixture()
    graph["nodes"][0]["data"]["node"]["template"]["agent_llm"] = {"value": legacy}
    with pytest.raises(ProviderSelectionUnverifiableError):
        _component_providers(graph, registry)


def test_connected_selection_remains_unverifiable_through_a_group_proxy():
    from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError

    graph, registry = delegated_fixture()
    inner_id = graph["nodes"][0]["id"]
    group = {
        "id": "group",
        "data": {
            "node": {"template": {"selected": {"proxy": {"id": inner_id, "field": "model"}}}, "flow": {"data": graph}}
        },
    }
    outer = {"nodes": [group], "edges": [{"target": "group", "data": {"targetHandle": {"fieldName": "selected"}}}]}
    with pytest.raises(ProviderSelectionUnverifiableError):
        _component_providers(outer, registry)


def test_unknown_standalone_identity_is_not_derived_into_proof():
    from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError

    graph, registry = delegated_fixture()
    registry["LanguageModelComponent"]["metadata"] = {"model_provider_id": "unknown-fixed-provider"}
    with pytest.raises(ProviderSelectionUnverifiableError):
        _component_providers(graph, registry)
