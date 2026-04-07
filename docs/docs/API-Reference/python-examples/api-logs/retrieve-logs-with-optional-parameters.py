import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/logs?lines_before=0&lines_after=0&timestamp=0"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
