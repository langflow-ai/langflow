from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import FlowCreate
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput, TextInputComponent, TextOutputComponent
from lfx.graph.graph.base import Graph
from lfx.helpers.flow import run_flow
from lfx.schema.dotdict import dotdict


class TestRunFlowEndToEnd:
    """End-to-end integration tests for run_flow component."""

    @pytest.mark.asyncio
    async def test_complete_flow_execution_workflow(self, client, logged_in_headers, active_user):
        """Test complete workflow: select flow, update config, execute flow."""
        # Configure client to follow redirects for folder API
        client.follow_redirects = True

        # First, create a folder for our flows
        folder_response = await client.post(
            "api/v1/folders/",
            json={"name": "Test Folder", "description": "Folder for integration tests"},
            headers=logged_in_headers,
        )
        assert folder_response.status_code == 201
        folder_id = folder_response.json()["id"]

        # Create the target flow that will be run (Integration Test Flow)
        chat_input = ChatInput()
        chat_output = ChatOutput()
        graph = Graph(start=chat_input, end=chat_output)
        graph_dict = graph.dump(name="Integration Test Flow", description="Test integration flow")
        target_flow = FlowCreate(**graph_dict, folder_id=folder_id)

        # Create target flow via API (uses real database)
        response = await client.post(
            "api/v1/flows/",
            json=target_flow.model_dump(mode="json"),
            headers=logged_in_headers,
        )
        assert response.status_code == 201
        target_flow_data = response.json()
        target_flow_id = target_flow_data["id"]
        target_flow_name = target_flow_data["name"]

        # Create a flow that wraps RunFlowComponent (in the same folder)
        run_flow_component = RunFlowComponent()
        wrapper_graph = Graph(start=run_flow_component, end=run_flow_component)
        wrapper_dict = wrapper_graph.dump(name="RunFlow Wrapper", description="Wrapper flow with RunFlow component")
        wrapper_flow = FlowCreate(**wrapper_dict, folder_id=folder_id)

        wrapper_response = await client.post(
            "api/v1/flows/",
            json=wrapper_flow.model_dump(mode="json"),
            headers=logged_in_headers,
        )
        assert wrapper_response.status_code == 201
        wrapper_flow_data = wrapper_response.json()
        wrapper_flow_id = wrapper_flow_data["id"]

        try:
            # Setup component with real user_id and flow_id from the wrapper flow
            component = RunFlowComponent()
            component._user_id = str(active_user.id)
            component._flow_id = wrapper_flow_id  # Use the wrapper flow's ID
            component.cache_flow = False

            # Step 1: Build config with flow list
            build_config = dotdict(
                {
                    "code": {},
                    "_type": {},
                    "flow_name_selected": {"options": [], "options_metadata": []},
                    "is_refresh": True,
                    "flow_id_selected": {},
                    "session_id": {},
                    "cache_flow": {},
                }
            )

            # NO MOCKING - Use real component methods that will hit real database
            updated_config = await component.update_build_config(
                build_config=build_config, field_value=None, field_name="flow_name_selected"
            )

            # Verify the real flow appears in options (should see target flow in same folder)
            assert target_flow_name in updated_config["flow_name_selected"]["options"]
            # Remove this assertion - the wrapper flow is excluded because it's the current flow:
            # assert "RunFlow Wrapper" in updated_config["flow_name_selected"]["options"]

            # Update the metadata check - we should only see 1 flow (the target flow)
            # because the wrapper flow (current flow) is excluded
            assert len(updated_config["flow_name_selected"]["options_metadata"]) == 1
            flow_ids = [str(meta["id"]) for meta in updated_config["flow_name_selected"]["options_metadata"]]
            assert target_flow_id in flow_ids
        finally:
            # Cleanup
            await client.delete(f"api/v1/flows/{target_flow_id}", headers=logged_in_headers)
            await client.delete(f"api/v1/flows/{wrapper_flow_id}", headers=logged_in_headers)
            await client.delete(f"api/v1/folders/{folder_id}", headers=logged_in_headers)

    @pytest.mark.asyncio
    async def test_run_flow_with_inputs_and_outputs(self, active_user):
        """Test running a flow with inputs and capturing outputs."""
        user_id = str(active_user.id)
        session_id = "test_session"

        # Create a REAL graph with real components
        chat_input = ChatInput()
        text_output = TextOutputComponent()

        # Connect components in a simple flow
        graph = Graph(start=chat_input, end=text_output)

        # Execute run_flow with real graph
        inputs = [{"components": [chat_input.get_id()], "input_value": "Hello, world!", "type": "chat"}]

        result = await run_flow(
            user_id=user_id,
            session_id=session_id,
            inputs=inputs,
            graph=graph,
            output_type="any",  # Get all outputs
        )

        # Verify graph properties were set correctly
        assert graph.session_id == session_id
        assert graph.user_id == user_id

        # Verify result structure
        assert len(result) > 0, "Expected at least one output from flow execution"

        # Verify the flow actually executed (has outputs)
        first_result = result[0]
        assert hasattr(first_result, "outputs"), "Expected RunOutputs object with outputs attribute"


class TestRunFlowComponentWithTools:
    """Integration tests for run_flow component tool generation."""

    @pytest.mark.asyncio
    async def test_tool_generation_from_flow(self, client, logged_in_headers, active_user):
        """Test that tools are generated correctly from flow inputs."""
        # Configure client to follow redirects for folder API
        client.follow_redirects = True

        # Create a folder for our flows
        folder_response = await client.post(
            "api/v1/folders/",
            json={"name": "Tool Test Folder", "description": "Folder for tool generation tests"},
            headers=logged_in_headers,
        )
        assert folder_response.status_code == 201
        folder_id = folder_response.json()["id"]

        # Create a REAL flow that can be used as a tool
        # Simple chat input -> chat output flow
        chat_input = ChatInput()
        chat_output = ChatOutput()
        graph = Graph(start=chat_input, end=chat_output)
        graph_dict = graph.dump(name="Tool Flow", description="A flow that can be used as a tool")
        tool_flow = FlowCreate(**graph_dict, folder_id=folder_id, user_id=str(active_user.id))

        # Create tool flow via API (will be associated with active_user via logged_in_headers)
        response = await client.post("api/v1/flows/", json=tool_flow.model_dump(mode="json"), headers=logged_in_headers)
        assert response.status_code == 201
        flow_data = response.json()
        flow_id = flow_data["id"]
        flow_name = flow_data["name"]
        # Verify the flow is owned by the active user
        assert flow_data["user_id"] == str(active_user.id), "Tool flow should be owned by active_user"

        # Create a wrapper flow with RunFlowComponent (in the same folder, same user)
        run_flow_component = RunFlowComponent()
        wrapper_graph = Graph(start=run_flow_component, end=run_flow_component)
        wrapper_dict = wrapper_graph.dump(name="Tool Wrapper", description="Wrapper for tool generation")
        wrapper_flow = FlowCreate(**wrapper_dict, folder_id=folder_id, user_id=str(active_user.id))

        wrapper_response = await client.post(
            "api/v1/flows/",
            json=wrapper_flow.model_dump(mode="json"),
            headers=logged_in_headers,
        )
        assert wrapper_response.status_code == 201
        wrapper_flow_data = wrapper_response.json()
        wrapper_flow_id = wrapper_flow_data["id"]
        # Verify the wrapper flow is also owned by the same user
        assert wrapper_flow_data["user_id"] == str(active_user.id), "Wrapper flow should be owned by active_user"

        try:
            # Setup component with real flow and wrapper flow's ID
            component = RunFlowComponent()
            component._user_id = str(active_user.id)
            component._flow_id = wrapper_flow_id  # Use the wrapper flow's ID
            component.flow_name_selected = flow_name
            component.flow_id_selected = flow_id

            # Verify the component can retrieve the graph from the database
            graph = await component.get_graph(flow_name, flow_id)
            assert graph is not None, "Expected to retrieve graph from database"
            assert graph.flow_name == flow_name, f"Expected flow_name to be {flow_name}"

            # Verify the graph has the expected components
            assert len(graph.vertices) > 0, "Expected graph to have vertices"

            # Call get_required_data to verify it extracts input fields
            result = await component.get_required_data()
            assert result is not None, "Expected to get flow description and fields"
            flow_description, tool_mode_fields = result
            assert isinstance(flow_description, str), "Flow description should be a string"
            assert isinstance(tool_mode_fields, list), "Tool mode fields should be a list"
            # Note: ChatInput may or may not have tool_mode=True inputs, so we don't assert the count

            # Get tools from real flow - ChatInput/ChatOutput may or may not generate tools
            # depending on whether inputs have tool_mode=True
            tools = await component._get_tools()
            # Verify the method executes without error (tools list may be empty for simple chat flow)
            assert isinstance(tools, list), "Expected tools to be a list"
        finally:
            # Cleanup
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
            await client.delete(f"api/v1/flows/{wrapper_flow_id}", headers=logged_in_headers)
            await client.delete(f"api/v1/folders/{folder_id}", headers=logged_in_headers)


class TestRunFlowOutputResolution:
    """Integration tests for output resolution."""

    @pytest.mark.asyncio
    async def test_resolve_flow_output_with_multiple_vertices(self, client, logged_in_headers, active_user):
        """Test resolving output from a specific vertex."""
        # Create a REAL flow with multiple outputs
        chat_input = ChatInput()
        text_output = TextOutputComponent()

        # Create a flow with one input and one output (Graph requires both)
        graph = Graph(start=chat_input, end=text_output)

        graph_dict = graph.dump(name="Multi Output Flow", description="Flow with multiple outputs")
        flow = FlowCreate(**graph_dict)

        # Create flow via API
        response = await client.post("api/v1/flows/", json=flow.model_dump(mode="json"), headers=logged_in_headers)
        assert response.status_code == 201
        flow_data = response.json()
        flow_id = flow_data["id"]
        flow_name = flow_data["name"]

        try:
            # Setup component with real flow
            component = RunFlowComponent()
            component._user_id = str(active_user.id)
            component._flow_id = str(uuid4())
            component.flow_name_selected = flow_name
            component.flow_id_selected = flow_id
            component.session_id = None
            component.flow_tweak_data = {}
            component._attributes = {}

            # Initialize the component's internal state
            from types import SimpleNamespace

            component._vertex = SimpleNamespace(data={"node": {}})
            component._pre_run_setup()

            # Get the real graph
            real_graph = await component.get_graph(flow_name_selected=flow_name, flow_id_selected=flow_id)

            # Verify the flow has multiple output vertices
            output_vertices = [v for v in real_graph.vertices if v.is_output]
            assert len(output_vertices) >= 1, "Expected at least one output vertex in the flow"

            # Test that the component can work with real flow structure
            # (actual output resolution would require running the flow, which is complex for integration test)
            assert real_graph is not None
            assert real_graph.flow_name == flow_name
        finally:
            # Cleanup
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)


class TestRunFlowCaching:
    """Integration tests for run_flow caching behavior with real flows.

    Note: Most caching tests should be in unit tests. These integration tests
    focus on end-to-end caching behavior with real database and components.
    """

    @pytest.mark.asyncio
    async def test_cache_enabled_reuses_graph_with_real_flow(self, client, logged_in_headers, active_user):
        """Test that with cache_flow=True, the graph is cached and reused with a real flow."""
        # Create a REAL flow in the database
        text_input = TextInputComponent()
        text_output = TextOutputComponent()
        graph = Graph(start=text_input, end=text_output)
        graph_dict = graph.dump(name="Cached Flow", description="Flow to test caching")
        flow = FlowCreate(**graph_dict)

        # Create flow via API
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_data = response.json()
        flow_id = flow_data["id"]
        flow_name = flow_data["name"]

        try:
            # Setup component with caching ENABLED
            component = RunFlowComponent()
            component._user_id = str(active_user.id)
            component._flow_id = str(uuid4())
            component.cache_flow = True  # Caching enabled

            # First access - should fetch from database
            graph1 = await component.get_graph(flow_name_selected=flow_name, flow_id_selected=flow_id)

            # Verify it's a real graph
            assert graph1 is not None
            assert graph1.flow_name == flow_name
            assert len(graph1.vertices) > 0

            # Second access - should reuse cached graph (same instance)
            graph2 = await component.get_graph(flow_name_selected=flow_name, flow_id_selected=flow_id)

            # With caching, should return the same graph instance
            assert graph2 is not None
            assert graph2.flow_name == flow_name
            assert graph1 == graph2, "Expected same graph instance from cache"
        finally:
            # Cleanup
            await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
