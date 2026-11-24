import os
import uuid

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

payload = {
    "name": f"docs-example-updated-flow-{uuid.uuid4().hex[:8]}",
    "description": "Updated via API docs Python example",
    "locked": False,
}

response = requests.patch(f"{base}/api/v1/flows/{flow_id}", headers=headers, json=payload, timeout=30)
response.raise_for_status()
print(response.text)
