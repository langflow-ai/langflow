"""Substitution must be visible even when a customized built-in runs successfully."""

import json
import pathlib
from copy import deepcopy
from importlib.resources import files

import pytest
from lfx.interface import components
from lfx.services.deps import get_settings_service
from lfx.utils.flow_validation import describe_component_code_substitution

HARD_FLOWS = pathlib.Path(__file__).parents[2] / "data" / "component_compat" / "hard_flows"


@pytest.fixture
def saved_agent(monkeypatch):
    registry = dict(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())["entries"])
    cache = components.ComponentCache()
    cache.all_types_dict = registry
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", False)
    monkeypatch.setattr(settings, "substitute_outdated_component_code", True)
    saved = deepcopy(registry["models_and_agents"]["Agent"])
    return {"nodes": [{"id": "Agent-qa", "data": {"id": "Agent-qa", "type": "Agent", "node": saved}}], "edges": []}


@pytest.mark.parametrize("change_inputs", [False, True], ids=["code-only", "forked-inputs"])
def test_warning_names_the_policy_and_preserves_saved_code(saved_agent, change_inputs):
    node = saved_agent["nodes"][0]["data"]["node"]
    node["template"]["code"]["value"] += "\n# Customized Agent\n"
    if change_inputs:
        node["template"].pop("model")
    original = deepcopy(saved_agent)

    warning = describe_component_code_substitution(saved_agent)

    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in warning
    assert "Agent (Agent-qa)" in warning
    assert "server" in warning
    assert "saved flow is unchanged" in warning
    assert "Review and update" in warning
    assert saved_agent == original


def test_matching_component_needs_no_warning(saved_agent):
    assert describe_component_code_substitution(saved_agent) is None


@pytest.mark.parametrize("setting", ["allow_custom_components", "substitute_outdated_component_code"])
def test_warning_requires_substitution_to_be_enabled(saved_agent, monkeypatch, setting):
    saved_agent["nodes"][0]["data"]["node"]["template"]["code"]["value"] += "\n# customization\n"
    monkeypatch.setattr(get_settings_service().settings, setting, setting == "allow_custom_components")
    assert describe_component_code_substitution(saved_agent) is None


def test_warning_can_omit_component_identities(saved_agent):
    saved_agent["nodes"][0]["data"]["node"]["template"]["code"]["value"] += "\n# customization\n"
    warning = describe_component_code_substitution(saved_agent, include_component_names=False)
    assert warning is not None
    assert "Agent" not in warning
    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in warning
    assert "Ask the flow owner" in warning
    assert "flow editor" not in warning


def test_warning_includes_nested_substitutions_once(saved_agent):
    saved_agent["nodes"][0]["data"]["node"]["template"]["code"]["value"] += "\n# customization\n"
    wrapper = {"nodes": [{"data": {"type": "GroupNode", "node": {"flow": {"data": saved_agent}}}}]}
    warning = describe_component_code_substitution(wrapper)
    assert warning.count("Agent (Agent-qa)") == 1


@pytest.mark.parametrize(
    ("allow_custom", "substitute"),
    [(False, True), (False, False), (True, True), (True, False)],
    ids=["substitution-on", "substitution-off", "permissive", "permissive-substitution-off"],
)
@pytest.mark.parametrize("code_current", [False, True], ids=["drifted", "current"])
@pytest.mark.parametrize("include_component_names", [True, False], ids=["owner", "shared"])
def test_retired_component_is_named_with_its_replacement(
    monkeypatch, include_component_names, code_current, allow_custom, substitute
):
    """Updating a retired component cannot help: it fails whatever code runs, in every mode."""
    from lfx.components.chroma.chroma import ChromaVectorStoreComponent
    from lfx.custom.utils import create_component_template

    chroma = create_component_template(component_extractor=ChromaVectorStoreComponent())[0]
    cache = components.ComponentCache()
    cache.all_types_dict = {"chroma": {"Chroma": chroma}}
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", allow_custom)
    monkeypatch.setattr(settings, "substitute_outdated_component_code", substitute)
    flow = json.loads((HARD_FLOWS / "v1.12.6" / "chroma_legacy_type.json").read_text(encoding="utf-8"))["data"]
    if code_current:
        saved = next(node for node in flow["nodes"] if node["data"]["type"] == "Chroma")["data"]["node"]
        saved["template"]["code"]["value"] = chroma["template"]["code"]["value"]

    warning = describe_component_code_substitution(flow, include_component_names=include_component_names)

    assert warning == (
        "Chroma DB (Chroma-9e7b2) was retired in 1.13.0 and fails when the flow runs. "
        "Replace it with files_and_knowledge.Knowledge."
        if include_component_names
        else "Some components in this flow were retired and fail when the flow runs. "
        "Ask the flow owner to replace them."
    )


@pytest.mark.parametrize("with_outdated", [False, True], ids=["retired-only", "with-outdated"])
def test_refusal_names_a_retired_component_with_its_replacement(monkeypatch, with_outdated):
    """With substitution off, a drifted retired component is refused with its replacement, not sent to an update."""
    from lfx.components.chroma.chroma import ChromaVectorStoreComponent
    from lfx.custom.utils import create_component_template
    from lfx.utils.flow_validation import CustomComponentValidationError, validate_flow_for_current_settings

    registry = dict(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text())["entries"])
    registry["chroma"] = {"Chroma": create_component_template(component_extractor=ChromaVectorStoreComponent())[0]}
    cache = components.ComponentCache()
    cache.all_types_dict = registry
    cache.all_types_ready = True
    monkeypatch.setattr(components, "component_cache", cache)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", False)
    monkeypatch.setattr(settings, "substitute_outdated_component_code", False)
    flow = json.loads((HARD_FLOWS / "v1.12.6" / "chroma_legacy_type.json").read_text(encoding="utf-8"))["data"]
    for node in flow["nodes"]:
        component_type = node["data"]["type"]
        if component_type != "Chroma":
            code = registry["input_output"][component_type]["template"]["code"]["value"]
            drift = "\n# edited\n" if with_outdated and component_type == "ChatInput" else ""
            node["data"]["node"]["template"]["code"]["value"] = code + drift

    with pytest.raises(CustomComponentValidationError) as refusal:
        validate_flow_for_current_settings(flow)

    retired = (
        "Chroma DB (Chroma-9e7b2) was retired in 1.13.0 and fails when the flow runs. "
        "Replace it with files_and_knowledge.Knowledge."
    )
    assert str(refusal.value) == (
        "Flow build blocked: outdated components must be updated before running: "
        f"Chat Input (ChatInput-1e6ab). {retired}"
        if with_outdated
        else f"Flow build blocked: {retired}"
    )


def test_unknown_component_is_not_reported_as_a_substitution(saved_agent):
    saved_agent["nodes"][0]["data"]["type"] = "UnknownCustomComponent"
    assert describe_component_code_substitution(saved_agent) is None


@pytest.mark.parametrize("allow_custom", [False, True], ids=["substituted", "saved-code"])
@pytest.mark.usefixtures("saved_agent")
async def test_code_only_edit_warns_when_server_component_succeeds(monkeypatch, allow_custom):
    """Exercise a real component without an external model, including the permissive control."""
    from lfx.graph import Graph

    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", allow_custom)
    saved = deepcopy(components.component_cache.all_types_dict["input_output"]["ChatInput"])
    code = saved["template"]["code"]["value"]
    signature = "async def message_response(self) -> Message:\n"
    assert signature in code
    saved["template"]["code"]["value"] = code.replace(
        signature, signature + '        raise RuntimeError("CUSTOM_CODE_RAN")\n', 1
    )
    payload = {
        "nodes": [{"id": "ChatInput-qa", "data": {"id": "ChatInput-qa", "type": "ChatInput", "node": saved}}],
        "edges": [],
    }
    warning = describe_component_code_substitution(payload)
    graph = Graph.from_payload(deepcopy(payload), emit_extension_events=False)
    graph.persist_messages = False
    component = graph.get_vertex("ChatInput-qa").custom_component
    component.set(input_value="Server component completed", should_store_message=False)

    if allow_custom:
        assert warning is None
        with pytest.raises(RuntimeError, match="CUSTOM_CODE_RAN"):
            await component.message_response()
    else:
        assert "Chat Input (ChatInput-qa)" in warning
        result = await component.message_response()
        assert result.text == "Server component completed"
        assert "CUSTOM_CODE_RAN" in saved["template"]["code"]["value"]
