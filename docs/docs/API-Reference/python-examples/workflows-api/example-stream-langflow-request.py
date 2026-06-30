import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

payload = {
    "flow_id": flow_id,
    "input_value": "Hello from a Langflow stream client",
    "mode": "stream",
    "session_id": "session-123",
}

with requests.post(
    f"{base}/api/v2/workflows",
    headers=headers,
    json=payload,
    stream=True,
    timeout=120,
) as response:
    response.raise_for_status()
    for line in response.iter_lines(decode_unicode=True):
        if line:
            print(line)
