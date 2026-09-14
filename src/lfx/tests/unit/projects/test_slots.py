"""Project forms share contracts without sharing presentation or runtime configuration."""

from dataclasses import replace

import pytest
from lfx.inputs.inputs import StrInput

from lfx.projects import (
    Cardinality,
    FireTiming,
    ProjectType,
    ProjectTypeField,
    SlotDefinition,
    all_slots,
    get_project_type,
    get_slot,
    register_project_type,
    register_slot,
    registered_project_types,
    registered_slots,
    registry,
)


@pytest.fixture(autouse=True)
def isolated_registries(monkeypatch):
    monkeypatch.setattr(registry, "_PROJECT_TYPES", dict(registry._PROJECT_TYPES))
    monkeypatch.setattr(registry, "_SLOT_DEFINITIONS", dict(registry._SLOT_DEFINITIONS))


def project_using(definition, *, name="test-project", field_name="custom"):
    return ProjectType(
        name=name,
        display_name="Test project",
        icon="Box",
        fields=(
            ProjectTypeField(
                name=field_name,
                input=StrInput(name=field_name, display_name=field_name),
                slot_definition=definition,
            ),
        ),
    )


def test_two_projects_reuse_one_contract_with_different_forms():
    tool = get_slot("Tool")
    harness = get_project_type("agent-harness")
    pack = register_project_type(project_using(tool, name="test-tool-pack", field_name="exports"))

    harness_tools = next(field for field in harness.fields if field.name == "tools")
    assert pack.fields[0].slot_definition is harness_tools.slot_definition
    assert pack.to_template()["exports"]["flow_contract"] == harness.to_template()["tools"]["flow_contract"]
    assert pack.to_template()["exports"]["display_name"] == "exports"
    assert harness.to_template()["tools"]["display_name"] == "Tools"


def test_unregistered_contract_rejects_project_without_partial_registration():
    definition = SlotDefinition("ResearchEvidence", "Data", FireTiming.ON_RESULT)
    project = project_using(definition)

    with pytest.raises(ValueError, match="ResearchEvidence"):
        register_project_type(project)

    assert project.name not in registered_project_types()
    register_slot(definition)
    assert register_project_type(project) is project


def test_equal_but_unregistered_copy_cannot_drift_from_the_registry():
    definition = replace(get_slot("Tool"))

    with pytest.raises(ValueError, match="registered definition"):
        register_project_type(project_using(definition))


def test_project_cannot_defer_contract_resolution_with_a_string():
    with pytest.raises(TypeError, match="SlotDefinition instance"):
        register_project_type(project_using("Tool"))


def test_slot_registration_requires_a_definition():
    with pytest.raises(TypeError, match="SlotDefinition instance"):
        register_slot("Tool")


def test_registration_is_idempotent_only_for_the_same_definition():
    definition = get_slot("Tool")

    assert register_slot(definition) is definition
    with pytest.raises(ValueError, match="already registered"):
        register_slot(replace(definition, terminal_output_type="Message"))
    assert get_slot("Tool") is definition


def test_unknown_slot_lists_available_contracts():
    with pytest.raises(ValueError, match=r"Registered slots: .*SystemPromptBuilder.*Tool"):
        get_slot("Unknown")


def test_all_contracts_are_available_in_stable_order():
    assert registered_slots() == (
        "AgenticLoop",
        "Compactor",
        "ContextManager",
        "Hook",
        "PermissionGate",
        "SystemPromptBuilder",
        "Tool",
    )
    assert tuple(definition.name for definition in all_slots()) == registered_slots()


def test_type_registration_rejects_fields_that_would_overwrite_each_other():
    project = project_using(get_slot("Tool"))
    project = replace(project, fields=project.fields + project.fields)

    with pytest.raises(ValueError, match="field 'custom' more than once"):
        register_project_type(project)

    assert project.name not in registered_project_types()


def test_scalar_fields_need_no_flow_contract():
    harness = get_project_type("agent-harness")

    assert "flow_contract" not in harness.to_template()["model"]
    field = ProjectTypeField(name="label", input=StrInput(name="label"))
    assert "flow_contract" not in field.to_template()


def test_contract_metadata_does_not_replace_the_existing_field_value_or_widget():
    template = get_project_type("agent-harness").to_template()

    assert template["tools"]["value"] == []
    assert template["tools"]["renders"] == "project_flows"
    assert template["tools"]["flow_contract"] == {
        "name": "Tool",
        "terminal_output_type": "Tool",
        "fire_timing": "on_llm_tool_call",
        "cardinality": "multi",
        "default_flow_ref": None,
    }
    assert template["n_messages"]["value"] == 100
    assert template["context_strategy"]["flow_contract"]["name"] == "ContextManager"
    assert template["tool_policy"]["flow_contract"]["name"] == "PermissionGate"
    assert not template["tool_policy"].get("supports_flow_binding", False)


def test_custom_contract_can_be_registered_before_a_component_cache_exists():
    definition = register_slot(
        SlotDefinition(
            "EvidenceGate",
            "EvidenceDecision",
            FireTiming.ON_RESULT,
            Cardinality.SINGLE,
            default_flow_ref="research/evidence-check",
        )
    )

    project = register_project_type(project_using(definition))

    assert project.to_template()["custom"]["flow_contract"]["default_flow_ref"] == "research/evidence-check"


def test_registered_vocabulary_does_not_claim_unbuilt_baseline_flows():
    assert {
        definition.name: definition.default_flow_ref for definition in all_slots() if definition.default_flow_ref
    } == {
        "SystemPromptBuilder": "builtin:instructions",
        "Hook": "builtin:hook",
        "ContextManager": "builtin:context",
    }
    # These contracts are ready for runtime adapters; no inert fields are added to the form.
    assert set(get_project_type("agent-harness").field_names()) == {
        "system_prompt",
        "model",
        "tools",
        "n_messages",
        "hooks",
        "tool_policy",
        "context_strategy",
        "context_turns",
        "compaction",
        "compaction_trigger_tokens",
        "compaction_keep_messages",
        "max_iterations",
    }
