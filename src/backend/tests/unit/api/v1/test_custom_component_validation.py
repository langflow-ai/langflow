"""Tests for custom component validation in flow endpoints.

These tests verify that custom components are properly blocked when
LANGFLOW_ALLOW_CUSTOM_COMPONENTS is disabled.
"""

import json

from fastapi import status
from httpx import AsyncClient

# Sample custom component code that will be blocked
CUSTOM_COMPONENT_CODE = """
from lfx.custom import Component

class MyCustomComponent(Component):
    display_name = "My Custom Component"

    def build(self):
        return "test"
"""

# Sample edited built-in component code
EDITED_BUILTIN_CODE = """
from lfx.base.io.chat import ChatComponent
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

class ChatInput(ChatComponent):
    display_name = "I am a custom component"
    description = "Get chat inputs from the Playground."

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Text",
            value="",
        ),
    ]
    outputs = [
        Output(display_name="Chat Message", name="message", method="message_response"),
    ]

    async def message_response(self) -> Message:
        print(f"asdf")
        message = await Message.create(text=self.input_value)
        return message
"""


def create_flow_with_custom_component(component_type="CustomComponent", code=CUSTOM_COMPONENT_CODE, edited=False):  # noqa: FBT002
    """Helper to create flow data with a custom component."""
    return {
        "name": "test_flow_with_custom",
        "data": {
            "nodes": [
                {
                    "id": "custom-1",
                    "data": {
                        "type": component_type,
                        "node": {
                            "display_name": "My Custom Component",
                            "edited": edited,
                            "template": {"code": {"value": code}},
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


def create_flow_with_edited_builtin(code=EDITED_BUILTIN_CODE):
    """Helper to create flow data with an edited built-in component."""
    return create_flow_with_custom_component(component_type="ChatInput", code=code, edited=True)


async def test_create_flow_blocks_custom_component(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/ blocks custom components."""
    flow_data = create_flow_with_custom_component()

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()
    assert "custom component" in response.json()["detail"].lower()


async def test_create_flow_blocks_edited_builtin_component(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/ blocks edited built-in components."""
    flow_data = create_flow_with_edited_builtin()

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_update_flow_blocks_custom_component(client: AsyncClient, logged_in_headers):
    """Test that PATCH /flows/{id} blocks custom components."""
    # First create a flow without custom components
    initial_flow = {"name": "test_flow", "data": {"nodes": [], "edges": []}}
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Try to update with custom component
    update_data = create_flow_with_custom_component()
    del update_data["name"]  # PATCH doesn't require name

    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_update_flow_blocks_edited_builtin(client: AsyncClient, logged_in_headers):
    """Test that PATCH /flows/{id} blocks edited built-in components."""
    # First create a flow
    initial_flow = {"name": "test_flow", "data": {"nodes": [], "edges": []}}
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    flow_id = create_response.json()["id"]

    # Try to update with edited built-in
    update_data = create_flow_with_edited_builtin()
    del update_data["name"]

    response = await client.patch(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_upsert_flow_blocks_custom_component_on_create(client: AsyncClient, logged_in_headers):
    """Test that PUT /flows/{id} blocks custom components when creating."""
    import uuid

    flow_id = str(uuid.uuid4())
    flow_data = create_flow_with_custom_component()

    response = await client.put(f"api/v1/flows/{flow_id}", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_upsert_flow_blocks_custom_component_on_update(client: AsyncClient, logged_in_headers):
    """Test that PUT /flows/{id} blocks custom components when updating."""
    # First create a flow
    initial_flow = {"name": "test_flow", "data": {"nodes": [], "edges": []}}
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    flow_id = create_response.json()["id"]

    # Try to upsert with custom component
    update_data = create_flow_with_custom_component()

    response = await client.put(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_batch_create_blocks_custom_components(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/batch/ blocks flows with custom components."""
    flows = [create_flow_with_custom_component(), {"name": "normal_flow", "data": {"nodes": [], "edges": []}}]

    response = await client.post("api/v1/flows/batch/", json={"flows": flows}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()
    assert "test_flow_with_custom" in response.json()["detail"]


async def test_batch_create_allows_all_valid_flows(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/batch/ succeeds when all flows are valid."""
    flows = [
        {"name": "flow_1", "data": {"nodes": [], "edges": []}},
        {"name": "flow_2", "data": {"nodes": [], "edges": []}},
    ]

    response = await client.post("api/v1/flows/batch/", json={"flows": flows}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.json()) == 2


async def test_upload_flow_blocks_custom_component(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/upload/ blocks custom components."""
    flow_data = create_flow_with_custom_component()
    file_content = json.dumps({"flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_upload_flow_blocks_edited_builtin(client: AsyncClient, logged_in_headers):
    """Test that POST /flows/upload/ blocks edited built-in components."""
    flow_data = create_flow_with_edited_builtin()
    file_content = json.dumps({"flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "blocked" in response.json()["detail"].lower()


async def test_upload_multiple_flows_blocks_if_any_has_custom_component(client: AsyncClient, logged_in_headers):
    """Test that upload blocks all flows if any contains custom components."""
    flows = [
        {"name": "valid_flow", "data": {"nodes": [], "edges": []}},
        create_flow_with_custom_component(),
        {"name": "another_valid_flow", "data": {"nodes": [], "edges": []}},
    ]
    file_content = json.dumps({"flows": flows})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "test_flow_with_custom" in response.json()["detail"]


async def test_create_flow_allows_flow_without_nodes(client: AsyncClient, logged_in_headers):
    """Test that flows without nodes are allowed."""
    flow_data = {
        "name": "empty_flow",
        "data": {},  # No nodes
    }

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED


async def test_validation_error_message_includes_component_name(client: AsyncClient, logged_in_headers):
    """Test that error messages include the blocked component's display name."""
    flow_data = create_flow_with_custom_component()

    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # Should mention the component name
    assert "My Custom Component" in response.json()["detail"] or "custom" in response.json()["detail"].lower()


# Made with Bob
