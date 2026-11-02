import os
from pathlib import Path

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

fixtures = Path(__file__).resolve().parents[2] / "fixtures"
default_json = fixtures / "project-import.json"
import_path = Path(os.environ.get("PROJECT_IMPORT_JSON", str(default_json)))

headers = {"accept": "application/json", "x-api-key": api_key}

files = {"file": (import_path.name, import_path.read_bytes(), "application/json")}
response = requests.post(f"{base}/api/v1/projects/upload/", headers=headers, files=files, timeout=60)

response.raise_for_status()
print(response.text)
