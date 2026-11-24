import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/flows/?remove_example_flows=true&components_only=false&get_all=false&project_id={os.getenv('PROJECT_ID', '')}&header_flows=false&page=1&size=1"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

print(response.text)
