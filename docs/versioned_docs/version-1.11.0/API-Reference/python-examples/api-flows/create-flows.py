import os
import uuid

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
folder_id = (os.environ.get("PROJECT_ID") or os.environ.get("FOLDER_ID") or "").strip()

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}


def _flow_doc(suffix: str) -> dict:
    doc = {
        "name": f"batch-flow-{uuid.uuid4().hex[:8]}",
        "description": f"Docs batch example {suffix}",
        "data": {"nodes": [], "edges": []},
    }
    if folder_id:
        doc["folder_id"] = folder_id
    return doc


payload = {"flows": [_flow_doc("A"), _flow_doc("B")]}

response = requests.post(f"{base}/api/v1/flows/batch/", headers=headers, json=payload, timeout=30)
response.raise_for_status()
print(response.text)
