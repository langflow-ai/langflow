import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}
payload = {
    "flow_id": flow_id,
    "input_value": "what is 2+2",
    "session_id": "session-123",
}

response = requests.post(f"{base}/api/v2/workflows", headers=headers, json=payload, timeout=120)
response.raise_for_status()
body = response.json()
print(body["output"]["text"])
