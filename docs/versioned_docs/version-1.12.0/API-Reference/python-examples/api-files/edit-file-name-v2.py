import json
import os
from pathlib import Path
from urllib.parse import quote

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

fixtures = Path(__file__).resolve().parents[2] / "fixtures"
upload_path = Path(os.environ.get("SAMPLE_UPLOAD_FILE", str(fixtures / "sample-upload.txt")))

headers = {"accept": "application/json", "x-api-key": api_key}

upload = requests.post(
    f"{base}/api/v2/files",
    headers=headers,
    files={"file": (upload_path.name, upload_path.read_bytes(), "text/plain")},
    timeout=30,
)
upload.raise_for_status()
file_id = upload.json()["id"]

new_name = os.environ.get("RENAMED_FILE_BASENAME", "renamed-sample-upload")
url = f"{base}/api/v2/files/{file_id}?name={quote(new_name)}"

response = requests.put(url, headers=headers, timeout=30)
response.raise_for_status()
print(json.dumps(response.json()))
