import json
from uuid import UUID
from orjson import orjson

from langflow.memory import get_messages
from langflow.services.database.models.flow import FlowCreate, FlowUpdate


def test_build_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        consume_and_assert_stream(r)

    check_messages(flow_id)


def test_build_flow_from_request_data(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    flow_data = client.get("api/v1/flows/" + str(flow_id), headers=logged_in_headers).json()

    with client.stream(
        "POST", f"api/v1/build/{flow_id}/flow", json={"data": flow_data["data"]}, headers=logged_in_headers
    ) as r:
        consume_and_assert_stream(r)

    check_messages(flow_id)


def test_build_flow_with_frozen_path(client, json_memory_chatbot_no_llm, logged_in_headers):
    flow_id = _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    flow_data = client.get("api/v1/flows/" + str(flow_id), headers=logged_in_headers).json()
    flow_data["data"]["nodes"][0]["data"]["node"]["frozen"] = True
    response = client.patch(
        "api/v1/flows/" + str(flow_id),
        json=FlowUpdate(name="Flow", description="description", data=flow_data["data"]).model_dump(),
        headers=logged_in_headers,
    )
    response.raise_for_status()

    with client.stream("POST", f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers) as r:
        consume_and_assert_stream(r)

    check_messages(flow_id)


def check_messages(flow_id):
    messages = get_messages(flow_id=UUID(flow_id), order="ASC")
    assert len(messages) == 2
    assert messages[0].session_id == flow_id
    assert messages[0].sender == "User"
    assert messages[0].sender_name == "User"
    assert messages[0].text == ""
    assert messages[1].session_id == flow_id
    assert messages[1].sender == "Machine"
    assert messages[1].sender_name == "AI"


def consume_and_assert_stream(r):
    count = 0
    for line in r.iter_lines():
        # httpx split by \n, but ndjson sends two \n for each line
        if not line:
            continue
        parsed = json.loads(line)
        if count == 0:
            assert parsed["event"] == "vertices_sorted"
            ids = parsed["data"]["ids"]
            ids.sort()
            assert ids == ["ChatInput-CIGht", "Memory-amN4Z"]

            to_run = parsed["data"]["to_run"]
            to_run.sort()
            assert to_run == ["ChatInput-CIGht", "ChatOutput-QA7ej", "Memory-amN4Z", "Prompt-iWbCC"]
        elif count > 0 and count < 5:
            assert parsed["event"] == "end_vertex"
            assert parsed["data"]["build_data"] is not None
        elif count == 5:
            assert parsed["event"] == "end"
        else:
            raise ValueError(f"Unexpected line: {line}")
        count += 1


def _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    vector_store = orjson.loads(json_memory_chatbot_no_llm)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
    response = client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    response.raise_for_status()
    flow_id = response.json()["id"]
    return flow_id
