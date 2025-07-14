import pytest
from httpx import AsyncClient
import json
import os
import asyncio
from dotenv import load_dotenv
import pathlib
import uuid

# Load environment variables from .env file
def load_env_vars():
    """Load environment variables from .env files."""
    # Try to find .env file in various locations
    possible_paths = [
        pathlib.Path(".env"),  # Current directory
        pathlib.Path("../../.env"),  # Project root
        pathlib.Path("../../../.env"),  # One level up from project root
    ]
    
    for env_path in possible_paths:
        if env_path.exists():
            print(f"Loading environment variables from {env_path.absolute()}")
            load_dotenv(env_path)
            return True
    
    print("Warning: No .env file found. Using existing environment variables.")
    return False

# Load environment variables at module import time
load_env_vars()

async def create_global_variable(client: AsyncClient, headers, name, value, variable_type="credential"):
    """Create a global variable in Langflow."""
    payload = {
        "name": name,
        "value": value,
        "type": variable_type,
        "default_fields": []
    }
    
    response = await client.post("/api/v1/variables/", json=payload, headers=headers)
    if response.status_code != 201:
        print(f"Failed to create global variable: {response.content}")
        return False
    
    print(f"Successfully created global variable: {name}")
    return True

async def load_and_prepare_flow(client: AsyncClient, created_api_key):
    """Load a flow template, create it, and wait for it to be ready."""
    # Set up headers
    headers = {"x-api-key": created_api_key.api_key}
    
    # Create OPENAI_API_KEY global variable
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")
    
    await create_global_variable(client, headers, "OPENAI_API_KEY", openai_api_key)
    
    # Load the Basic Prompting template
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "base", "langflow", "initial_setup", "starter_projects", "Basic Prompting.json"
    )
    
    with open(template_path, "r") as f:
        flow_data = json.load(f)
    
    # Add the flow
    response = await client.post("/api/v1/flows/", json=flow_data, headers=headers)
    print(f"Flow creation response: {response.status_code}")
    
    assert response.status_code == 201
    flow = response.json()
    
    # Poll for flow builds to complete
    max_attempts = 10
    for attempt in range(max_attempts):
        # Get the flow builds
        builds_response = await client.get(
            f"/api/v1/monitor/builds?flow_id={flow['id']}", 
            headers=headers
        )
        
        if builds_response.status_code == 200:
            builds = builds_response.json().get("vertex_builds", {})
            # Check if builds are complete
            all_valid = True
            for node_id, build_list in builds.items():
                if not build_list or build_list[0].get("valid") is not True:
                    all_valid = False
                    break
            
            if all_valid and builds:
                print(f"Flow builds completed successfully after {attempt+1} attempts")
                break
        
        # Wait before polling again
        if attempt < max_attempts - 1:
            print(f"Waiting for flow builds to complete (attempt {attempt+1}/{max_attempts})...")
            await asyncio.sleep(1)
    else:
        print("Warning: Flow builds polling timed out, proceeding anyway")
    
    return flow, headers

@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_non_streaming(
    client: AsyncClient, created_api_key
):
    """Test the OpenAI-compatible non-streaming responses endpoint directly."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)
    
    # Now test the OpenAI-compatible endpoint
    payload = {
        "model": flow["id"],
        "input": "Hello, Langflow!",
        "stream": False
    }
    
    # Make the request
    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content}")
    
    # Handle potential errors
    if response.status_code != 200:
        print(f"Error response: {response.content}")
        pytest.fail(f"Request failed with status {response.status_code}")
    
    try:
        data = response.json()
        if "error" in data:
            print(f"Error in response: {data['error']}")
            # Don't fail immediately, print more details for debugging
            print(f"Full error details: {data}")
            pytest.fail(f"Error in response: {data['error'].get('message', 'Unknown error')}")
        
        # Validate the response
        assert "id" in data
        assert "output" in data
    except Exception as e:
        print(f"Exception parsing response: {e}")
        pytest.fail(f"Failed to parse response: {e}")


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_streaming(
    client: AsyncClient, created_api_key
):
    """Test the OpenAI-compatible streaming responses endpoint directly."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)
    
    # Now test the OpenAI-compatible streaming endpoint
    payload = {
        "model": flow["id"],
        "input": "Hello, stream!",
        "stream": True
    }
    
    # Make the request
    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    print(f"Response status: {response.status_code}")
    
    # Handle potential errors
    if response.status_code != 200:
        print(f"Error response: {response.content}")
        pytest.fail(f"Request failed with status {response.status_code}")
    
    # For streaming, we should get a stream of server-sent events
    content = await response.aread()
    text_content = content.decode("utf-8")
    print(f"Response content (first 200 chars): {text_content[:200]}")
    
    # Check that we got some SSE data events
    assert "data:" in text_content
    
    # Parse the events to validate structure
    events = text_content.strip().split("\n\n")
    data_events = [event for event in events if event.startswith("data:")]
    
    # Ensure we received at least one data event
    assert data_events, "No streaming events were received"
    
    # Parse the first and last events to check their structure
    first_event = json.loads(data_events[0].replace("data: ", ""))
    last_event = json.loads(data_events[-1].replace("data: ", ""))
    
    # Verify event structure
    assert "delta" in first_event
    assert "delta" in last_event
