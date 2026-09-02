import os

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")

# `/logs-stream` is an SSE endpoint. For doc example stability, only read a small
# number of events, then close the connection.
url = f"{base}/logs-stream"
headers = {"accept": "text/event-stream", "x-api-key": api_key}

response = requests.get(url, headers=headers, stream=True, timeout=30)
response.raise_for_status()

events_read = 0
chunks: list[str] = []
for line in response.iter_lines(decode_unicode=True):
    if line:
        chunks.append(line)
        events_read += 1
        if events_read >= 3:
            break

response.close()

print("\n".join(chunks))
