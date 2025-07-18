import asyncio
import json
import os
import pathlib

import httpx
import pytest
from dotenv import load_dotenv
from httpx import AsyncClient
from loguru import logger


# Load environment variables from .env file
def load_env_vars():
    """Load environment variables from .env files."""
    possible_paths = [
        pathlib.Path(".env"),
        pathlib.Path("../../.env"),
        pathlib.Path("../../../.env"),
    ]

    for env_path in possible_paths:
        if env_path.exists():
            logger.info(f"Loading environment variables from {env_path.absolute()}")
            load_dotenv(env_path)
            return True

    logger.warning("No .env file found. Using existing environment variables.")
    return False


# Load environment variables at module import time
load_env_vars()


async def create_global_variable(client: AsyncClient, headers, name, value, variable_type="credential"):
    """Create a global variable in Langflow."""
    payload = {"name": name, "value": value, "type": variable_type, "default_fields": []}

    response = await client.post("/api/v1/variables/", json=payload, headers=headers)
    if response.status_code != 201:
        logger.error(f"Failed to create global variable: {response.content}")
        return False

    logger.info(f"Successfully created global variable: {name}")
    return True


async def load_and_prepare_flow(client: AsyncClient, created_api_key):
    """Load Simple Agent flow and wait for it to be ready."""
    headers = {"x-api-key": created_api_key.api_key}

    # Create OPENAI_API_KEY global variable
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    await create_global_variable(client, headers, "OPENAI_API_KEY", openai_api_key)

    # Load the Simple Agent template
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "base",
        "langflow",
        "initial_setup",
        "starter_projects",
        "Simple Agent.json",
    )

    with open(template_path) as f:
        flow_data = json.load(f)

    # Add the flow
    response = await client.post("/api/v1/flows/", json=flow_data, headers=headers)
    assert response.status_code == 201
    flow = response.json()

    # Poll for flow builds to complete
    max_attempts = 10
    for attempt in range(max_attempts):
        builds_response = await client.get(f"/api/v1/monitor/builds?flow_id={flow['id']}", headers=headers)

        if builds_response.status_code == 200:
            builds = builds_response.json().get("vertex_builds", {})
            all_valid = True
            for node_id, build_list in builds.items():
                if not build_list or build_list[0].get("valid") is not True:
                    all_valid = False
                    break

            if all_valid and builds:
                break

        if attempt < max_attempts - 1:
            await asyncio.sleep(1)

    return flow, headers


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_streaming_format_comparison(client: AsyncClient, created_api_key):
    """Compare raw HTTP streaming formats between OpenAI and our API."""
    # Test input
    input_msg = "What is 25 + 17? Use your calculator tool."

    # Tools definition
    tools = [
        {
            "type": "function",
            "name": "evaluate_expression",
            "description": "Perform basic arithmetic operations on a given expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
                    }
                },
                "required": ["expression"],
            },
        }
    ]

    # Get OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    # === Test OpenAI's raw HTTP streaming format ===
    logger.info("=== Testing OpenAI API Raw HTTP Format ===")

    async with httpx.AsyncClient() as openai_client:
        openai_payload = {"model": "gpt-4o-mini", "input": input_msg, "tools": tools, "stream": True}

        openai_response = await openai_client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
            json=openai_payload,
        )

        logger.info(f"OpenAI status: {openai_response.status_code}")
        if openai_response.status_code != 200:
            logger.error(f"OpenAI error: {openai_response.text}")
            pytest.skip("OpenAI API request failed")

        # Parse OpenAI's raw SSE stream
        openai_content = await openai_response.aread()
        openai_text = openai_content.decode("utf-8")

        openai_events = openai_text.strip().split("\n\n")
        openai_data_events = [evt for evt in openai_events if "data: " in evt and not evt.startswith("data: [DONE]")]

    # === Test Our API's streaming format ===
    logger.info("=== Testing Our API Format ===")

    flow, headers = await load_and_prepare_flow(client, created_api_key)

    our_payload = {"model": flow["id"], "input": input_msg, "stream": True}

    our_response = await client.post("/api/v1/responses", json=our_payload, headers=headers)
    assert our_response.status_code == 200

    our_content = await our_response.aread()
    our_text = our_content.decode("utf-8")

    our_events = our_text.strip().split("\n\n")
    our_data_events = [evt for evt in our_events if "data: " in evt and not evt.startswith("data: [DONE]")]

    # === Parse and compare events ===

    # Extract JSON data from OpenAI events
    openai_parsed = []
    for event_block in openai_data_events:
        lines = event_block.strip().split("\n")
        for line in lines:
            if line.startswith("data: "):
                try:
                    json_str = line.replace("data: ", "", 1)
                    event_data = json.loads(json_str)
                    openai_parsed.append(event_data)
                    break
                except json.JSONDecodeError:
                    continue

    # Extract JSON data from our events
    our_parsed = []
    for event_block in our_data_events:
        lines = event_block.strip().split("\n")
        for line in lines:
            if line.startswith("data: "):
                try:
                    json_str = line.replace("data: ", "", 1)
                    event_data = json.loads(json_str)
                    our_parsed.append(event_data)
                    break
                except json.JSONDecodeError:
                    continue

    # === Analysis ===
    logger.info("Event counts:")
    logger.info(f"  OpenAI: {len(openai_parsed)} events")
    logger.info(f"  Our API: {len(our_parsed)} events")

    # Check for tool call events with detailed logging
    logger.info("Detailed OpenAI event analysis:")
    output_item_added_events = [e for e in openai_parsed if e.get("type") == "response.output_item.added"]
    logger.info(f"  Found {len(output_item_added_events)} 'response.output_item.added' events")

    for i, event in enumerate(output_item_added_events):
        item = event.get("item", {})
        item_type = item.get("type", "unknown")
        logger.info(f"    Event {i}: item.type = '{item_type}'")
        logger.info(f"    Event {i}: item keys = {list(item.keys())}")
        if "name" in item:
            logger.info(f"    Event {i}: item.name = '{item.get('name')}'")
        logger.debug(f"    Event {i}: full item = {json.dumps(item, indent=6)}")

    openai_tool_events = [
        e
        for e in openai_parsed
        if e.get("type") == "response.output_item.added" and e.get("item", {}).get("type") == "tool_call"
    ]
    openai_function_events = [
        e
        for e in openai_parsed
        if e.get("type") == "response.output_item.added" and e.get("item", {}).get("type") == "function_call"
    ]

    logger.info("Detailed Our API event analysis:")
    our_output_item_added_events = [e for e in our_parsed if e.get("type") == "response.output_item.added"]
    logger.info(f"  Found {len(our_output_item_added_events)} 'response.output_item.added' events")

    for i, event in enumerate(our_output_item_added_events):
        item = event.get("item", {})
        item_type = item.get("type", "unknown")
        logger.info(f"    Event {i}: item.type = '{item_type}'")
        logger.info(f"    Event {i}: item keys = {list(item.keys())}")
        if "name" in item:
            logger.info(f"    Event {i}: item.name = '{item.get('name')}'")
        logger.debug(f"    Event {i}: full item = {json.dumps(item, indent=6)}")

    our_function_events = [
        e
        for e in our_parsed
        if e.get("type") == "response.output_item.added" and e.get("item", {}).get("type") == "function_call"
    ]

    logger.info("Tool call detection results:")
    logger.info(f"  OpenAI tool_call events: {len(openai_tool_events)}")
    logger.info(f"  OpenAI function_call events: {len(openai_function_events)}")
    logger.info(f"  Our function_call events: {len(our_function_events)}")

    # Use the correct event type for OpenAI (function_call vs tool_call)
    openai_actual_tool_events = openai_function_events if openai_function_events else openai_tool_events

    logger.info("Function call events:")
    logger.info(f"  OpenAI: {len(openai_actual_tool_events)} function call events")
    logger.info(f"  Our API: {len(our_function_events)} function call events")

    # Show event types
    openai_types = {e.get("type", e.get("object", "unknown")) for e in openai_parsed}
    our_types = {e.get("type", e.get("object", "unknown")) for e in our_parsed}

    logger.info("Event types:")
    logger.info(f"  OpenAI: {sorted(openai_types)}")
    logger.info(f"  Our API: {sorted(our_types)}")

    # Print sample events for debugging
    logger.info("Sample OpenAI events:")
    for i, event in enumerate(openai_parsed[:3]):
        logger.debug(f"  {i}: {json.dumps(event, indent=2)[:200]}...")

    logger.info("Sample Our events:")
    for i, event in enumerate(our_parsed[:3]):
        logger.debug(f"  {i}: {json.dumps(event, indent=2)[:200]}...")

    if openai_actual_tool_events:
        logger.info("OpenAI tool call example:")
        logger.debug(f"  {json.dumps(openai_actual_tool_events[0], indent=2)}")

    if our_function_events:
        logger.info("Our function call example:")
        logger.debug(f"  {json.dumps(our_function_events[0], indent=2)}")

    # === Validation ===

    # Basic validation
    assert len(openai_parsed) > 0, "No OpenAI events received"
    assert len(our_parsed) > 0, "No events from our API"

    # Check if both APIs produced function call events
    if len(openai_actual_tool_events) > 0:
        logger.success("✅ OpenAI produced function call events")
        if len(our_function_events) > 0:
            logger.success("✅ Our API also produced function call events")
            logger.success("✅ Both APIs support function call streaming")
        else:
            logger.error("❌ Our API did not produce function call events")
            pytest.fail("Our API should produce function call events when OpenAI does")
    else:
        logger.info("ℹ️  No function calls were made by OpenAI")

    logger.info("📊 Test Summary:")
    logger.info(f"  OpenAI events: {len(openai_parsed)}")
    logger.info(f"  Our events: {len(our_parsed)}")
    logger.info(f"  OpenAI function events: {len(openai_actual_tool_events)}")
    logger.info(f"  Our function events: {len(our_function_events)}")
    compatibility_result = "✅ PASS" if len(our_function_events) > 0 or len(openai_actual_tool_events) == 0 else "❌ FAIL"
    logger.info(f"  Format compatibility: {compatibility_result}")
