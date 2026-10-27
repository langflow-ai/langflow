import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/run/{os.getenv('FLOW_ID', '')}"

headers = {
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {
    "input_value": "what do you see?",
    "output_type": "chat",
    "input_type": "text",
    "tweaks": {
        "Read-File-1olS3": {"path": ["07e5b864-e367-4f52-b647-a48035ae7e5e/3a290013-fe1e-4d3d-a454-cacae81288f3.pdf"]}
    },
}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
