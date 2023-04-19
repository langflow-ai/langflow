import json


def test_websocket_connection(client):
    with client.websocket_connect("/ws") as websocket:
        assert websocket.client == client
        assert websocket.url.path == "/ws"


def test_chat_history(client):
    chat_history = ["Test message 1", "Test message 2"]

    with client.websocket_connect("/ws") as websocket:
        received_history = websocket.receive_text()
        received_history = json.loads(received_history)

        assert received_history == chat_history


def test_send_message(client, basic_graph):
    with client.websocket_connect("/ws") as websocket:
        # Send the JSON payload through the WebSocket connection
        websocket.send_text(basic_graph)

        # Receive and parse the response from the server
        response = websocket.receive_text()
        response = json.loads(response)

        # Test that the response is as expected
        assert response == "Your response message here"
