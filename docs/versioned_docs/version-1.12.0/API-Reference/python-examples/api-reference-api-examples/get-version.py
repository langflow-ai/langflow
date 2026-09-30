import os

import requests

url = f"{os.getenv('LANGFLOW_SERVER_URL', '')}/api/v1/version"

headers = {
    "accept": "application/json",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
