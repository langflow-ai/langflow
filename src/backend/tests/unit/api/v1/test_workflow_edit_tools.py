from uuid import uuid4

import pytest
from langflow.api.v1.mcp_utils import handle_list_tools
from langflow.api.v1.workflow_edit_tools import apply_workflow_patch

# Fake user_id for tests
TEST_USER_ID = uuid4()


@pytest.mark.asyncio
async def test_mcp_list_tools_includes_workflow_tools():
    tools = await handle_list_tools()
    tool_names = {t.name for t in tools}
    assert "lf_workflow_get" in tool_names
    assert "lf_workflow_validate" in tool_names
    assert "lf_workflow_patch" in tool_names


@pytest.mark.asyncio
async def test_apply_workflow_patch_sets_node_template_value():
    payload = {
        "nodes": [
            {
                "id": "n1",
                "data": {"node": {"template": {"input_value": {"type": "str", "value": "old", "show": True}}}},
            }
        ],
        "edges": [],
    }
    patch = {
        "ops": [
            {
                "op": "set_node_template_value",
                "node_id": "n1",
                "field": "input_value",
                "value": "new",
            }
        ]
    }
    updated = await apply_workflow_patch(payload, patch, user_id=TEST_USER_ID)
    assert updated["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] == "new"


@pytest.mark.asyncio
async def test_apply_workflow_patch_remove_node_also_removes_connected_edges():
    payload = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"id": "e1", "source": "a", "target": "b"}],
    }
    patch = {"ops": [{"op": "remove_node", "node_id": "a"}]}
    updated = await apply_workflow_patch(payload, patch, user_id=TEST_USER_ID)
    assert [n["id"] for n in updated["nodes"]] == ["b"]
    assert updated["edges"] == []


@pytest.mark.asyncio
async def test_apply_workflow_patch_add_edge_updates_selected_output_for_multi_output_nodes():
    payload = {
        "nodes": [
            {
                "id": "QueryRouter-abc",
                "type": "genericNode",
                "data": {
                    "id": "QueryRouter-abc",
                    "type": "QueryRouter",
                    "selected_output": "text_output",
                    "node": {
                        "outputs": [
                            {"name": "text_output", "types": ["Message"]},
                            {"name": "model_output", "types": ["LanguageModel"]},
                        ],
                        "template": {},
                    },
                },
            },
            {
                "id": "Agent-xyz",
                "type": "genericNode",
                "data": {
                    "id": "Agent-xyz",
                    "type": "Agent",
                    "node": {
                        "outputs": [{"name": "response", "types": ["Message"]}],
                        "template": {"agent_llm": {"type": "str", "value": "", "input_types": ["LanguageModel"]}},
                    },
                },
            },
        ],
        "edges": [],
    }
    patch = {
        "ops": [
            {
                "op": "add_edge",
                "edge": {
                    "source": "QueryRouter-abc",
                    "target": "Agent-xyz",
                    "sourceHandle": "model_output",
                    "targetHandle": "agent_llm",
                },
            }
        ]
    }
    updated = await apply_workflow_patch(payload, patch, user_id=TEST_USER_ID)
    assert updated["nodes"][0]["data"]["selected_output"] == "model_output"
