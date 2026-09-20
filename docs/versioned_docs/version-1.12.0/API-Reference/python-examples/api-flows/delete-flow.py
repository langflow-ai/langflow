import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

create = requests.post(
    f"{base}/api/v1/flows/",
    headers=headers,
    json={
        "name": "docs-example-delete-me",
        "description": "Temporary flow for delete-flow example",
        "data": {"nodes": [], "edges": []},
    },
    timeout=30,
)
create.raise_for_status()
flow_id = create.json()["id"]

delete = requests.delete(f"{base}/api/v1/flows/{flow_id}", headers=headers, timeout=30)
delete.raise_for_status()
print(delete.text)
