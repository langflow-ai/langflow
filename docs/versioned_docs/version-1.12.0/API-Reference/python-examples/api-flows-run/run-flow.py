import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

url = f"{base}/api/v1/run/{flow_id}"

headers = {
    "Content-Type": "application/json",
    "x-api-key": api_key,
}

payload = {
    "input_value": "Tell me about something interesting!",
    "session_id": "chat-123",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "",
}

response = requests.post(url, headers=headers, json=payload, timeout=60)
response.raise_for_status()
print(response.text)
