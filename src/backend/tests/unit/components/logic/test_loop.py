from uuid import UUID

import pytest
from httpx import AsyncClient
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowCreate
from orjson import orjson

# 3 lines of dummy sentences
TEXT = (
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet."
)


async def _create_flow(client, json_loop_test, logged_in_headers):
    vector_store = orjson.loads(json_loop_test)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
    response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    response.raise_for_status()
    return response.json()["id"]


async def check_messages(flow_id):
    messages = await aget_messages(flow_id=UUID(flow_id), order="ASC")
    assert len(messages) == 2
    assert messages[0].session_id == flow_id
    assert messages[0].sender == "User"
    assert messages[0].sender_name == "User"
    assert messages[0].text != ""
    assert messages[1].session_id == flow_id
    assert messages[1].sender == "Machine"
    assert messages[1].sender_name == "AI"
    assert messages[1].text != ""
    assert len(messages[1].text) > 0


@pytest.mark.benchmark
async def test_build_flow_loop(client, json_loop_test, logged_in_headers):
    flow_id = await _create_flow(client, json_loop_test, logged_in_headers)

    async with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        async for line in r.aiter_lines():
            # httpx split by \n, but ndjson sends two \n for each line
            if line:
                # Process the line if needed
                pass

    await check_messages(flow_id)


async def test_run_flow_loop(client: AsyncClient, created_api_key, json_loop_test, logged_in_headers):
    flow_id = await _create_flow(client, json_loop_test, logged_in_headers)
    headers = {"x-api-key": created_api_key.api_key}
    payload = {"input_value": TEXT, "input_type": "chat", "output_type": "chat", "tweaks": {}}
    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
    data = response.json()
    assert "outputs" in data
    assert "session_id" in data
    assert len(data["outputs"]) > 0
