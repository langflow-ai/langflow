import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/projects/"

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {
    "name": "new_project_name",
    "description": "string",
    "components_list": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    "flows_list": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
