import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/monitor/messages/session/different_session_id_2"

headers = {
    "accept": "*/*",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("DELETE", url, headers=headers)
response.raise_for_status()

print(response.text)
