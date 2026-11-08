import os

import requests

base_url = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "http://127.0.0.1:7860")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")

response = requests.get(
    f"{base_url}/api/v1/monitor/traces",
    params={"flow_id": flow_id, "page": 1, "size": 50},
    headers={"x-api-key": api_key, "accept": "application/json"},
    timeout=30,
)
response.raise_for_status()
print(response.json())
