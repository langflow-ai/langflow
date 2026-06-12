import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

who = requests.get(f"{base}/api/v1/users/whoami", headers=headers, timeout=30)
who.raise_for_status()
user_id = who.json()["id"]

# Must differ from the current password (default superuser is often langflow/langflow).
payload = {"password": "DocsExampleResetPass2025!"}

response = requests.patch(
    f"{base}/api/v1/users/{user_id}/reset-password",
    headers=headers,
    json=payload,
    timeout=30,
)
response.raise_for_status()
print(response.text)
