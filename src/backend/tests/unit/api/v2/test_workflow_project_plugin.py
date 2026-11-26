"""An installed project plugin survives form/save/archive and runs through Workflows."""

# ruff: noqa: F811 -- The real entry-point fixture is shared with save acceptance.

from copy import deepcopy
from uuid import UUID

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.flow_builder import add_component, add_connection
from pydantic import Field

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)
from tests.unit.api.v1.test_project_save_hooks import installed_save_plugin, versions  # noqa: F401
from tests.unit.api.v2.test_workflow_skills import wait_status


class SupportModel(BaseChatModel):
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "offline-project-plugin-acceptance"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        instructions = next(message.content for message in messages if isinstance(message, SystemMessage))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"Support received: {instructions}"))])


@pytest.mark.parametrize(
    ("mode", "protocol", "missing_plugin"),
    [
        ("sync", "langflow", False),
        ("stream", "langflow", False),
        ("stream", "agui", False),
        ("background", "langflow", False),
        ("sync", "langflow", True),
    ],
)
async def test_installed_type_round_trip_executes_via_workflows(
    client,
    logged_in_headers,
    active_user,
    created_api_key,
    installed_save_plugin,
    monkeypatch,
    mode,
    protocol,
    missing_plugin,
):
    catalog = (await client.get("/api/v1/projects/types", headers=logged_in_headers)).json()
    form = next(item for item in catalog if item["name"] == installed_save_plugin.name)
    assert form["template"]["instructions"]["display_name"] == "Instructions"
    project = await create_project(client, logged_in_headers, name="Support acceptance", project_type=form["name"])
    data = agent_flow_data()
    registry = {}
    for component in (ChatInput, ChatOutput):
        node = component().to_frontend_node()["data"]["node"]
        node["field_order"] = [item.name for item in component.inputs]
        registry[component.name] = node
    payload = {"data": data}
    source = add_component(payload, "ChatInput", registry, component_id="ChatInput-request")
    output = add_component(payload, "ChatOutput", registry, component_id="ChatOutput-answer")
    add_connection(payload, source["id"], "message", "Agent-1", "input_value")
    add_connection(payload, "Agent-1", "response", output["id"], "input_value")
    template = data["nodes"][0]["data"]["node"]["template"]
    template["model"]["value"] = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]
    template["add_current_date_tool"]["value"] = False
    target = await create_flow(active_user, folder_id=project, name="Support agent", data=data)
    reference = await create_flow(active_user, folder_id=project, name="Reviewed source", data=echo_flow_data())
    saved = await save_config(
        client,
        logged_in_headers,
        project,
        {"instructions": "  Answer clearly from the support policy.  ", "source_id": reference},
    )
    assert saved["project_config"]["instructions"] == "Answer clearly from the support policy."
    archive = await client.get(f"/api/v1/projects/download/{project}", headers=logged_in_headers)
    assert archive.status_code == 200, archive.text
    upload = await client.post(
        "/api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("support.zip", archive.content, "application/zip")},
    )
    assert upload.status_code == 201, upload.text
    imported = next(
        flow for flow in upload.json() if any(node["data"]["type"] == "Agent" for node in flow["data"]["nodes"])
    )
    assert imported["id"] != target
    detail = (await client.get(f"/api/v1/projects/{imported['folder_id']}", headers=logged_in_headers)).json()
    assert detail["project_type"] == installed_save_plugin.name
    config = detail["project_config"]
    assert config["source_id"] != reference
    assert str((await versions(config["source_id"]))[0].id) == config["source_version"]
    assert (await save_config(client, logged_in_headers, imported["folder_id"], config))["flows_updated"] == 0

    # No original identity remains available to accidentally satisfy an imported reference.
    async with session_scope() as session:
        for original in (target, reference):
            row = await session.get(Flow, UUID(original))
            await session.delete(row)
    if missing_plugin:
        from lfx.projects import get_project_type, registry

        original = registry._PROJECT_TYPES
        without_plugin = type(original)(
            adapter_type=original.adapter_type,
            entry_point_group=original.entry_point_group,
            config_section_path=original.config_section_path,
        )
        for key in original.list_keys():
            if key != installed_save_plugin.name:
                without_plugin.register_class(key, original.get_class(key))
        without_plugin._discovered = True
        monkeypatch.setattr(registry, "_PROJECT_TYPES", without_plugin)
        with pytest.raises(ValueError, match="not registered"):
            get_project_type(installed_save_plugin.name)
        read = await client.get(f"/api/v1/projects/{imported['folder_id']}", headers=logged_in_headers)
        assert read.json()["project_type"] == installed_save_plugin.name
        refused = await client.get(f"/api/v1/projects/download/{imported['folder_id']}", headers=logged_in_headers)
        assert refused.status_code == 422
        refused = await client.post(
            "/api/v1/projects/upload/",
            headers=logged_in_headers,
            files={"file": ("support.zip", archive.content, "application/zip")},
        )
        assert refused.status_code == 422

    model = SupportModel()
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_kwargs: model)
    monkeypatch.setattr("lfx.components.models_and_agents.agent.get_llm", lambda **_kwargs: model)
    headers = {"x-api-key": created_api_key.api_key}
    response = await client.post(
        "/api/v2/workflows",
        headers=headers,
        json={
            "flow_id": imported["id"],
            "input_value": "Help with my request",
            "mode": mode,
            "stream_protocol": protocol,
        },
    )
    assert response.status_code == 200, response.text
    if mode == "background":
        status = await wait_status(client, headers, response.json()["job_id"], {"completed", "failed", "cancelled"})
        assert status["status"] == "completed", status
    else:
        assert "Support received: Answer clearly from the support policy." in response.text
        if protocol == "agui":
            assert "RUN_FINISHED" in response.text
    assert model.seen
    assert any(
        message.content == "Answer clearly from the support policy."
        for message in model.seen[0]
        if isinstance(message, SystemMessage)
    )
    assert (await stored_flow(imported["id"])).folder_id == UUID(imported["folder_id"])
