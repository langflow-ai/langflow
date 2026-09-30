import os

import requests

url = f"{os.getenv('LANGFLOW_SERVER_URL', '')}/health_check"

headers = {
    "accept": "application/json",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
