"""Test error propagation in OpenAI-compatible streaming API."""

import json

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_openai_streaming_error_propagation(client: AsyncClient, created_api_key):
    """Test that errors are properly propagated in OpenAI-compatible streaming format.
    
    This test verifies the fix for the bug where error events were not being
    propagated to clients using the OpenAI SDK. The fix ensures errors are sent
    as content chunks with finish_reason="error" instead of custom error events.
    """
    # Create a flow that will generate an error
    # For this test, we'll use an invalid flow ID which should trigger an error
    invalid_flow_id = "00000000-0000-0000-0000-000000000000"
    
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "model": invalid_flow_id,
        "input": "test input",
        "stream": True,
    }
    
    response = await client.post(
        "api/v1/responses",
        json=payload,
        headers=headers,
    )
    
    # Should return 200 even for errors in streaming mode
    assert response.status_code == 200
    
    # Parse the streaming response
    chunks = []
    error_found = False
    finish_reason_error = False
    
    for line in response.text.split("\n"):
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            data_str = line[6:]  # Remove "data: " prefix
            try:
                chunk_data = json.loads(data_str)
                chunks.append(chunk_data)
                
                # Check if this is an error chunk
                if chunk_data.get("status") == "failed":
                    error_found = True
                    
                # Check if finish_reason is "error"
                if chunk_data.get("finish_reason") == "error":
                    finish_reason_error = True
                    
                # Check if error message is in content
                delta = chunk_data.get("delta", {})
                content = delta.get("content", "")
                if content and "Error:" in content:
                    error_found = True
                    
            except json.JSONDecodeError:
                pass
    
    # Verify that error was properly propagated
    assert error_found, "Error should be present in streaming response"
    assert finish_reason_error, "finish_reason should be 'error' for error chunks"
    assert len(chunks) > 0, "Should have received at least one chunk"
    
    # Verify chunk format is OpenAI-compatible
    for chunk in chunks:
        assert "id" in chunk, "Chunk should have 'id' field"
        assert "object" in chunk, "Chunk should have 'object' field"
        assert chunk.get("object") == "response.chunk", "Object should be 'response.chunk'"
        assert "created" in chunk, "Chunk should have 'created' field"
        assert "model" in chunk, "Chunk should have 'model' field"
        assert "delta" in chunk, "Chunk should have 'delta' field"


@pytest.mark.integration
async def test_openai_streaming_success_finish_reason(client: AsyncClient, created_api_key, simple_api_test):
    """Test that successful streaming responses include finish_reason='stop'."""
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "model": str(simple_api_test.id),
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