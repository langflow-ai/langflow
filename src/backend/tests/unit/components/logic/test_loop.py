import json
from uuid import UUID

import orjson
import pytest
from httpx import AsyncClient
from langflow.components.logic import LoopComponent
from langflow.memory import aget_messages
from langflow.schema.data import Data
from langflow.services.database.models.flow import FlowCreate

from tests.base import ComponentTestBaseWithClient
from tests.unit.build_utils import build_flow, get_build_events

TEXT = (
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet."
)


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
        return {
            "data": [[Data(text="Hello World")]],
            "loop_input": [Data(text=TEXT)],
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
