import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v2/files/{os.getenv('FILE_ID', '')}"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("DELETE", url, headers=headers)
response.raise_for_status()

print(response.text)
