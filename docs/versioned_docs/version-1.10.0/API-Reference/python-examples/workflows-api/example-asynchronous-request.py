import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

payload = {
    "flow_id": flow_id,
    "background": True,
    "stream": False,
    "inputs": {},
}

response = requests.post(f"{base}/api/v2/workflows", headers=headers, json=payload, timeout=60)
response.raise_for_status()
print(response.text)
