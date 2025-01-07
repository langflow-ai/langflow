import json
from uuid import UUID

import pytest
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowCreate
from orjson import orjson


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
    assert messages[0].text == ""
    assert messages[1].session_id == flow_id
    assert messages[1].sender == "Machine"
    assert messages[1].sender_name == "AI"

@pytest.mark.benchmark
async def test_build_flow_loop(client, json_loop_test, logged_in_headers):
    flow_id = await _create_flow(client, json_loop_test, logged_in_headers)

    async with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        await consume_and_assert_stream(r)

    await check_messages(flow_id)



async def consume_and_assert_stream(r):
    count = 0
    async for line in r.aiter_lines():
        # httpx split by \n, but ndjson sends two \n for each line
        if not line:
            continue
        count += 1
