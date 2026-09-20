import json
import os
from pathlib import Path

import requests

base = os.environ.get("LANGFLOW_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

fixtures = Path(__file__).resolve().parents[2] / "fixtures"
image_path = Path(os.environ.get("SAMPLE_IMAGE_FILE", str(fixtures / "sample-upload.png")))

headers = {"accept": "application/json", "x-api-key": api_key}

upload = requests.post(
    f"{base}/api/v1/files/upload/{flow_id}",
    headers=headers,
    files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
    timeout=30,
)
upload.raise_for_status()

listed = requests.get(f"{base}/api/v1/files/list/{flow_id}", headers=headers, timeout=30)
listed.raise_for_status()
print(json.dumps({"upload": upload.json(), "list": listed.json()}))
