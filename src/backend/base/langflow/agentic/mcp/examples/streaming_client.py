"""Example streaming HTTP client for Langflow Agentic MCP Server.

Demonstrates SSE (Server-Sent Events) streaming.
"""

import json
import time

import requests


def stream_tool_call(tool_name: str, arguments: dict, base_url: str = "http://localhost:8000"):
    """Stream tool execution results using SSE.

    Args:
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        base_url: Base URL of the server

    Yields:
        Parsed event dictionaries
    """
    payload = {"tool_name": tool_name, "arguments": arguments}

    print(f"\n📡 Streaming {tool_name}...")
    print(f"   Arguments: {arguments}")
    print(f"   URL: {base_url}/stream\n")

    response = requests.post(
        f"{base_url}/stream", json=payload, stream=True, timeout=60  # Enable streaming
    )

    response.raise_for_status()

    for line in response.iter_lines():
        if line:
            decoded_line = line.decode("utf-8")

            # SSE format: "data: {json}"
            if decoded_line.startswith("data: "):
                data_str = decoded_line[6:]  # Remove "data: " prefix

                # Check for end marker
                if data_str == "[DONE]":
                    print("✅ Stream completed!\n")
                    break

                try:
                    event = json.loads(data_str)
                    yield event

                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    print(f"   Raw data: {data_str}")


def demo_basic_streaming():
    """Demonstrate basic streaming."""
    print("=" * 80)
    print("Example 1: Basic Streaming")
    print("=" * 80)

    for event in stream_tool_call("get_templates_count", {}):
        event_type = event.get("event")

        if event_type == "start":
            print(f"🚀 Started: {event.get('tool')}")

        elif event_type == "data":
            data = event.get("data")
            print(f"📦 Data received: {data}")

        elif event_type == "done":
            print(f"✅ Completed: success={event.get('success')}")

        elif event_type == "error":
            print(f"❌ Error: {event.get('error')}")


def demo_streaming_with_query():
    """Demonstrate streaming with query parameters."""
    print("\n" + "=" * 80)
    print("Example 2: Streaming with Query")
    print("=" * 80)

    for event in stream_tool_call("list_templates", {"query": "agent", "fields": ["id", "name"]}):
        event_type = event.get("event")

        if event_type == "start":
            print(f"🚀 Searching for templates with 'agent'...")

        elif event_type == "data":
            templates = event.get("data", [])
            print(f"📦 Found {len(templates)} templates:")
            for i, template in enumerate(templates[:3], 1):
                print(f"   {i}. {template.get('name')}")
            if len(templates) > 3:
                print(f"   ... and {len(templates) - 3} more")

        elif event_type == "done":
            print(f"✅ Search completed")


def demo_streaming_all_tags():
    """Demonstrate streaming tag retrieval."""
    print("\n" + "=" * 80)
    print("Example 3: Streaming Tags")
    print("=" * 80)

    for event in stream_tool_call("get_all_tags", {}):
        event_type = event.get("event")

        if event_type == "start":
            print(f"🚀 Fetching all tags...")

        elif event_type == "data":
            tags = event.get("data", [])
            print(f"📦 Received {len(tags)} tags:")
            # Display in columns
            for i in range(0, len(tags), 4):
                row = tags[i : i + 4]
                print(f"   {' | '.join(row)}")

        elif event_type == "done":
            print(f"✅ Tags retrieved")


def demo_streaming_with_timing():
    """Demonstrate streaming with timing measurements."""
    print("\n" + "=" * 80)
    print("Example 4: Streaming with Timing")
    print("=" * 80)

    start_time = time.time()
    first_byte_time = None

    for event in stream_tool_call("list_templates", {"tags": ["agents"]}):
        current_time = time.time()

        if first_byte_time is None:
            first_byte_time = current_time - start_time
            print(f"⏱️  Time to first byte: {first_byte_time * 1000:.2f}ms\n")

        event_type = event.get("event")

        if event_type == "start":
            print(f"🚀 Starting at t={current_time - start_time:.3f}s")

        elif event_type == "data":
            templates = event.get("data", [])
            elapsed = current_time - start_time
            print(f"📦 Data at t={elapsed:.3f}s ({len(templates)} items)")

        elif event_type == "done":
            elapsed = current_time - start_time
            print(f"✅ Done at t={elapsed:.3f}s")
            print(f"\n📊 Total time: {elapsed * 1000:.2f}ms")


def demo_error_handling():
    """Demonstrate error handling in streaming."""
    print("\n" + "=" * 80)
    print("Example 5: Error Handling")
    print("=" * 80)

    # Try to call a non-existent tool
    print("Attempting to call non-existent tool...")

    try:
        for event in stream_tool_call("nonexistent_tool", {}):
            event_type = event.get("event")

            if event_type == "error":
                print(f"❌ Caught error: {event.get('error')}")
                print(f"   Error type: {event.get('type', 'Unknown')}")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Status code: {e.response.status_code}")


def demo_multiple_concurrent_streams():
    """Demonstrate multiple concurrent streaming requests."""
    print("\n" + "=" * 80)
    print("Example 6: Multiple Concurrent Streams")
    print("=" * 80)

    import concurrent.futures

    def stream_and_count(tool_name, args):
        """Stream and count events."""
        event_count = 0
        for event in stream_tool_call(tool_name, args):
            event_count += 1
        return tool_name, event_count

    # Stream multiple tools concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(stream_and_count, "get_templates_count", {}),
            executor.submit(stream_and_count, "get_all_tags", {}),
            executor.submit(stream_and_count, "list_templates", {"query": "chat"}),
        ]

        for future in concurrent.futures.as_completed(futures):
            tool_name, count = future.result()
            print(f"✅ {tool_name}: {count} events")


def main():
    """Run all streaming examples."""
    print("\n" + "🌊 " * 40)
    print("LANGFLOW AGENTIC MCP - STREAMING HTTP CLIENT EXAMPLES")
    print("🌊 " * 40 + "\n")

    print("Starting HTTP streaming server on http://localhost:8000")
    print("Make sure the server is running:")
    print("  python -m langflow.agentic.mcp.cli --http\n")

    try:
        # Test server connectivity
        response = requests.get("http://localhost:8000/info", timeout=5)
        response.raise_for_status()
        print(f"✅ Server is running: {response.json()['name']}\n")

    except requests.exceptions.RequestException as e:
        print(f"❌ Server not reachable: {e}")
        print("\nPlease start the server first:")
        print("  python -m langflow.agentic.mcp.cli --http\n")
        return

    # Run examples
    demo_basic_streaming()
    demo_streaming_with_query()
    demo_streaming_all_tags()
    demo_streaming_with_timing()
    demo_error_handling()
    demo_multiple_concurrent_streams()

    print("\n" + "=" * 80)
    print("✅ All streaming examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
