import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_websocket_connection(client: TestClient):
    with client.websocket_connect("api/v1/chat/test_client") as websocket:
        assert websocket.scope["client"] == ["testclient", 50000]
        assert websocket.scope["path"] == "/api/v1/chat/test_client"


def test_chat_history(client: TestClient):
    # Mock the process_graph function to return a specific value
    with patch("langflow.chat.manager.process_graph") as mock_process_graph:
        mock_process_graph.return_value = ("Hello, I'm a mock response!", "")

        with client.websocket_connect("api/v1/chat/test_client") as websocket:
            # First message should be the history
            history = websocket.receive_json()
            assert history == []  # Empty history
            # Send a message
            payload = {"message": "Hello"}
            websocket.send_json(json.dumps(payload))

            # Receive the response from the server
            response = websocket.receive_json()
            assert response == {
                "is_bot": True,
                "message": None,
                "type": "start",
                "intermediate_steps": "",
                "files": [],
            }
            # Send another message
            payload = {"message": "How are you?"}
            websocket.send_json(json.dumps(payload))

            # Receive the response from the server
            response = websocket.receive_json()
            assert response == {
                "is_bot": True,
                "message": "Hello, I'm a mock response!",
                "type": "end",
                "intermediate_steps": "",
                "files": [],
            }
