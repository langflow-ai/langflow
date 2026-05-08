import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

start = requests.post(
    f"{base}/api/v2/workflows",
    headers=headers,
    json={"flow_id": flow_id, "background": True, "stream": False, "inputs": {}},
    timeout=60,
)
start.raise_for_status()
job_id = start.json()["job_id"]

stop = requests.post(
    f"{base}/api/v2/workflows/stop",
    headers=headers,
    json={"job_id": job_id},
    timeout=60,
)
print(stop.status_code, stop.text)
