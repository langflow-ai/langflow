import json
import os
from pathlib import Path

import requests

base = os.environ.get("LANGFLOW_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

fixtures = Path(__file__).resolve().parents[2] / "fixtures"
upload_path = Path(os.environ.get("SAMPLE_UPLOAD_FILE", str(fixtures / "sample-upload.txt")))

headers = {"accept": "application/json", "x-api-key": api_key}

upload = requests.post(
    f"{base}/api/v1/files/upload/{flow_id}",
    headers=headers,
    files={"file": (upload_path.name, upload_path.read_bytes(), "text/plain")},
    timeout=30,
)
upload.raise_for_status()
meta = upload.json()
file_name = meta["file_path"].split("/")[-1]

download = requests.get(
    f"{base}/api/v1/files/download/{flow_id}/{file_name}",
    headers=headers,
    timeout=30,
)
download.raise_for_status()

out_path = Path("downloaded_file.txt")
out_path.write_bytes(download.content)
print(json.dumps({"saved_bytes": len(download.content), "path": str(out_path), "upload": meta}))
