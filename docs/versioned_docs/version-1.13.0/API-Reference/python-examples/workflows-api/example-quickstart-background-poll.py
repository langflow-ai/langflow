import os
import time

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

start = requests.post(
    f"{base}/api/v2/workflows",
    headers=headers,
    json={
        "flow_id": flow_id,
        "input_value": "Process this in the background",
        "session_id": "session-456",
        "mode": "background",
    },
    timeout=60,
)
start.raise_for_status()
job_id = start.json()["job_id"]
print(f"Queued job {job_id}")

while True:
    status = requests.get(
        f"{base}/api/v2/workflows",
        headers=headers,
        params={"job_id": job_id},
        timeout=60,
    )
    status.raise_for_status()
    body = status.json()

    if body.get("object") == "response" and body.get("status") == "completed":
        print(body["output"]["text"])
        break

    if body.get("status") in {"failed", "cancelled", "timed_out"}:
        raise SystemExit(f"Job ended with status {body.get('status')}")

    time.sleep(1)
