import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")

headers = {"accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key}

list_resp = requests.get(
    f"{base}/api/v1/monitor/messages",
    headers=headers,
    params={"flow_id": flow_id},
    timeout=30,
)
list_resp.raise_for_status()
messages = list_resp.json()
if not messages:
    print("No messages to update.")
    raise SystemExit(0)

message_id = messages[0]["id"]
payload = {"text": "testing 1234"}

response = requests.put(
    f"{base}/api/v1/monitor/messages/{message_id}",
    headers=headers,
    json=payload,
    timeout=30,
)
response.raise_for_status()
print(response.text)
