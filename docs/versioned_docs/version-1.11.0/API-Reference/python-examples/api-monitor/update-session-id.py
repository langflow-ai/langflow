import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")

headers = {"accept": "application/json", "x-api-key": api_key}

list_resp = requests.get(
    f"{base}/api/v1/monitor/messages",
    headers=headers,
    params={"flow_id": flow_id},
    timeout=30,
)
list_resp.raise_for_status()
messages = list_resp.json()
if not messages:
    print("No messages; cannot migrate session id.")
    raise SystemExit(0)

old_session_id = messages[0]["session_id"]
new_session_id = f"{old_session_id}-migrated"

response = requests.patch(
    f"{base}/api/v1/monitor/messages/session/{old_session_id}",
    headers=headers,
    params={"new_session_id": new_session_id},
    timeout=30,
)
response.raise_for_status()
print(response.text)
