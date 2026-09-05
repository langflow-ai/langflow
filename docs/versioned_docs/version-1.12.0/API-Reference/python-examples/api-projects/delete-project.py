import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"accept": "*/*", "Content-Type": "application/json", "x-api-key": api_key}

create = requests.post(
    f"{base}/api/v1/projects/",
    headers=headers,
    json={
        "name": "docs-example-delete-me",
        "description": "Temporary project",
        "components_list": [],
        "flows_list": [],
    },
    timeout=30,
)
create.raise_for_status()
project_id = create.json()["id"]

delete = requests.delete(f"{base}/api/v1/projects/{project_id}", headers=headers, timeout=30)
delete.raise_for_status()
print(delete.text)
