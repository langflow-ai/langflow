import json
from uuid import UUID

import orjson
import pytest
from httpx import AsyncClient
from langflow.components.logic import LoopComponent
from langflow.memory import aget_messages
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.database.models.flow import FlowCreate

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.build_utils import build_flow, get_build_events

TEXT = (
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet."
)


class TestLoopComponent(ComponentTestBaseWithoutClient):
    """Unit tests for the Loop component."""
    
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return LoopComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def default_kwargs_foreach(self):
        """Return default kwargs for For-Each mode."""
        return {
            "mode": "For-Each",
            "dataframe_input": DataFrame([Data(text="Hello World"), Data(text="Test Data")]),
            "data_input": None,
            "iterations": 1,
        }

    @pytest.fixture
    def default_kwargs_counted(self):
        """Return default kwargs for Counted mode."""
        return {
            "mode": "Counted",
            "dataframe_input": None,
            "data_input": Data(text="Hello World"),
            "iterations": 3,
        }

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component (For-Each mode for backward compatibility)."""
        return {
            "mode": "For-Each",
            "dataframe_input": DataFrame([Data(text="Hello World")]),
            "data_input": None,
            "iterations": 1,
        }

    async def test_component_structure(self, component_class, default_kwargs):
        """Test that the component has the correct structure."""
        component = await self.component_setup(component_class, default_kwargs)
        
        # Test component properties
        assert component.display_name == "Loop"
        assert "two modes" in component.description.lower()
        assert component.icon == "infinity"
        
        # Test inputs
        assert len(component.inputs) == 4
        input_names = [inp.name for inp in component.inputs]
        assert "mode" in input_names
        assert "dataframe_input" in input_names
        assert "data_input" in input_names
        assert "iterations" in input_names
        
        # Test outputs
        assert len(component.outputs) == 2
        output_names = [out.name for out in component.outputs]
        assert "item" in output_names
        assert "done" in output_names

    async def test_foreach_mode_with_dataframe(self, component_class, default_kwargs_foreach):
        """Test For-Each mode with DataFrame input."""
        component = await self.component_setup(component_class, default_kwargs_foreach)
        
        # Test data validation
        data_list = component._validate_data_foreach(component.dataframe_input)
        assert len(data_list) == 2
        assert all(isinstance(item, Data) for item in data_list)
        assert data_list[0].text == "Hello World"
        assert data_list[1].text == "Test Data"

    async def test_foreach_mode_with_data_list(self, component_class):
        """Test For-Each mode with Data list input."""
        data_list = [Data(text="Item 1"), Data(text="Item 2"), Data(text="Item 3")]
        kwargs = {
            "mode": "For-Each",
            "dataframe_input": data_list,
            "data_input": None,
            "iterations": 1,
        }
        component = await self.component_setup(component_class, kwargs)
        
        # Test data validation
        validated_data = component._validate_data_foreach(component.dataframe_input)
        assert len(validated_data) == 3
        assert all(isinstance(item, Data) for item in validated_data)

    async def test_counted_mode_with_data(self, component_class, default_kwargs_counted):
        """Test Counted mode with Data input."""
        component = await self.component_setup(component_class, default_kwargs_counted)
        
        # Test data validation
        data_list = component._validate_data_counted(component.data_input, component.iterations)
        assert len(data_list) == 3
        assert all(isinstance(item, Data) for item in data_list)
        assert all(item.text == "Hello World" for item in data_list)

    async def test_counted_mode_with_message(self, component_class):
        """Test Counted mode with Message input."""
        message_input = Message(text="Test Message")
        kwargs = {
            "mode": "Counted",
            "dataframe_input": None,
            "data_input": message_input,
            "iterations": 2,
        }
        component = await self.component_setup(component_class, kwargs)
        
        # Test data validation
        data_list = component._validate_data_counted(component.data_input, component.iterations)
        assert len(data_list) == 2
        assert all(isinstance(item, Data) for item in data_list)
        assert all(item.text == "Test Message" for item in data_list)

    async def test_counted_mode_iterations(self, component_class):
        """Test Counted mode with different iteration counts."""
        test_cases = [1, 5, 10]
        
        for iterations in test_cases:
            kwargs = {
                "mode": "Counted",
                "dataframe_input": None,
                "data_input": Data(text=f"Test {iterations}"),
                "iterations": iterations,
            }
            component = await self.component_setup(component_class, kwargs)
            
            data_list = component._validate_data_counted(component.data_input, component.iterations)
            assert len(data_list) == iterations
            assert all(item.text == f"Test {iterations}" for item in data_list)

    async def test_foreach_mode_validation_errors(self, component_class):
        """Test validation errors in For-Each mode."""
        component = await self.component_setup(component_class, {
            "mode": "For-Each",
            "dataframe_input": None,
            "data_input": None,
            "iterations": 1,
        })
        
        # Test with invalid input
        with pytest.raises(TypeError):
            component._validate_data_foreach("invalid_input")

    async def test_update_build_config_foreach(self, component_class, default_kwargs_foreach):
        """Test build config updates for For-Each mode."""
        component = await self.component_setup(component_class, default_kwargs_foreach)
        
        # Get the frontend node to test build config
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        
        # Test mode field exists
        assert "mode" in build_config
        
        # Test update_build_config for For-Each mode
        updated_config = component.update_build_config(build_config, "For-Each", "mode")
        
        # The method should return the updated config (basic test)
        assert updated_config is not None

    async def test_update_build_config_counted(self, component_class, default_kwargs_counted):
        """Test build config updates for Counted mode."""
        component = await self.component_setup(component_class, default_kwargs_counted)
        
        # Get the frontend node to test build config
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        
        # Test update_build_config for Counted mode
        updated_config = component.update_build_config(build_config, "Counted", "mode")
        
        # The method should return the updated config (basic test)
        assert updated_config is not None

    async def test_mode_switching(self, component_class, default_kwargs):
        """Test switching between modes."""
        component = await self.component_setup(component_class, default_kwargs)
        
        # Test default mode
        assert component.mode == "For-Each"
        
        # Test frontend node structure
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        
        # Verify all expected inputs are present
        expected_inputs = ["mode", "dataframe_input", "data_input", "iterations"]
        for input_name in expected_inputs:
            assert input_name in build_config


class TestLoopComponentWithAPI(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return LoopComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        # For-Each mode default kwargs (backward compatibility)
        return {
            "mode": "For-Each",
            "dataframe_input": DataFrame([Data(text="Hello World")]),
            "data_input": None,
            "iterations": 1,
        }

    def test_latest_version(self, component_class, default_kwargs) -> None:
        """Test that the component works with the latest version."""
        result = component_class(**default_kwargs)
        assert result is not None, "Component returned None for the latest version."

    async def _create_flow(self, client, json_loop_test, logged_in_headers):
        vector_store = orjson.loads(json_loop_test)
        data = vector_store["data"]
        vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
        response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
        response.raise_for_status()
        return response.json()["id"]

    async def check_messages(self, flow_id):
        messages = await aget_messages(flow_id=UUID(flow_id), order="ASC")
        assert len(messages) == 1
        assert messages[0].session_id == flow_id
        assert messages[0].sender == "Machine"
        assert messages[0].sender_name == "AI"
        assert len(messages[0].text) > 0
        return messages

    async def test_build_flow_loop(self, client, json_loop_test, logged_in_headers):
        """Test building a flow with a loop component."""
        # Create the flow
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)

        # Start the build and get job_id
        build_response = await build_flow(client, flow_id, logged_in_headers)
        job_id = build_response["job_id"]
        assert job_id is not None

        # Get the events stream
        events_response = await get_build_events(client, job_id, logged_in_headers)
        assert events_response.status_code == 200

        # Process the events stream
        chat_output = None
        lines = []
        async for line in events_response.aiter_lines():
            if not line:  # Skip empty lines
                continue
            lines.append(line)
            if "ChatOutput" in line:
                chat_output = json.loads(line)
            # Process events if needed
            # We could add specific assertions here for loop-related events
        assert chat_output is not None
        messages = await self.check_messages(flow_id)
        ai_message = messages[0].text
        json_data = orjson.loads(ai_message)

        # Use a for loop for better debugging
        found = []
        json_data = [(data["text"], q_dict) for data, q_dict in json_data]
        for text, q_dict in json_data:
            expected_text = f"==> {q_dict['q']}"
            assert expected_text in text, (
                f"Found {found} until now, but expected '{expected_text}' not found in '{text}',"
                f"and the json_data is {json_data}"
            )
            found.append(expected_text)

    async def test_run_flow_loop(self, client: AsyncClient, created_api_key, json_loop_test, logged_in_headers):
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)
        headers = {"x-api-key": created_api_key.api_key}
        payload = {
            "input_value": TEXT,
            "input_type": "chat",
            "session_id": f"{flow_id}run",
            "output_type": "chat",
            "tweaks": {},
        }
        response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
        data = response.json()
        assert "outputs" in data
        assert "session_id" in data
        assert len(data["outputs"][-1]["outputs"]) > 0
