import os

import requests

url = f"{os.getenv('LANGFLOW_URL', '')}/api/v1/flows/upload/?folder_id={os.getenv('FOLDER_ID', '')}"

headers = {
    "accept": "application/json",
    "x-api-key": f"{os.getenv('LANGFLOW_API_KEY', '')}",
}

files = {
    "file": open(os.getenv("FLOW_IMPORT_FILE", "docs/docs/API-Reference/fixtures/flow-import.json"), "rb"),
}

response = requests.request("POST", url, headers=headers, files=files)
response.raise_for_status()

print(response.text)

for _f in files.values():
    if hasattr(_f, "close"):
        _f.close()
