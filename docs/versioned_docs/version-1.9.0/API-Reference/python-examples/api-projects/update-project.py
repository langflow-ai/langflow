import os
import uuid

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
project_id = os.environ.get("PROJECT_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

payload = {
    "name": f"docs-example-renamed-project-{uuid.uuid4().hex[:8]}",
    "description": "Updated via API docs Python example",
}

response = requests.patch(f"{base}/api/v1/projects/{project_id}", headers=headers, json=payload, timeout=30)
response.raise_for_status()
print(response.text)
