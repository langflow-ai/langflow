import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/projects/download/{os.getenv('PROJECT_ID', '')}"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

response = requests.request("GET", url, headers=headers)
response.raise_for_status()

with open("langflow-project.zip", "wb") as f:
    f.write(response.content)
print("Saved response to langflow-project.zip")
