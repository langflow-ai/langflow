import os

from openai import OpenAI

base = (os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")).rstrip("/")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
flow_id = os.environ.get("FLOW_ID", "")

client = OpenAI(
    base_url=f"{base}/api/v1/",
    default_headers={"x-api-key": api_key},
    api_key="dummy-api-key",  # Required by OpenAI SDK but not used by Langflow
)

try:
    response = client.responses.create(
        model=flow_id,
        input="There is an event that happens on the second wednesday of every month. What are the event dates in 2026?",
    )
except Exception as exc:
    # Empty bootstrap flows return an error body; use a flow with ChatInput + ChatOutput in the UI.
    print(exc)
else:
    try:
        print(response.output_text)
    except Exception:
        print(response)
