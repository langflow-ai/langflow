import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/flows/"

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

payload = {
    "name": "string2",
    "description": "string",
    "icon": "string",
    "icon_bg_color": "#FF0000",
    "gradient": "string",
    "data": {},
    "is_component": False,
    "updated_at": "2024-12-30T15:48:01.519Z",
    "webhook": False,
    "endpoint_name": "string",
    "tags": ["string"],
}

response = requests.request("POST", url, headers=headers, json=payload)
response.raise_for_status()

print(response.text)
