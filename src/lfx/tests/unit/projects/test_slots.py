"""Project forms share contracts without sharing presentation or runtime configuration."""

from dataclasses import replace

import pytest
from lfx.inputs.inputs import StrInput
from lfx.projects import (
    Cardinality,
    FireTiming,
    ProjectTypeDefinition,
    ProjectTypeField,
    SlotDefinition,
    all_slots,
    get_project_type,
    get_slot,
    register_project_type,
    register_slot,
    registered_project_types,
    registered_slots,
)


def project_using(definition, *, name="test-project", field_name="custom"):
    class TestProjectType(ProjectTypeDefinition):
        display_name = "Test project"
        icon = "Box"
        fields = (
            ProjectTypeField(
                name=field_name,
                input=StrInput(name=field_name, display_name=field_name),
                slot_definition=definition,
            ),
        )

    TestProjectType.name = name
    return TestProjectType


def test_two_projects_reuse_one_contract_with_different_forms():
    tool = get_slot("Tool")
    harness = get_project_type("agent-harness")
    pack = register_project_type(project_using(tool, name="test-tool-pack", field_name="exports"))

    harness_tools = next(field for field in harness.fields if field.name == "tools")
    assert pack.fields[0].slot_definition is harness_tools.slot_definition
    assert pack().to_template()["exports"]["flow_contract"] == harness.to_template()["tools"]["flow_contract"]
    assert pack().to_template()["exports"]["display_name"] == "exports"
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
    with pytest.raises(ValueError, match=r"Registered slots: .*Instructions.*Tool"):
        get_slot("Unknown")


def test_all_contracts_are_available_in_stable_order():
    assert registered_slots() == (
        "AgenticLoop",
        "Compactor",
        "ContextManager",
        "Hook",
        "Instructions",
        "PermissionGate",
        "Scorer",
        "Tool",
    )
    assert tuple(definition.name for definition in all_slots()) == registered_slots()


def test_type_registration_rejects_fields_that_would_overwrite_each_other():
    project = project_using(get_slot("Tool"))
    project.fields += project.fields

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
    assert template["context_strategy"]["supports_flow_binding"]
    assert template["tool_policy"]["flow_contract"]["name"] == "PermissionGate"
    assert template["tool_policy"]["supports_flow_binding"]


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

    assert project().to_template()["custom"]["flow_contract"]["default_flow_ref"] == "research/evidence-check"


def test_registered_vocabulary_does_not_claim_unbuilt_baseline_flows():
    assert {
        definition.name: definition.default_flow_ref for definition in all_slots() if definition.default_flow_ref
    } == {
        "Instructions": "builtin:instructions",
        "Hook": "builtin:hook",
        "ContextManager": "builtin:context",
        "Compactor": "builtin:compaction",
        "PermissionGate": "builtin:permission",
    }
    # These contracts are ready for runtime adapters; no inert fields are added to the form.
    assert set(get_project_type("agent-harness").field_names()) == {
        "system_prompt",
        "model",
        "tools",
        "tool_packs",
        "skill_packs",
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


@pytest.mark.parametrize(
    ("slot_name", "timeout"),
    [("Instructions", None), ("Hook", 10), ("ContextManager", 30), ("Compactor", 60), ("PermissionGate", 10)],
)
def test_slot_owns_discovery_validation_and_binding_defaults(slot_name, timeout):
    from lfx.projects.bindings import FlowBinding, flow_revision

    slot = get_slot(slot_name)
    data = slot.build_baseline("Answer with sources.")["data"]
    selected = slot.binding_outputs(data)[0]
    model, _, _ = slot.binding_contract()
    values = {
        "flow_id": "reviewed-flow",
        "revision": flow_revision(data),
        "node_id": selected["node_id"],
        "output_name": selected["output_name"],
    }
    binding = model(**values, **({"on_event": "before_llm_call"} if slot_name == "Hook" else {}))
    slot.validate_binding(data, binding)
    assert slot.to_dict()["binding"]["defaults"].get("timeout_seconds") == timeout
    with pytest.raises(ValueError, match=r"selected .* output"):
        slot.validate_binding(data, binding.model_copy(update={"output_name": "not-the-reviewed-output"}))
    with pytest.raises(ValueError, match=r"flow (has )?changed"):
        slot.validate_binding(data, binding.model_copy(update={"revision": "stale"}))
    if model is not FlowBinding:
        with pytest.raises(ValueError, match="support flow bindings"):
            slot.validate_binding(data, FlowBinding(**values))


def test_project_field_resolves_its_slot_without_a_builtin_field_name():
    from lfx.projects.flow_slots import binding_outputs, binding_slot

    contract = get_slot("Instructions")
    project = project_using(contract, name="support", field_name="briefing")
    project.fields = (replace(project.fields[0], supports_flow_binding=True),)
    data = contract.build_baseline("Answer the support request.")["data"]
    assert binding_slot("briefing", project()) is contract
    assert binding_outputs("briefing", data, project_type=project()) == contract.binding_outputs(data)
    with pytest.raises(ValueError, match="support flow bindings"):
        binding_outputs("briefing", data)
