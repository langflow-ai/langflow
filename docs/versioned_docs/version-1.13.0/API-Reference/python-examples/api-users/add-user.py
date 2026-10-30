import os
import uuid

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

payload = {
    "username": f"docsuser_{uuid.uuid4().hex[:12]}",
    "password": "securepassword123",
}

response = requests.post(f"{base}/api/v1/users/", headers=headers, json=payload, timeout=30)
response.raise_for_status()
print(response.text)
