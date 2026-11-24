import json
import os
from pathlib import Path

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

download = requests.get(
    f"{base}/api/v2/files/{file_id}",
    headers=headers,
    timeout=30,
)
download.raise_for_status()

out_path = Path("downloaded_file.txt")
out_path.write_bytes(download.content)
print(json.dumps({"saved_bytes": len(download.content), "file_id": str(file_id), "path": str(out_path)}))
