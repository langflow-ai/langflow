import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

url = f"{base}/api/v1/responses"

headers = {
    "Content-Type": "application/json",
    "x-api-key": api_key,
}

payload = {
    "model": flow_id,
    "input": "Calculate 23 * 15 and show me the result",
    "stream": False,
    "include": ["tool_call.results"],
}

response = requests.post(url, headers=headers, json=payload, timeout=120)
response.raise_for_status()

print(response.text)
