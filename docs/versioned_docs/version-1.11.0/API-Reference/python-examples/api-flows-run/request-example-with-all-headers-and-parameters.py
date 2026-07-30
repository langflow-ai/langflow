import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {
    "Content-Type": "application/json",
    "accept": "application/json",
    "x-api-key": api_key,
}

payload = {
    "input_value": "Tell me a story",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "chat_output",
    "session_id": "chat-123",
}

response = requests.post(
    f"{base}/api/v1/run/{flow_id}?stream=false",
    headers=headers,
    json=payload,
    timeout=60,
)
response.raise_for_status()
print(response.text)
