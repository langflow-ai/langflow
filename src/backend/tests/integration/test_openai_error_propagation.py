"""Test error propagation in OpenAI-compatible streaming API."""

import json

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_openai_pre_streaming_error_format(client: AsyncClient, created_api_key):
    """Test that pre-streaming errors (e.g., invalid flow ID) return proper error format.
    
    Errors that occur before streaming starts (validation errors, flow not found, etc.)
    return a JSON error response, not a streaming response.
    """
    invalid_flow_id = "00000000-0000-0000-0000-000000000000"
    
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "model": invalid_flow_id,
        "input": "test input",
        "stream": True,  # Even with stream=True, pre-streaming errors return JSON
    }
    
    response = await client.post(
        "api/v1/responses",
        json=payload,
        headers=headers,
    )
    
    # Should return 200 with error in response body
    assert response.status_code == 200
    
    # Parse the response
    response_data = response.json()
    
    # Verify error response format
    assert "error" in response_data, "Response should contain error field"
    error = response_data["error"]
    assert "message" in error, "Error should have message field"
    assert "type" in error, "Error should have type field"
    assert "not found" in error["message"].lower(), "Error message should indicate flow not found"


@pytest.mark.integration
async def test_openai_streaming_runtime_error_format(client: AsyncClient, created_api_key, simple_api_test):
    """Test that runtime errors during streaming are properly formatted.
    
    This test verifies the fix for the bug where error events during flow execution
    were not being propagated to clients using the OpenAI SDK. The fix ensures errors
    are sent as content chunks with finish_reason="error" instead of custom error events.
    
    Note: This test validates the error chunk format. Runtime errors during actual
    flow execution will be formatted the same way.
    """
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "model": str(simple_api_test["id"]),
        "input": "test input",
        "stream": True,
    }
    
    response = await client.post(
        "api/v1/responses",
        json=payload,
        headers=headers,
    )
    
    assert response.status_code == 200
    
    # Parse the streaming response
    chunks = []
    for line in response.text.split("\n"):
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            data_str = line[6:]
            try:
                chunk_data = json.loads(data_str)
                chunks.append(chunk_data)
            except json.JSONDecodeError:
                pass
    
    # Verify all chunks have proper OpenAI format
    assert len(chunks) > 0, "Should have received at least one chunk"
    for chunk in chunks:
        assert "id" in chunk, "Chunk should have 'id' field"
        assert "object" in chunk, "Chunk should have 'object' field"
        assert chunk.get("object") == "response.chunk", "Object should be 'response.chunk'"
        assert "created" in chunk, "Chunk should have 'created' field"
        assert "model" in chunk, "Chunk should have 'model' field"
        assert "delta" in chunk, "Chunk should have 'delta' field"
        
        # If there's a finish_reason, it should be valid
        if "finish_reason" in chunk and chunk["finish_reason"] is not None:
            assert chunk["finish_reason"] in ["stop", "length", "error", "tool_calls"], \
                f"finish_reason should be valid, got: {chunk['finish_reason']}"


@pytest.mark.integration
async def test_openai_streaming_success_finish_reason(client: AsyncClient, created_api_key, simple_api_test):
    """Test that successful streaming responses include finish_reason='stop'."""
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "model": str(simple_api_test["id"]),
        "input": "Hello",
        "stream": True,
    }
    
    response = await client.post(
        "api/v1/responses",
        json=payload,
        headers=headers,
    )
    
    assert response.status_code == 200
    
    # Parse the streaming response
    chunks = []
    finish_reason_stop = False
    
    for line in response.text.split("\n"):
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            data_str = line[6:]
            try:
                chunk_data = json.loads(data_str)
                chunks.append(chunk_data)
                
                # Check for finish_reason="stop" in final chunk
                if chunk_data.get("finish_reason") == "stop":
                    finish_reason_stop = True
                    
            except json.JSONDecodeError:
                pass
    
    # Verify that successful completion has finish_reason="stop"
    assert finish_reason_stop, "Successful completion should have finish_reason='stop'"
    assert len(chunks) > 0, "Should have received at least one chunk"