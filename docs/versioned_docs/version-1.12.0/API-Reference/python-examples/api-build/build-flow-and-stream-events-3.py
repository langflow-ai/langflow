import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
job_id = os.environ.get("JOB_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

# Use the API's `event_delivery` query param to avoid keeping a streaming connection open.
# For local smoke tests, polling returns a finite JSON response.
url = f"{base}/api/v1/build/{job_id}/events?event_delivery=polling"

headers = {"accept": "application/json", "x-api-key": api_key}

response = requests.get(url, headers=headers, timeout=60)
response.raise_for_status()

print(response.text)
