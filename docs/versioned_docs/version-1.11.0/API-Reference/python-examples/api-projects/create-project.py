import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/projects/"

headers = {
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {"name": "new_project_name", "description": "string", "components_list": [], "flows_list": []}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
