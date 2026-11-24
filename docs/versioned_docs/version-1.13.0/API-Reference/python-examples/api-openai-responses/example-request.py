import os

import requests

url = f"{os.getenv('LANGFLOW_SERVER_URL', '')}/api/v1/responses"

headers = {
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
    "Content-Type": "application/json",
}

payload = {"model": "$YOUR_FLOW_ID", "input": "Hello, how are you?", "stream": False}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
