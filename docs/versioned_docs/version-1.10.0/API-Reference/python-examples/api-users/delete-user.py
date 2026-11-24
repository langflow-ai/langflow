import os
import uuid

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

create = requests.post(
    f"{base}/api/v1/users/",
    headers=headers,
    json={"username": f"docsdel_{uuid.uuid4().hex[:12]}", "password": "securepassword123"},
    timeout=30,
)
create.raise_for_status()
user_id = create.json()["id"]

delete = requests.delete(f"{base}/api/v1/users/{user_id}", headers=headers, timeout=30)
delete.raise_for_status()
print(delete.text)
