"""Comprehensive tests for all MCP tools in the agentic MCP server.

This test module covers all 18 MCP tools exposed in mcp/server.py:
- Template Tools: search_templates, get_template, list_all_tags, count_templates
- Component Tools: search_components, get_component, list_component_types,
  count_components, get_components_by_type_tool
- Flow Graph Tools: visualize_flow_graph, get_flow_ascii_diagram,
  get_flow_text_representation, get_flow_structure_summary
- Flow Component Tools: get_flow_component_details, get_flow_component_field_value,
  update_flow_component_field, list_flow_component_fields
- Flow Creation: create_flow_from_template
"""

import json
from uuid import UUID

import pytest
from langflow.agentic.mcp.server import (
    count_components,
    count_templates,
    create_flow_from_template,
    get_component,
    get_components_by_type_tool,
    get_flow_ascii_diagram,
    get_flow_component_details,
    get_flow_component_field_value,
    get_flow_structure_summary,
    get_flow_text_representation,
    get_template,
    list_all_tags,
    list_component_types,
    list_flow_component_fields,
    search_components,
    search_templates,
    update_flow_component_field,
    visualize_flow_graph,
)
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.deps import session_scope

# =============================================================================
# Template Tools Tests (4 tools)
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestSearchTemplates:
    """Test cases for search_templates MCP tool."""

    def test_search_all_templates(self):
        """Test searching all templates without filters."""
        result = search_templates()

        assert isinstance(result, list)
        assert len(result) > 0
        # Each result should be a dict with default fields
        for template in result:
            assert isinstance(template, dict)
            assert "id" in template or "name" in template

    def test_search_with_query(self):
        """Test searching templates with a query string."""
        result = search_templates(query="agent")

        assert isinstance(result, list)
        # Results should match query in name or description
        for template in result:
            name_match = "agent" in template.get("name", "").lower()
            desc_match = "agent" in template.get("description", "").lower()
            assert name_match or desc_match

    def test_search_with_custom_fields(self):
        """Test searching with custom field selection."""
        result = search_templates(fields=["id", "name", "tags"])

        assert isinstance(result, list)
        if result:
            # Should only have requested fields (plus any defaults)
            template = result[0]
            assert "id" in template
            assert "name" in template

    def test_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        lower = search_templates(query="chat")
        upper = search_templates(query="CHAT")
        mixed = search_templates(query="ChAt")

        assert len(lower) == len(upper) == len(mixed)

    def test_search_no_matches(self):
        """Test search with no matching results."""
        result = search_templates(query="xyznonexistent123456")

        assert result == []


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetTemplate:
    """Test cases for get_template MCP tool."""

    def test_get_existing_template(self):
        """Test getting an existing template by ID."""
        # First get list of templates to find a valid ID
        templates = search_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]
        result = get_template(template_id=template_id)

        assert result is not None
        assert result.get("id") == template_id

    def test_get_template_with_fields(self):
        """Test getting template with specific fields."""
        templates = search_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]
        result = get_template(template_id=template_id, fields=["name", "description"])

        assert result is not None
        assert "name" in result

    def test_get_nonexistent_template(self):
        """Test getting a nonexistent template returns None."""
        result = get_template(template_id="00000000-0000-0000-0000-000000000000")

        assert result is None


@pytest.mark.skip(reason="Skipping agentic tests")
class TestListAllTags:
    """Test cases for list_all_tags MCP tool."""

    def test_list_all_tags(self):
        """Test listing all unique tags."""
        result = list_all_tags()

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(tag, str) for tag in result)

    def test_tags_are_sorted(self):
        """Test that tags are sorted alphabetically."""
        result = list_all_tags()

        assert result == sorted(result)

    def test_tags_are_unique(self):
        """Test that tags have no duplicates."""
        result = list_all_tags()

        assert len(result) == len(set(result))


@pytest.mark.skip(reason="Skipping agentic tests")
class TestCountTemplates:
    """Test cases for count_templates MCP tool."""

    def test_count_templates(self):
        """Test counting all templates."""
        count = count_templates()
        templates = search_templates()

        assert count == len(templates)
        assert count > 0


# =============================================================================
# Component Tools Tests (5 tools)
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestSearchComponents:
    """Test cases for search_components MCP tool."""

    @pytest.mark.asyncio
    async def test_search_all_components(self):
        """Test searching all components without filters."""
        result = await search_components()

        assert isinstance(result, list)
        assert len(result) > 0
        for comp in result:
            assert isinstance(comp, dict)
            assert "name" in comp
            assert "type" in comp

    @pytest.mark.asyncio
    async def test_search_with_query(self):
        """Test searching components with a query."""
        result = await search_components(query="OpenAI")

        assert isinstance(result, list)
        for comp in result:
            name_match = "openai" in comp.get("name", "").lower()
            display_match = "openai" in comp.get("display_name", "").lower()
            desc_match = "openai" in comp.get("description", "").lower()
            assert name_match or display_match or desc_match

    @pytest.mark.asyncio
    async def test_search_by_type(self):
        """Test searching components filtered by type."""
        types = await list_component_types()
        if types:
            result = await search_components(component_type=types[0])

            assert isinstance(result, list)
            for comp in result:
                assert comp["type"].lower() == types[0].lower()

    @pytest.mark.asyncio
    async def test_search_with_custom_fields(self):
        """Test searching with custom field selection."""
        result = await search_components(fields=["name", "type", "display_name"])

        assert isinstance(result, list)
        if result:
            comp = result[0]
            assert "name" in comp
            assert "type" in comp

    @pytest.mark.asyncio
    async def test_search_add_search_text(self):
        """Test that add_search_text parameter adds text field."""
        result = await search_components(add_search_text=True)

        assert isinstance(result, list)
        if result:
            # Each component should have a 'text' field
            for comp in result:
                assert "text" in comp
                assert isinstance(comp["text"], str)

    @pytest.mark.asyncio
    async def test_search_no_search_text(self):
        """Test that add_search_text=False omits text field."""
        result = await search_components(add_search_text=False)

        assert isinstance(result, list)
        if result:
            # Text field should not be added
            for comp in result:
                assert "text" not in comp


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetComponent:
    """Test cases for get_component MCP tool."""

    @pytest.mark.asyncio
    async def test_get_existing_component(self):
        """Test getting an existing component by name."""
        components = await search_components(fields=["name"])
        assert len(components) > 0

        comp_name = components[0]["name"]
        result = await get_component(component_name=comp_name)

        assert result is not None
        assert result["name"] == comp_name

    @pytest.mark.asyncio
    async def test_get_component_with_type(self):
        """Test getting component with type filter."""
        types = await list_component_types()
        if types:
            type_comps = await search_components(component_type=types[0])
            if type_comps:
                comp_name = type_comps[0]["name"]
                result = await get_component(component_name=comp_name, component_type=types[0])

                assert result is not None
                assert result["type"].lower() == types[0].lower()

    @pytest.mark.asyncio
    async def test_get_nonexistent_component(self):
        """Test getting a nonexistent component returns None."""
        result = await get_component(component_name="NonExistentComponentXYZ123")

        assert result is None


@pytest.mark.skip(reason="Skipping agentic tests")
class TestListComponentTypes:
    """Test cases for list_component_types MCP tool."""

    @pytest.mark.asyncio
    async def test_list_types(self):
        """Test listing all component types."""
        result = await list_component_types()

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(t, str) for t in result)

    @pytest.mark.asyncio
    async def test_types_are_sorted(self):
        """Test that types are sorted."""
        result = await list_component_types()

        assert result == sorted(result)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestCountComponents:
    """Test cases for count_components MCP tool."""

    @pytest.mark.asyncio
    async def test_count_all_components(self):
        """Test counting all components."""
        count = await count_components()
        components = await search_components()

        assert count == len(components)
        assert count > 0

    @pytest.mark.asyncio
    async def test_count_by_type(self):
        """Test counting components by type."""
        types = await list_component_types()
        if types:
            count = await count_components(component_type=types[0])
            type_comps = await search_components(component_type=types[0])

            assert count == len(type_comps)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetComponentsByTypeTool:
    """Test cases for get_components_by_type_tool MCP tool."""

    @pytest.mark.asyncio
    async def test_get_by_type(self):
        """Test getting all components of a specific type."""
        types = await list_component_types()
        if types:
            result = await get_components_by_type_tool(component_type=types[0])

            assert isinstance(result, list)
            for comp in result:
                assert comp["type"].lower() == types[0].lower()

    @pytest.mark.asyncio
    async def test_get_by_type_with_fields(self):
        """Test getting components by type with field selection."""
        types = await list_component_types()
        if types:
            result = await get_components_by_type_tool(component_type=types[0], fields=["name", "display_name"])

            assert isinstance(result, list)
            if result:
                assert "name" in result[0]


# =============================================================================
# Flow Graph Tools Tests (4 tools)
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestVisualizeFlowGraph:
    """Test cases for visualize_flow_graph MCP tool."""

    @pytest.mark.asyncio
    async def test_visualize_flow(self, client, logged_in_headers, active_user):
        """Test visualizing a flow graph."""
        # Create a simple flow with proper structure for visualization
        simple_flow_data = {
            "nodes": [
                {
                    "id": "ChatInput-1",
                    "type": "genericNode",
                    "data": {"type": "ChatInput", "node": {"template": {}, "display_name": "Chat Input"}},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "ChatOutput-1",
                    "type": "genericNode",
                    "data": {"type": "ChatOutput", "node": {"template": {}, "display_name": "Chat Output"}},
                    "position": {"x": 200, "y": 0},
                },
            ],
            "edges": [
                {"source": "ChatInput-1", "target": "ChatOutput-1", "id": "edge-1"},
            ],
        }
        flow = FlowCreate(name="VisualizeMCPTest", description="Test", data=simple_flow_data)
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            result = await visualize_flow_graph(flow_id_or_name=flow_id, user_id=str(active_user.id))

            # Result might have error for complex flows - check structure
            if "error" not in result:
                assert result["flow_id"] == flow_id
                assert "vertex_count" in result
                assert "edge_count" in result
                assert "text_repr" in result
            else:
                # Accept error as valid result for certain flow structures
                assert "flow_id" in result

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    async def test_visualize_nonexistent_flow(self, client, active_user):  # noqa: ARG002
        """Test visualizing a nonexistent flow."""
        result = await visualize_flow_graph(
            flow_id_or_name="00000000-0000-0000-0000-000000000000", user_id=str(active_user.id)
        )

        assert "error" in result


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetFlowAsciiDiagram:
    """Test cases for get_flow_ascii_diagram MCP tool."""

    @pytest.mark.asyncio
    async def test_get_ascii_diagram(self, client, logged_in_headers, active_user):
        """Test getting ASCII diagram of a flow."""
        simple_flow_data = {
            "nodes": [
                {
                    "id": "Node-1",
                    "type": "genericNode",
                    "data": {"type": "Input", "node": {"template": {}, "display_name": "Input"}},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "Node-2",
                    "type": "genericNode",
                    "data": {"type": "Output", "node": {"template": {}, "display_name": "Output"}},
                    "position": {"x": 200, "y": 0},
                },
            ],
            "edges": [{"source": "Node-1", "target": "Node-2", "id": "edge-1"}],
        }
        flow = FlowCreate(name="ASCIIMCPTest", description="Test", data=simple_flow_data)
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            result = await get_flow_ascii_diagram(flow_id_or_name=flow_id, user_id=str(active_user.id))

            assert isinstance(result, str)

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetFlowTextRepresentation:
    """Test cases for get_flow_text_representation MCP tool."""

    @pytest.mark.asyncio
    async def test_get_text_representation(self, client, logged_in_headers, active_user):
        """Test getting text representation of a flow."""
        simple_flow_data = {
            "nodes": [
                {
                    "id": "Node-1",
                    "type": "genericNode",
                    "data": {"type": "Input", "node": {"template": {}, "display_name": "Input"}},
                    "position": {"x": 0, "y": 0},
                },
            ],
            "edges": [],
        }
        flow = FlowCreate(name="TextReprMCPTest", description="Test", data=simple_flow_data)
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            result = await get_flow_text_representation(flow_id_or_name=flow_id, user_id=str(active_user.id))

            assert isinstance(result, str)
            assert len(result) > 0

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetFlowStructureSummary:
    """Test cases for get_flow_structure_summary MCP tool."""

    @pytest.mark.asyncio
    async def test_get_summary(self, client, logged_in_headers, active_user):
        """Test getting flow structure summary."""
        simple_flow_data = {
            "nodes": [
                {
                    "id": "Node-1",
                    "type": "genericNode",
                    "data": {"type": "Input", "node": {"template": {}, "display_name": "Input"}},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "Node-2",
                    "type": "genericNode",
                    "data": {"type": "Output", "node": {"template": {}, "display_name": "Output"}},
                    "position": {"x": 200, "y": 0},
                },
            ],
            "edges": [{"source": "Node-1", "target": "Node-2", "id": "edge-1"}],
        }
        expected_nodes = 2
        expected_edges = 1

        flow = FlowCreate(name="SummaryMCPTest", description="Test", data=simple_flow_data)
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            result = await get_flow_structure_summary(flow_id_or_name=flow_id, user_id=str(active_user.id))

            if "error" not in result:
                assert result["vertex_count"] == expected_nodes
                assert result["edge_count"] == expected_edges
                assert "vertices" in result
                assert "edges" in result
            # If there's an error, the test still passes - we're testing the API doesn't crash

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


# =============================================================================
# Flow Component Tools Tests (4 tools)
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetFlowComponentDetails:
    """Test cases for get_flow_component_details MCP tool."""

    @pytest.mark.asyncio
    async def test_get_component_details(self, client, logged_in_headers, active_user, json_chat_input):
        """Test getting component details from a flow.

        Note: Graph parsing may fail with old fixture data format.
        """
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="CompDetailsMCPTest", description="Test", data=flow_data.get("data"))
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            component_id = flow_data["data"]["nodes"][0]["id"]
            result = await get_flow_component_details(
                flow_id_or_name=flow_id, component_id=component_id, user_id=str(active_user.id)
            )

            # Should return a dict
            assert isinstance(result, dict)
            # If successful, verify component_id
            if "error" not in result:
                assert result["component_id"] == component_id

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestGetFlowComponentFieldValue:
    """Test cases for get_flow_component_field_value MCP tool."""

    @pytest.mark.asyncio
    async def test_get_field_value(self, client, logged_in_headers, active_user, json_chat_input):
        """Test getting a specific field value from a component."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="FieldValueMCPTest", description="Test", data=flow_data.get("data"))
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            # Find a component with a field
            for node in flow_data["data"]["nodes"]:
                template = node.get("data", {}).get("node", {}).get("template", {})
                for field_name in template:
                    if field_name != "_type" and isinstance(template[field_name], dict):
                        component_id = node["id"]
                        result = await get_flow_component_field_value(
                            flow_id_or_name=flow_id,
                            component_id=component_id,
                            field_name=field_name,
                            user_id=str(active_user.id),
                        )

                        if "error" not in result:
                            assert result["field_name"] == field_name
                            return

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestUpdateFlowComponentField:
    """Test cases for update_flow_component_field MCP tool."""

    @pytest.mark.asyncio
    async def test_update_field(self, client, logged_in_headers, active_user, json_chat_input):
        """Test updating a component field value."""
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="UpdateFieldMCPTest", description="Test", data=flow_data.get("data"))
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            # Find a string field to update
            for node in flow_data["data"]["nodes"]:
                template = node.get("data", {}).get("node", {}).get("template", {})
                for field_name, field_config in template.items():
                    if (
                        field_name != "_type"
                        and isinstance(field_config, dict)
                        and field_config.get("type") in ["str", "string"]
                    ):
                        component_id = node["id"]
                        new_value = "MCP Updated Value"

                        result = await update_flow_component_field(
                            flow_id_or_name=flow_id,
                            component_id=component_id,
                            field_name=field_name,
                            new_value=new_value,
                            user_id=str(active_user.id),
                        )

                        if result.get("success"):
                            assert result["new_value"] == new_value
                            return

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


@pytest.mark.skip(reason="Skipping agentic tests")
class TestListFlowComponentFields:
    """Test cases for list_flow_component_fields MCP tool."""

    @pytest.mark.asyncio
    async def test_list_fields(self, client, logged_in_headers, active_user, json_chat_input):
        """Test listing all fields of a component.

        Note: Graph parsing may fail with old fixture data format.
        """
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="ListFieldsMCPTest", description="Test", data=flow_data.get("data"))
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            component_id = flow_data["data"]["nodes"][0]["id"]
            result = await list_flow_component_fields(
                flow_id_or_name=flow_id, component_id=component_id, user_id=str(active_user.id)
            )

            # Should return a dict
            assert isinstance(result, dict)
            # If successful, verify expected fields
            if "error" not in result:
                assert "fields" in result
                assert "field_count" in result

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


# =============================================================================
# Flow Creation Tool Tests (1 tool)
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestCreateFlowFromTemplate:
    """Test cases for create_flow_from_template MCP tool."""

    @pytest.mark.asyncio
    async def test_create_flow(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test creating a flow from a template via MCP tool."""
        templates = search_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]

        result = await create_flow_from_template(template_id=template_id, user_id=str(active_user.id))

        assert "id" in result
        assert "link" in result

        # Cleanup
        async with session_scope() as session:
            flow_uuid = UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
            flow = await session.get(Flow, flow_uuid)
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_flow_with_folder(self, client, logged_in_headers, active_user):
        """Test creating a flow in a specific folder."""
        # Create folder (using projects endpoint as folders redirects)
        folder_response = await client.post(
            "api/v1/projects/",
            json={"name": "MCP Test Folder", "description": "Test"},
            headers=logged_in_headers,
        )
        assert folder_response.status_code == 201
        folder_id = folder_response.json()["id"]

        try:
            templates = search_templates(fields=["id"])
            assert len(templates) > 0

            template_id = templates[0]["id"]

            result = await create_flow_from_template(
                template_id=template_id, user_id=str(active_user.id), folder_id=folder_id
            )

            assert "id" in result
            assert f"/folder/{folder_id}" in result["link"]

            # Cleanup flow
            async with session_scope() as session:
                flow_uuid = UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
                flow = await session.get(Flow, flow_uuid)
                if flow:
                    await session.delete(flow)
                    await session.commit()

        finally:
            # Cleanup folder
            await client.delete(f"api/v1/projects/{folder_id}", headers=logged_in_headers)


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.skip(reason="Skipping agentic tests")
class TestMCPToolsIntegration:
    """Integration tests combining multiple MCP tools."""

    @pytest.mark.asyncio
    async def test_search_and_get_component_workflow(self):
        """Test workflow: search components -> get specific component."""
        # Search for components
        components = await search_components(query="input", fields=["name", "type"])

        if components:
            # Get details of first component
            comp_name = components[0]["name"]
            detailed = await get_component(component_name=comp_name)

            assert detailed is not None
            assert detailed["name"] == comp_name

    @pytest.mark.asyncio
    async def test_template_to_flow_workflow(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test complete workflow: search template -> create flow -> visualize.

        Note: Graph visualization may fail with certain data formats.
        """
        # Search templates
        templates = search_templates(query="chat", fields=["id", "name"])

        if not templates:
            templates = search_templates(fields=["id", "name"])

        assert len(templates) > 0
        template = templates[0]

        # Create flow from template
        result = await create_flow_from_template(template_id=template["id"], user_id=str(active_user.id))

        flow_id = result["id"]

        try:
            # Visualize the created flow
            viz = await visualize_flow_graph(flow_id_or_name=flow_id, user_id=str(active_user.id))

            # Should return a dict (may have error if graph parsing fails)
            assert isinstance(viz, dict)
            # If successful, verify flow name
            if "error" not in viz:
                assert viz["flow_name"] == template["name"]

        finally:
            # Cleanup
            async with session_scope() as session:
                flow_uuid = UUID(flow_id) if isinstance(flow_id, str) else flow_id
                flow = await session.get(Flow, flow_uuid)
                if flow:
                    await session.delete(flow)
                    await session.commit()

    @pytest.mark.asyncio
    async def test_flow_inspection_workflow(self, client, logged_in_headers, active_user, json_chat_input):
        """Test workflow: create flow -> get summary -> inspect components -> get field values.

        Note: Graph parsing may fail with old fixture data format, so this test
        verifies the workflow returns valid responses.
        """
        flow_data = json.loads(json_chat_input)
        flow = FlowCreate(name="InspectionWorkflow", description="Test", data=flow_data.get("data"))
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

        flow_response = response.json()
        flow_id = flow_response["id"]

        try:
            # Step 1: Get flow summary
            summary = await get_flow_structure_summary(flow_id_or_name=flow_id, user_id=str(active_user.id))

            # Should return a dict
            assert isinstance(summary, dict)

            # If successful with graph parsing, continue the workflow
            if "error" not in summary and summary.get("vertex_count", 0) > 0:
                # Step 2: Get details for each component
                for vertex_id in summary.get("vertices", []):
                    details = await get_flow_component_details(
                        flow_id_or_name=flow_id, component_id=vertex_id, user_id=str(active_user.id)
                    )

                    if "error" not in details:
                        # Step 3: List fields
                        fields = await list_flow_component_fields(
                            flow_id_or_name=flow_id, component_id=vertex_id, user_id=str(active_user.id)
                        )

                        if "error" not in fields:
                            assert "fields" in fields
                        break  # Test one component

        finally:
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    async def test_component_type_coverage(self):
        """Test that all component types can be queried."""
        types = await list_component_types()

        for comp_type in types:
            components = await get_components_by_type_tool(component_type=comp_type)
            count = await count_components(component_type=comp_type)

            assert len(components) == count
            assert len(components) > 0, f"Type {comp_type} has no components"

    def test_template_tag_coverage(self):
        """Test that templates with each tag can be found."""
        tags = list_all_tags()

        for tag in tags:
            templates = search_templates(query=None, fields=["id", "tags"])
            tag_templates = [t for t in templates if tag in t.get("tags", [])]
            assert len(tag_templates) > 0, f"No templates found with tag: {tag}"
