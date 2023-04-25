import json
from unittest.mock import patch
from langflow.api.schemas import ChatMessage
from fastapi.testclient import TestClient


def test_websocket_connection(client: TestClient):
    with client.websocket_connect("/ws/test_client") as websocket:
        assert websocket.scope["client"] == ["testclient", 50000]
        assert websocket.scope["path"] == "/ws/test_client"


def test_chat_history(client: TestClient):
    chat_history = []

    # Mock the process_graph function to return a specific value
    with patch("langflow.api.chat_manager.process_graph") as mock_process_graph:
        mock_process_graph.return_value = ("Hello, I'm a mock response!", "")

        with client.websocket_connect("/ws/test_client") as websocket:
            # First message should be the history
            history = websocket.receive_json()
            assert json.loads(history) == []  # Empty history
            # Send a message
            payload = {"message": "Hello"}
            websocket.send_json(json.dumps(payload))

            # Receive the response from the server
            response = websocket.receive_json()
            assert json.loads(response) == {
                "sender": "bot",
                "message": None,
                "intermediate_steps": "",
                "type": "start",
            }
            # Send another message
            payload = {"message": "How are you?"}
            websocket.send_json(json.dumps(payload))

            # Receive the response from the server
            response = websocket.receive_json()
            assert json.loads(response) == {
                "sender": "bot",
                "message": "Hello, I'm a mock response!",
                "intermediate_steps": "",
                "type": "end",
            }
