import os
from uuid import UUID

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")

headers = {"accept": "*/*", "Content-Type": "application/json", "x-api-key": api_key}

list_resp = requests.get(
    f"{base}/api/v1/monitor/messages",
    headers=headers,
    params={"flow_id": flow_id},
    timeout=30,
)
list_resp.raise_for_status()
messages = list_resp.json()
if not messages:
    print("No messages to delete.")
    raise SystemExit(0)

ids = [UUID(str(m["id"])) for m in messages[:2]]
params = [("message_ids", str(i)) for i in ids]

response = requests.delete(f"{base}/api/v1/monitor/messages", headers=headers, params=params, timeout=30)
response.raise_for_status()
print(response.status_code)
