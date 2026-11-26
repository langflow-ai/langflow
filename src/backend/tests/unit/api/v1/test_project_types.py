"""``GET /api/v1/projects/types`` serves the project type vocabulary.

The UI needs the list of types and the form each one renders before a project exists, so the
endpoint reads the lfx registry directly: no database rows, no component cache.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from lfx.projects import all_project_types


@pytest.fixture
def custom_project_type(monkeypatch):
    from lfx.inputs.inputs import StrInput
    from lfx.projects import (
        FireTiming,
        ProjectTypeDefinition,
        ProjectTypeField,
        SlotDefinition,
        get_slot,
        register_project_type,
        register_slot,
        registry,
    )

    original = registry._PROJECT_TYPES
    isolated = type(original)(
        adapter_type=original.adapter_type,
        entry_point_group=original.entry_point_group,
        config_section_path=original.config_section_path,
    )
    for name in original.list_keys():
        isolated.register_class(name, original.get_class(name))
    monkeypatch.setattr(registry, "_PROJECT_TYPES", isolated)
    monkeypatch.setattr(registry, "_SLOT_DEFINITIONS", dict(registry._SLOT_DEFINITIONS))

    class SupportInstructions(SlotDefinition):
        def binding_contract(self):
            return get_slot("Instructions").binding_contract()

        def binding_outputs(self, data):
            # This plugin chooses only the first compatible output.
            return super().binding_outputs(data)[:1]

        def build_baseline(self, initial_value=None, *, initial_config=None):
            return get_slot("Instructions").build_baseline(initial_value, initial_config=initial_config)

    instructions = register_slot(
        SupportInstructions(
            "SupportInstructions",
            "Message",
            FireTiming.ONCE_PER_RUN,
            default_flow_ref="test:support-instructions",
            binding_kind="instructions",
            binding_label="Briefing",
            validation_hint="Connect a support briefing output.",
        )
    )

    @register_project_type
    class CustomProjectType(ProjectTypeDefinition):
        name = "test-custom-project"
        display_name = "Custom project"
        icon = "Box"
        description = "A plugin-defined form."
        fields = (
            ProjectTypeField(name="team", input=StrInput(name="team", display_name="Team")),
            ProjectTypeField(
                name="briefing",
                input=StrInput(name="briefing", display_name="Briefing"),
                slot_definition=instructions,
                supports_flow_binding=True,
            ),
        )

    return CustomProjectType, original


async def test_plugin_slot_drives_baseline_discovery_and_draft_validation(
    client, logged_in_headers, custom_project_type
):
    from copy import deepcopy

    from lfx.projects.bindings import instruction_outputs

    definition, _ = custom_project_type
    created = await client.post(
        "api/v1/projects/",
        headers=logged_in_headers,
        json={"name": "Support project", "project_type": definition.name},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    endpoint = f"api/v1/projects/{project_id}"
    baseline = await client.post(
        f"{endpoint}/flow-baseline?field_name=briefing",
        headers=logged_in_headers,
        json={"initial_value": "Cite the support guide."},
    )
    assert baseline.status_code == 200
    flow = baseline.json()
    assert flow["data"]["harness_contract"] == {"slot": "SupportInstructions", "field_name": "briefing"}
    second = deepcopy(flow["data"]["nodes"][0])
    second["id"] += "-second"
    flow["data"]["nodes"].append(second)
    assert len(instruction_outputs(flow["data"])) == 2
    saved = await client.post("api/v1/flows/", headers=logged_in_headers, json=flow)
    assert saved.status_code == 201
    choices = await client.get(f"{endpoint}/flow-outputs?field_name=briefing", headers=logged_in_headers)
    assert choices.status_code == 200
    assert len(choices.json()) == 1
    checked = await client.post(
        f"{endpoint}/flow-outputs/validate?field_name=briefing",
        headers=logged_in_headers,
        json={"data": flow["data"]},
    )
    assert checked.status_code == 200
    assert checked.json()["valid"] is True
    assert len(checked.json()["outputs"]) == 1
    invalid = await client.post(
        f"{endpoint}/flow-outputs/validate?field_name=briefing",
        headers=logged_in_headers,
        json={"data": {"nodes": [], "edges": []}},
    )
    assert invalid.json() == {"valid": False, "outputs": [], "reason": "Connect a support briefing output."}


async def test_custom_type_form_and_config_use_existing_api(client, logged_in_headers, custom_project_type):
    definition, _ = custom_project_type
    response = await client.get("api/v1/projects/types", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    template = next(item for item in response.json() if item["name"] == definition.name)["template"]
    assert template["team"]["display_name"] == "Team"

    response = await client.post(
        "api/v1/projects/",
        json={"name": "Plugin project", "project_type": definition.name, "project_config": {"team": "Support"}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["project_type"] == definition.name
    assert response.json()["project_config"]["team"] == "Support"


async def test_missing_plugin_preserves_existing_project_on_read(
    client, logged_in_headers, custom_project_type, monkeypatch
):
    from lfx.projects import registry

    definition, without_plugin = custom_project_type
    created = await client.post(
        "api/v1/projects/",
        json={
            "name": "Retained plugin project",
            "project_type": definition.name,
            "project_config": {"team": "Support"},
        },
        headers=logged_in_headers,
    )
    assert created.status_code == status.HTTP_201_CREATED
    saved = created.json()
    monkeypatch.setattr(registry, "_PROJECT_TYPES", without_plugin)

    read = await client.get(f"api/v1/projects/{saved['id']}", headers=logged_in_headers)
    assert read.status_code == status.HTTP_200_OK
    assert read.json()["project_type"] == definition.name
    assert read.json()["project_config"] == saved["project_config"]


@pytest.fixture
def harness_from_api():
    async def _fetch(client, headers):
        response = await client.get("api/v1/projects/types", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        return next(t for t in response.json() if t["name"] == "agent-harness")

    return _fetch


async def test_lists_every_registered_type(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/types", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert [t["name"] for t in response.json()] == [t.name for t in all_project_types()]


async def test_each_type_carries_what_the_ui_needs_to_present_it(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/types", headers=logged_in_headers)

    for project_type in response.json():
        assert project_type["display_name"], f"{project_type['name']} has no label"
        assert project_type["icon"], f"{project_type['name']} has no icon"
        assert project_type["description"], f"{project_type['name']} has no description"


async def test_requires_authentication(client: AsyncClient):
    response = await client.get("api/v1/projects/types")

    assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


async def test_the_route_is_not_parsed_as_a_project_id(client: AsyncClient, logged_in_headers):
    """``/types`` sits next to ``/{project_id}``, so declaration order decides which one wins."""
    response = await client.get("api/v1/projects/types", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


async def test_flows_has_no_form(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/types", headers=logged_in_headers)

    flows = next(t for t in response.json() if t["name"] == "flows")
    assert flows["template"] == {}


async def test_the_harness_form_renders_with_canvas_widgets(client, logged_in_headers, harness_from_api):
    """Each field must arrive in the shape the frontend's field renderer already reads."""
    harness = await harness_from_api(client, logged_in_headers)

    assert list(harness["template"]) == [
        "system_prompt",
        "model",
        "tools",
        "tool_packs",
        "n_messages",
        "skill_packs",
        "tool_policy",
        "context_strategy",
        "context_turns",
        "compaction",
        "compaction_trigger_tokens",
        "compaction_keep_messages",
        "max_iterations",
        "hooks",
    ]
    for name, field in harness["template"].items():
        assert field["name"] == name
        assert field["type"], f"{name} has no widget type"
        assert field["display_name"], f"{name} has no label"


async def test_the_form_carries_the_sections_it_should_be_grouped_into(client, logged_in_headers, harness_from_api):
    """The type decides how its form reads, so the UI does not hardcode the grouping."""
    harness = await harness_from_api(client, logged_in_headers)

    sections = [field["section"] for field in harness["template"].values()]
    assert sections == ["Instructions", "Model", "Tools", "Tools", "Runtime", "Skills", *(["Runtime"] * 7), "Hooks"]
    assert harness["template"]["tool_packs"]["show"] is True
    assert harness["template"]["hooks"]["show"] is True
    assert harness["template"]["hooks"]["renders"] == "hook_flows"


async def test_the_form_exposes_shared_contracts_without_changing_config_keys(
    client, logged_in_headers, harness_from_api
):
    harness = await harness_from_api(client, logged_in_headers)
    template = harness["template"]

    assert template["system_prompt"]["flow_contract"] == {
        "name": "Instructions",
        "terminal_output_type": "Message",
        "fire_timing": "once_per_run",
        "cardinality": "single",
        "default_flow_ref": "builtin:instructions",
        "binding": {
            "kind": "instructions",
            "label": "Instructions",
            "validation_hint": "Configure required inputs and connect a terminal text output.",
            "initial_config_fields": [],
            "defaults": {},
        },
    }
    assert template["tools"]["flow_contract"]["name"] == "Tool"
    assert template["tools"]["flow_contract"]["cardinality"] == "multi"
    assert "flow_contract" not in template["model"]
    assert "flow_contract" not in template


async def test_visible_fields_use_available_page_widgets(client, logged_in_headers, harness_from_api):
    """Every other field has to render with a shipped canvas widget, or the form is bespoke."""
    harness = await harness_from_api(client, logged_in_headers)

    bespoke = {name: f["renders"] for name, f in harness["template"].items() if f.get("renders") and f.get("show")}
    assert bespoke == {
        "system_prompt": "long_text",
        "tools": "project_flows",
        "tool_packs": "project_refs",
        "skill_packs": "skill_pack_refs",
        "hooks": "hook_flows",
    }


async def test_the_harness_form_can_be_saved_as_a_project_config(client, logged_in_headers, harness_from_api):
    """The defaults the form ships must be a config the API accepts back."""
    harness = await harness_from_api(client, logged_in_headers)
    defaults = {name: field.get("value") for name, field in harness["template"].items()}

    response = await client.post(
        "api/v1/projects/",
        json={"name": "Harness from the form", "project_type": "agent-harness", "project_config": defaults},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    created = response.json()
    assert created["project_type"] == "agent-harness"
    assert created["project_config"]["n_messages"] == defaults["n_messages"]
