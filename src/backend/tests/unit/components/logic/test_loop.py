from uuid import UUID

import pytest
from httpx import AsyncClient
from langflow.components.logic.loop import LoopComponent
from langflow.memory import aget_messages
from langflow.schema.data import Data
from langflow.services.database.models.flow import FlowCreate
from orjson import orjson

from tests.base import ComponentTestBaseWithClient

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

    def test_latest_version(self, default_kwargs) -> None:
        """Test that the component works with the latest version."""
        result = LoopComponent(**default_kwargs)
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
        assert len(messages) == 2
        assert messages[0].session_id == flow_id
        assert messages[0].sender == "User"
        assert messages[0].sender_name == "User"
        assert messages[0].text != ""
        assert messages[1].session_id == flow_id
        assert messages[1].sender == "Machine"
        assert messages[1].sender_name == "AI"
        assert len(messages[1].text) > 0

    async def test_build_flow_loop(self, client, json_loop_test, logged_in_headers):
        # TODO: Add a test for the loop where the loop component gets updated even the component in json
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)

        async with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
            async for line in r.aiter_lines():
                # httpx split by \n, but ndjson sends two \n for each line
                if line:
                    # Process the line if needed
                    pass

        await self.check_messages(flow_id)

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
