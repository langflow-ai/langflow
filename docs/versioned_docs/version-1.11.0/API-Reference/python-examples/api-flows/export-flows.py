import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")
folder_id = os.environ.get("PROJECT_ID") or os.environ.get("FOLDER_ID", "")

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": api_key,
}

# Export needs at least two flows to return a ZIP; a single id returns JSON.
extra = requests.post(
    f"{base}/api/v1/flows/",
    headers=headers,
    json={
        "name": "docs-export-temp-flow",
        "description": "Temporary second flow for export example",
        "data": {"nodes": [], "edges": []},
        **({"folder_id": folder_id} if folder_id else {}),
    },
    timeout=30,
)
extra.raise_for_status()
extra_id = extra.json()["id"]

payload = [flow_id, extra_id]

response = requests.post(f"{base}/api/v1/flows/download/", headers=headers, json=payload, timeout=60)
response.raise_for_status()

with open("langflow-flows.zip", "wb") as f:
    f.write(response.content)
print("Saved response to langflow-flows.zip")

requests.delete(f"{base}/api/v1/flows/{extra_id}", headers=headers, timeout=30)
