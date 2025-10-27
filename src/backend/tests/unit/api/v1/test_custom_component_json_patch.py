"""Tests for custom component JSON Patch endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_custom_component_json_patch_success(client: AsyncClient, logged_in_headers):
    """Test successful custom component update using JSON Patch."""
    # Simple component code
    component_code = """
from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.template import Output
from langflow.schema.message import Message

class TestComponent(Component):
    display_name = "Test Component"
    description = "A test component"

    inputs = [
        StrInput(name="input_text", display_name="Input Text", value="default"),
        StrInput(name="param2", display_name="Param 2", value="test"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Message:
        return Message(text=self.input_text)
"""

    # First, build the component to get the template
    build_response = await client.post(
        "api/v1/custom_component",
        json={"code": component_code},
        headers=logged_in_headers,
    )
    assert build_response.status_code == 200
    template = build_response.json()["data"]["template"]

    # Now update it using JSON Patch
    patch_payload = {
        "operations": [
            {"op": "replace", "path": "/code", "value": component_code},
            {"op": "replace", "path": "/template", "value": template},
            {"op": "replace", "path": "/field/input_text", "value": "updated_value"},
            {"op": "replace", "path": "/tool_mode", "value": False},
        ]
    }

    response = await client.post(
        "api/v1/custom_component/json-patch",
        json=patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    result = response.json()

    # Verify response structure
    assert result["success"] is True
    assert "updated_at" in result
    assert result["operations_applied"] == 4
    assert "component_node" in result
    assert "response_operations" in result

    # Verify the component node was updated
    component_node = result["component_node"]
    assert "template" in component_node
    assert "input_text" in component_node["template"]

    # Verify response operations were generated
    assert isinstance(result["response_operations"], list)


@pytest.mark.asyncio
async def test_custom_component_json_patch_without_code_fails(client: AsyncClient, logged_in_headers):
    """Test that JSON Patch without code fails."""
    patch_payload = {
        "operations": [
            {"op": "replace", "path": "/template", "value": {}},
        ]
    }

    response = await client.post(
        "api/v1/custom_component/json-patch",
        json=patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 400
    assert "code" in response.json()["detail"].lower() or "template" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_custom_component_json_patch_without_template_fails(client: AsyncClient, logged_in_headers):
    """Test that JSON Patch without template fails."""
    component_code = """
from langflow.custom import Component
from langflow.schema.message import Message

class TestComponent(Component):
    display_name = "Test"

    def build_output(self) -> Message:
        return Message(text="test")
"""

    patch_payload = {
        "operations": [
            {"op": "replace", "path": "/code", "value": component_code},
        ]
    }

    response = await client.post(
        "api/v1/custom_component/json-patch",
        json=patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 400
    assert "template" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_custom_component_json_patch_field_update(client: AsyncClient, logged_in_headers):
    """Test that field updates are properly tracked in response operations."""
    component_code = """
from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.template import Output
from langflow.schema.message import Message

class TestComponent(Component):
    display_name = "Test Component"

    inputs = [
        StrInput(name="test_field", display_name="Test Field", value="original"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Message:
        return Message(text=self.test_field)
"""

    # Build component
    build_response = await client.post(
        "api/v1/custom_component",
        json={"code": component_code},
        headers=logged_in_headers,
    )
    assert build_response.status_code == 200
    template = build_response.json()["data"]["template"]

    # Update field using JSON Patch
    patch_payload = {
        "operations": [
            {"op": "replace", "path": "/code", "value": component_code},
            {"op": "replace", "path": "/template", "value": template},
            {"op": "replace", "path": "/field/test_field", "value": "new_value"},
        ]
    }

    response = await client.post(
        "api/v1/custom_component/json-patch",
        json=patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    result = response.json()

    # Verify the field was updated
    assert result["success"] is True
    assert result["operations_applied"] == 3

    # Verify response operations include the field update
    response_ops = result["response_operations"]
    assert len(response_ops) > 0

    # Check if field update is in response operations
    field_op = next((op for op in response_ops if "test_field" in op.get("path", "")), None)
    assert field_op is not None
    assert field_op["value"] == "new_value"


@pytest.mark.asyncio
async def test_custom_component_json_patch_invalid_operations(client: AsyncClient, logged_in_headers):
    """Test that invalid JSON Patch operations are rejected."""
    # Missing required field 'path'
    patch_payload = {
        "operations": [
            {"op": "replace", "value": "something"},
        ]
    }

    response = await client.post(
        "api/v1/custom_component/json-patch",
        json=patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 422  # Validation error
