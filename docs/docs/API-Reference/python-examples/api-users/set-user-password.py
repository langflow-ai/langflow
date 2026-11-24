import os

import requests

base = os.environ.get("LANGFLOW_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
user_id = os.environ.get("LANGFLOW_USER_ID", "10c1c6a2-ab8a-4748-8700-0e4832fd5ce8")

headers = {"Content-Type": "application/json", "x-api-key": api_key}

payload = {"password": "newsecurepassword123"}

response = requests.patch(f"{base}/api/v1/users/{user_id}", headers=headers, json=payload, timeout=30)
response.raise_for_status()
print(response.text)
