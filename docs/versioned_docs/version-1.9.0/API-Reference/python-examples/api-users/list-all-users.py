import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/users/?skip=0&limit=10"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
