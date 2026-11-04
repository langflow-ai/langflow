# Same pattern as continue-conversations-with-response-and-session-ids-2.py; you can pass
# `previous_response_id` from the prior turn (or a session id your app stores).

import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

url = f"{base}/api/v1/responses"

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json",
}

payload = {
    "model": flow_id,
    "input": "Hello, my name is Alice",
    "stream": False,
}

response = requests.post(url, headers=headers, json=payload, timeout=120)
response.raise_for_status()

print(response.text)
