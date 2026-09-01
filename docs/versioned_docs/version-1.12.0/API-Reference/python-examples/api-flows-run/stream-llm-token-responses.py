import os

import requests

url = f"{os.getenv('LANGFLOW_SERVER_URL', '')}/api/v1/run/{os.getenv('FLOW_ID', '')}?stream=true"

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {"message": "Tell me something interesting!", "session_id": "chat-123"}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
