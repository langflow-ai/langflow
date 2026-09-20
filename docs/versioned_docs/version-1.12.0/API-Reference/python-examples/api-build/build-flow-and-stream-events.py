import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/build/{os.getenv('FLOW_ID', '')}/flow"

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {"inputs": {"input_value": "Tell me a story"}}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
