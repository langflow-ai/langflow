from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

# from langflow.services.chat.manager import ChatService

import pytest


def test_init_build(client, active_user, logged_in_headers):
    response = client.post(
        "api/v1/build/init/test",
        json={"id": "test", "data": {"key": "value"}},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    assert response.json() == {"flowId": "test"}


# def test_stream_build(client):
#     client.post(
#         "api/v1/build/init", json={"id": "stream_test", "data": {"key": "value"}}
#     )

#     # Test the stream
#     response = client.get("api/v1/build/stream/stream_test")
#     assert response.status_code == 200
#     assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_websocket_endpoint(client: TestClient, active_user, logged_in_headers):
    # Assuming your websocket_endpoint uses chat_service which caches data from stream_build
    access_token = logged_in_headers["Authorization"].split(" ")[1]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"api/v1/chat/non_existing_client_id?token={access_token}"
        ) as websocket:
            websocket.send_json({"type": "test"})
            data = websocket.receive_json()
            assert "Please, build the flow before sending messages" in data["message"]


def test_websocket_endpoint_after_build(client, basic_graph_data):
    # Assuming your websocket_endpoint uses chat_service which caches data from stream_build
    client.post("api/v1/build/init", json=basic_graph_data)
    client.get("api/v1/build/stream/websocket_test")

    # There should be more to test here, but it depends on the inner workings of your websocket handler
    # and how your chat_service and other classes behave. The following is just an example structure.
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("api/v1/chat/websocket_test") as websocket:
            websocket.send_json({"input": "test"})
            websocket.receive_json()
