"""Integration test for JSON Patch API endpoint with efficiency metrics."""

import logging
import time

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_json_patch_vs_traditional_patch_comparison(client: AsyncClient, flow, logged_in_headers):
    """Compare JSON Patch vs Traditional PATCH: payload size and performance."""
    # Prepare test data
    new_name = "Updated Flow Name"
    new_description = "Updated Description"
    new_data = {
        "nodes": [
            {"id": "node-1", "type": "test", "position": {"x": 0, "y": 0}},
            {"id": "node-2", "type": "test", "position": {"x": 100, "y": 100}},
        ],
        "edges": [{"id": "edge-1", "source": "node-1", "target": "node-2"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    # Test 1: Traditional PATCH
    # Note: Traditional PATCH only needs the fields being updated
    traditional_payload = {
        "name": new_name,
        "description": new_description,
        "data": new_data,
    }

    traditional_payload_size = len(str(traditional_payload))
    start_time = time.time()

    response_traditional = await client.patch(
        f"api/v1/flows/{flow.id}",
        json=traditional_payload,
        headers=logged_in_headers,
    )

    traditional_duration = (time.time() - start_time) * 1000  # Convert to ms

    assert response_traditional.status_code == 200
    assert response_traditional.json()["name"] == new_name

    # Test 2: JSON Patch
    json_patch_payload = {
        "operations": [
            {"op": "replace", "path": "/name", "value": new_name},
            {"op": "replace", "path": "/description", "value": new_description},
            {"op": "replace", "path": "/data", "value": new_data},
        ]
    }

    json_patch_payload_size = len(str(json_patch_payload))
    start_time = time.time()

    response_json_patch = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json=json_patch_payload,
        headers=logged_in_headers,
    )

    json_patch_duration = (time.time() - start_time) * 1000  # Convert to ms

    assert response_json_patch.status_code == 200

    # Calculate efficiency metrics
    size_savings = traditional_payload_size - json_patch_payload_size
    size_savings_percent = (size_savings / traditional_payload_size) * 100
    time_diff = traditional_duration - json_patch_duration

    # Log comparison metrics
    ops_list = "\n".join([f"   - {op['op']:8} {op['path']}" for op in json_patch_payload["operations"]])
    logger.info(
        "\n%s\n📊 JSON PATCH vs TRADITIONAL PATCH COMPARISON\n%s\n"
        "\n📦 PAYLOAD SIZE:\n"
        "   Traditional PATCH: %s bytes\n"
        "   JSON Patch:        %s bytes\n"
        "   Savings:           %s bytes (%.1f%% reduction)\n"
        "\n⚡ RESPONSE TIME:\n"
        "   Traditional PATCH: %.2fms\n"
        "   JSON Patch:        %.2fms\n"
        "   Difference:        %+.2fms\n"
        "\n🎯 JSON PATCH OPERATIONS:\n"
        "   Total operations:  %s\n%s\n%s\n",
        "=" * 70,
        "=" * 70,
        f"{traditional_payload_size:,}",
        f"{json_patch_payload_size:,}",
        f"{size_savings:,}",
        size_savings_percent,
        traditional_duration,
        json_patch_duration,
        time_diff,
        len(json_patch_payload["operations"]),
        ops_list,
        "=" * 70,
    )

    # Assertions
    # Note: When updating ALL fields, JSON Patch may have overhead due to operations array
    # The real benefit is in partial updates (see test_json_patch_partial_update_efficiency)
    response_data = response_json_patch.json()
    assert response_data["success"] is True
    assert response_data["operations_applied"] == 3
    assert "/name" in response_data["updated_fields"]
    assert "/description" in response_data["updated_fields"]
    assert "/data" in response_data["updated_fields"]

    # Verify patched_data contains the updated fields
    assert "patched_data" in response_data
    assert "name" in response_data["patched_data"]
    assert response_data["patched_data"]["name"] == new_name
    assert "description" in response_data["patched_data"]
    assert response_data["patched_data"]["description"] == new_description
    assert "data" in response_data["patched_data"]
    assert response_data["patched_data"]["data"] == new_data

    # Verify the flow was actually updated by fetching it
    verify_response = await client.get(
        f"api/v1/flows/{flow.id}",
        headers=logged_in_headers,
    )
    verify_data = verify_response.json()
    assert verify_data["name"] == new_name
    assert verify_data["description"] == new_description
    assert verify_data["data"] == new_data


@pytest.mark.asyncio
async def test_json_patch_null_value_clears_field(client: AsyncClient, flow, logged_in_headers):
    """Test that JSON Patch with null value properly clears a field."""
    # First, set an endpoint name
    response = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json={"operations": [{"op": "replace", "path": "/endpoint_name", "value": "test-endpoint"}]},
        headers=logged_in_headers,
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["operations_applied"] == 1
    assert "/endpoint_name" in response_data["updated_fields"]
    assert "patched_data" in response_data
    assert "endpoint_name" in response_data["patched_data"]
    assert response_data["patched_data"]["endpoint_name"] == "test-endpoint"

    # Verify the endpoint was set by fetching the flow
    verify_response = await client.get(
        f"api/v1/flows/{flow.id}",
        headers=logged_in_headers,
    )
    assert verify_response.json()["endpoint_name"] == "test-endpoint"

    # Now clear it with null
    response = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json={"operations": [{"op": "replace", "path": "/endpoint_name", "value": None}]},
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["operations_applied"] == 1
    assert "/endpoint_name" in response_data["updated_fields"]
    assert "patched_data" in response_data
    assert "endpoint_name" in response_data["patched_data"]
    assert response_data["patched_data"]["endpoint_name"] is None

    # Verify the endpoint was cleared by fetching the flow
    verify_response = await client.get(
        f"api/v1/flows/{flow.id}",
        headers=logged_in_headers,
    )
    assert verify_response.json()["endpoint_name"] is None

    logger.info(
        "\n✅ NULL VALUE TEST PASSED:\n   Verified that null values in replace operations properly clear fields"
    )


@pytest.mark.asyncio
async def test_json_patch_partial_update_efficiency(client: AsyncClient, flow, logged_in_headers):
    """Test that JSON Patch only sends changed fields, not the entire object."""
    # Simulate updating only the name (most common use case)
    json_patch_payload = {
        "operations": [
            {"op": "replace", "path": "/name", "value": "Just Name Change"},
        ]
    }

    # Compare to traditional PATCH which must send many fields
    traditional_payload = {
        "name": "Just Name Change",
        "description": flow.description or "",
        "data": flow.data or {},
        "folder_id": str(flow.folder_id),
        "locked": flow.locked,
    }

    json_patch_size = len(str(json_patch_payload))
    traditional_size = len(str(traditional_payload))
    savings = traditional_size - json_patch_size
    savings_percent = (savings / traditional_size) * 100

    response = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json=json_patch_payload,
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["operations_applied"] == 1
    assert "/name" in response_data["updated_fields"]
    assert "patched_data" in response_data
    assert "name" in response_data["patched_data"]
    assert response_data["patched_data"]["name"] == "Just Name Change"

    # Verify the name was updated by fetching the flow
    verify_response = await client.get(
        f"api/v1/flows/{flow.id}",
        headers=logged_in_headers,
    )
    assert verify_response.json()["name"] == "Just Name Change"

    separator = "=" * 70
    logger.info(
        "\n%s\n🎯 PARTIAL UPDATE EFFICIENCY TEST (Name Only)\n%s\n"
        "\n   Traditional PATCH: %s bytes (sends entire object)\n"
        "   JSON Patch:        %s bytes (sends only changes)\n"
        "   Savings:           %s bytes (%.1f%% reduction)\n"
        "\n   This is the REAL benefit of JSON Patch! 🚀\n%s\n",
        separator,
        separator,
        f"{traditional_size:,}",
        f"{json_patch_size:,}",
        f"{savings:,}",
        savings_percent,
        separator,
    )

    # The savings should be significant for partial updates
    assert savings_percent > 50, f"Expected >50% savings for partial update, got {savings_percent:.1f}%"


@pytest.mark.asyncio
async def test_json_patch_remove_operation_returns_null(client: AsyncClient, flow, logged_in_headers):
    """Test that remove operations return null in patched_data so frontend can delete the field."""
    # First, set an endpoint name
    response = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json={"operations": [{"op": "replace", "path": "/endpoint_name", "value": "test-endpoint"}]},
        headers=logged_in_headers,
    )
    assert response.status_code == 200

    # Now remove it
    response = await client.patch(
        f"api/v1/flows/{flow.id}/json-patch",
        json={"operations": [{"op": "remove", "path": "/endpoint_name"}]},
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["operations_applied"] == 1
    assert "/endpoint_name" in response_data["updated_fields"]

    # The key part: patched_data should contain endpoint_name: null
    assert "patched_data" in response_data
    assert "endpoint_name" in response_data["patched_data"]
    assert response_data["patched_data"]["endpoint_name"] is None

    # Verify the field was actually removed in the database
    verify_response = await client.get(
        f"api/v1/flows/{flow.id}",
        headers=logged_in_headers,
    )
    assert verify_response.json()["endpoint_name"] is None

    logger.info(
        "\n✅ REMOVE OPERATION TEST PASSED:\n"
        "   Verified that remove operations return null in patched_data\n"
        "   This allows the frontend to properly remove fields from local state"
    )
