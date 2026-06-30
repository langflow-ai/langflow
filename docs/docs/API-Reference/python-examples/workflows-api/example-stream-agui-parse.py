import json
import os
import re

import requests

base = os.environ.get("LANGFLOW_URL") or os.environ.get("LANGFLOW_SERVER_URL", "")
flow_id = os.environ.get("FLOW_ID", "")
api_key = os.environ.get("LANGFLOW_API_KEY", "")
session_id = os.environ.get("AGUI_SESSION_ID", "thread-123")
number = re.compile(r"-?\d+(?:\.\d+)?")


def extract_number(text: str, tool_results: list) -> float | None:
    """Prefer calculator tool output, then the last number in the assistant reply."""
    for raw in reversed(tool_results):
        if matches := number.findall(str(raw)):
            return float(matches[-1])
    if matches := number.findall(text):
        return float(matches[-1])
    return None


def ask(prompt: str) -> tuple[str, list]:
    """Stream one AG-UI run; return assistant text and tool results."""
    text = ""
    tool_results = []

    with requests.post(
        f"{base}/api/v2/workflows",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "Accept": "text/event-stream",
        },
        json={
            "flow_id": flow_id,
            "input_value": prompt,
            "mode": "stream",
            "stream_protocol": "agui",
            "session_id": session_id,
        },
        stream=True,
        timeout=120,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            event = json.loads(line.removeprefix("data:").strip())
            match event.get("type"):
                case "TEXT_MESSAGE_CONTENT":
                    text += event.get("delta", "")
                case "TOOL_CALL_RESULT":
                    tool_results.append(event.get("content") or event.get("result"))
                case "RUN_ERROR":
                    raise RuntimeError(event.get("message") or "Run failed")
                case "RUN_FINISHED":
                    break

    return text, tool_results


prompt1 = os.environ.get("AGUI_PROMPT1", "What is 847 divided by 7?")
multiplier = int(os.environ.get("AGUI_MULTIPLIER", "3"))

print(f"User: {prompt1}")
reply1, tools1 = ask(prompt1)
quotient = extract_number(reply1, tools1)
if quotient is None:
    raise SystemExit("Could not extract a number from run 1.")
print(f"Assistant: {reply1.strip()}")
print(f"Extracted: {quotient:g}")

prompt2 = os.environ.get("AGUI_PROMPT2") or f"Now multiply {quotient:g} by {multiplier}."
print(f"\nUser: {prompt2}")
reply2, tools2 = ask(prompt2)
product = extract_number(reply2, tools2)
if product is None:
    raise SystemExit("Could not extract a number from run 2.")
print(f"Assistant: {reply2.strip()}")

print("\n=== Calculation chain ===")
print(f"847 ÷ 7 = {quotient:g}")
print(f"{quotient:g} × {multiplier} = {product:g}")
