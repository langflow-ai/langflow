import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/flows/basic_examples/"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
