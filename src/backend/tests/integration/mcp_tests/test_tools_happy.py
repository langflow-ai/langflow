import re

import pytest

pytestmark = pytest.mark.asyncio


async def test_connect_and_list_tools(mcp_client):
    transport, client = mcp_client
    tools = await client.list_tools()
    names = sorted(t.name for t in tools)
    expected = {"echo", "add_numbers", "process_data", "simulate_error", "get_server_info"}
    assert expected.issubset(set(names))


async def test_echo_roundtrip(mcp_client):
    _transport, client = mcp_client
    payload = {"message": "integration"}
    result = await client.call_tool("echo", payload)
    assert "integration" in str(result).lower()


async def test_add_numbers(mcp_client):
    _transport, client = mcp_client
    result = await client.call_tool("add_numbers", {"a": 1, "b": 2})

    # The reference server returns text like "Result: 3" wrapped in a dict;
    # make the assertion flexible.
    match = re.search(r"[=:]\s*([0-9]+)", str(result))
    assert match, f"Unexpected result format: {result}"
    assert int(match.group(1)) == 3


async def test_process_data(mcp_client):
    _transport, client = mcp_client
    data = {"name": "test", "values": [1, 2, 3]}
    result = await client.call_tool("process_data", {"data": data})

    # Normalise result into raw text that *should* contain the JSON blob.
    if isinstance(result, dict) and "content" in result:
        # Handle dict style: {"content": [ {"text": "..."}, ... ] }
        pieces = []
        for item in result["content"]:
            if isinstance(item, dict) and "text" in item:
                pieces.append(item["text"])
            else:  # dataclass / namespace
                maybe_text = getattr(item, "text", None)
                if maybe_text:
                    pieces.append(maybe_text)
        raw = "\n".join(pieces)
    else:
        raw = str(result)

    # Locate a JSON object using a DOTALL regex so newlines are captured.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    assert match, f"No JSON found in result: {raw}"

    json_blob = match.group(0).strip()  # remove surrounding whitespace

    # If the blob is quoted with single quotes (repr artefact), strip them.
    if (json_blob.startswith("'{") and json_blob.endswith("'}")) or (
        json_blob.startswith('"{') and json_blob.endswith('}"')):
        json_blob = json_blob[1:-1]

    # Instead of strict JSON parsing (which can break due to double escaping
    # from various SDK reprs) just assert that the expected key/value pairs
    # appear in the textual blob. This keeps the test transport-agnostic and
    # tolerant of formatting differences (pretty JSON, minified, etc.).

    for snippet in [
        '"processed": true',
        '"name": "test"',
        '"sum": 6',
        '"count": 3',
    ]:
        assert snippet in json_blob.replace("\n", " "), f"{snippet} missing in {json_blob}"
