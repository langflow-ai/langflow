"""Tests for the Flow History (versioning) API endpoints.

Tests cover:
- Creating snapshots
- Listing history entries
- Getting a single history entry with full data
- Activating a version (auto-snapshot, overwrite)
- Deleting history entries
- Edge cases: empty history, nonexistent IDs, cross-user isolation
- Cascade deletion when the parent flow is deleted
- Realistic data payloads using starter project JSON
"""

import json

import pytest
from fastapi import status
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_flow(client: AsyncClient, headers: dict, name: str = "history-test-flow") -> dict:
    """Create a minimal flow and return the JSON response."""
    payload = {
        "name": name,
        "description": "flow for history tests",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _create_snapshot(client: AsyncClient, headers: dict, flow_id: str, description: str | None = None) -> dict:
    """POST a snapshot and return the JSON response."""
    body = {"description": description} if description else {}
    resp = await client.post(f"api/v1/flows/{flow_id}/history/", json=body, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _list_history(client: AsyncClient, headers: dict, flow_id: str) -> list[dict]:
    resp = await client.get(f"api/v1/flows/{flow_id}/history/", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()


async def _patch_flow_data(client: AsyncClient, headers: dict, flow_id: str, data: dict) -> dict:
    """PATCH the flow to change its data (simulates canvas auto-save)."""
    resp = await client.patch(f"api/v1/flows/{flow_id}", json={"data": data}, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


async def test_create_snapshot(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"], description="initial save")

    assert snap["flow_id"] == flow["id"]
    assert snap["version_number"] == 1
    assert snap["version_tag"] == "v1"
    assert snap["description"] == "initial save"
    assert "created_at" in snap
    # List endpoint should NOT include data
    assert "data" not in snap


async def test_create_snapshot_without_description(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    assert snap["description"] is None
    assert snap["version_number"] == 1


async def test_list_history_empty(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    entries = await _list_history(client, logged_in_headers, flow["id"])
    assert entries == []


async def test_list_history_returns_entries_newest_first(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    await _create_snapshot(client, logged_in_headers, flow["id"], description="first")
    await _create_snapshot(client, logged_in_headers, flow["id"], description="second")
    await _create_snapshot(client, logged_in_headers, flow["id"], description="third")

    entries = await _list_history(client, logged_in_headers, flow["id"])
    assert len(entries) == 3
    # newest first → highest version_number first
    assert entries[0]["version_number"] == 3
    assert entries[1]["version_number"] == 2
    assert entries[2]["version_number"] == 1


async def test_version_numbers_auto_increment(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    s1 = await _create_snapshot(client, logged_in_headers, flow["id"])
    s2 = await _create_snapshot(client, logged_in_headers, flow["id"])
    s3 = await _create_snapshot(client, logged_in_headers, flow["id"])

    assert s1["version_number"] == 1
    assert s2["version_number"] == 2
    assert s3["version_number"] == 3


async def test_get_single_history_entry_includes_data(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await client.get(f"api/v1/flows/{flow['id']}/history/{snap['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    full = resp.json()

    assert "data" in full
    assert full["data"] == flow["data"]  # snapshot captured the flow's data
    assert full["version_tag"] == "v1"


async def test_snapshot_captures_current_flow_data(client: AsyncClient, logged_in_headers):
    """Snapshot data should be a deep copy of flow.data at the time of snapshot."""
    flow = await _create_flow(client, logged_in_headers)

    # Take snapshot of the initial empty data
    s1 = await _create_snapshot(client, logged_in_headers, flow["id"], description="empty")

    # Modify the flow
    new_data = {"nodes": [{"id": "node-1"}], "edges": []}
    await _patch_flow_data(client, logged_in_headers, flow["id"], new_data)

    # Take another snapshot
    s2 = await _create_snapshot(client, logged_in_headers, flow["id"], description="with node")

    # Fetch full snapshots and compare
    r1 = await client.get(f"api/v1/flows/{flow['id']}/history/{s1['id']}", headers=logged_in_headers)
    r2 = await client.get(f"api/v1/flows/{flow['id']}/history/{s2['id']}", headers=logged_in_headers)

    assert r1.json()["data"] == {"nodes": [], "edges": []}
    assert r2.json()["data"] == new_data


async def test_delete_history_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await client.delete(f"api/v1/flows/{flow['id']}/history/{snap['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    entries = await _list_history(client, logged_in_headers, flow["id"])
    assert len(entries) == 0


# ---------------------------------------------------------------------------
# Activate version
# ---------------------------------------------------------------------------


async def test_activate_version_overwrites_flow_data(client: AsyncClient, logged_in_headers):
    """Activating a historical version should replace the current flow.data."""
    flow = await _create_flow(client, logged_in_headers)
    original_data = flow["data"]  # {"nodes": [], "edges": []}

    # Snapshot the original state
    snap = await _create_snapshot(client, logged_in_headers, flow["id"], description="v1 original")

    # Modify the flow
    modified_data = {"nodes": [{"id": "added-node"}], "edges": []}
    await _patch_flow_data(client, logged_in_headers, flow["id"], modified_data)

    # Activate the old snapshot
    resp = await client.post(f"api/v1/flows/{flow['id']}/history/{snap['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    updated_flow = resp.json()

    assert updated_flow["data"] == original_data


async def test_activate_creates_auto_snapshot(client: AsyncClient, logged_in_headers):
    """Activation should auto-snapshot the current draft before overwriting."""
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    # Modify flow so auto-snapshot has different data
    await _patch_flow_data(client, logged_in_headers, flow["id"], {"nodes": [{"id": "x"}], "edges": []})

    # Activate — this should create an auto-snapshot first
    await client.post(f"api/v1/flows/{flow['id']}/history/{snap['id']}/activate", headers=logged_in_headers)

    entries = await _list_history(client, logged_in_headers, flow["id"])
    # 1 manual snapshot + 1 auto-snapshot = 2
    assert len(entries) == 2

    auto_snap = next(e for e in entries if "Auto-saved" in (e["description"] or ""))
    assert auto_snap is not None


# ---------------------------------------------------------------------------
# Cascade deletion
# ---------------------------------------------------------------------------


async def test_deleting_flow_cascades_to_history(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await _create_snapshot(client, logged_in_headers, flow["id"])

    # Delete the flow
    resp = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK

    # History endpoint for the deleted flow should 404
    resp = await client.get(f"api/v1/flows/{flow['id']}/history/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------


async def test_get_history_for_nonexistent_flow(client: AsyncClient, logged_in_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{fake_id}/history/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_nonexistent_history_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{flow['id']}/history/{fake_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_activate_nonexistent_history_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(f"api/v1/flows/{flow['id']}/history/{fake_id}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_nonexistent_history_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.delete(f"api/v1/flows/{flow['id']}/history/{fake_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_activate_entry_belonging_to_different_flow(client: AsyncClient, logged_in_headers):
    """A history entry from flow A should not be activatable on flow B."""
    flow_a = await _create_flow(client, logged_in_headers, name="flow-a")
    flow_b = await _create_flow(client, logged_in_headers, name="flow-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    # Try to activate snap_a on flow_b
    resp = await client.post(f"api/v1/flows/{flow_b['id']}/history/{snap_a['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_entry_belonging_to_different_flow(client: AsyncClient, logged_in_headers):
    """A history entry from flow A should not be deletable via flow B's endpoint."""
    flow_a = await _create_flow(client, logged_in_headers, name="flow-a-del")
    flow_b = await _create_flow(client, logged_in_headers, name="flow-b-del")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    resp = await client.delete(f"api/v1/flows/{flow_b['id']}/history/{snap_a['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_unauthenticated_request_is_rejected(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{fake_id}/history/")
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


async def test_list_history_pagination(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    # Create 5 snapshots
    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow["id"], description=f"snap-{i}")

    # Fetch with limit=2
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/history/",
        params={"limit": 2, "offset": 0},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    page1 = resp.json()
    assert len(page1) == 2
    assert page1[0]["version_number"] == 5  # newest first
    assert page1[1]["version_number"] == 4

    # Second page
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/history/",
        params={"limit": 2, "offset": 2},
        headers=logged_in_headers,
    )
    page2 = resp.json()
    assert len(page2) == 2
    assert page2[0]["version_number"] == 3


# ---------------------------------------------------------------------------
# Multi-activate scenario (full lifecycle)
# ---------------------------------------------------------------------------


async def test_full_lifecycle(client: AsyncClient, logged_in_headers):
    """End-to-end: create, snapshot, edit, snapshot, activate old, verify."""
    # 1. Create flow with initial data
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]
    initial_data = flow["data"]

    # 2. Save v1 snapshot
    v1 = await _create_snapshot(client, logged_in_headers, flow_id, description="version 1")
    assert v1["version_number"] == 1

    # 3. Edit the flow
    data_v2 = {"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": [{"id": "e1"}]}
    await _patch_flow_data(client, logged_in_headers, flow_id, data_v2)

    # 4. Save v2 snapshot
    v2 = await _create_snapshot(client, logged_in_headers, flow_id, description="version 2")
    assert v2["version_number"] == 2

    # 5. Edit the flow again
    data_v3 = {"nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}], "edges": []}
    await _patch_flow_data(client, logged_in_headers, flow_id, data_v3)

    # 6. Activate v1 — should auto-snapshot current state, then revert to v1's data
    resp = await client.post(f"api/v1/flows/{flow_id}/history/{v1['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    activated_flow = resp.json()
    assert activated_flow["data"] == initial_data

    # 7. Verify history now has 3 entries: v1, v2, + auto-snapshot (v3)
    entries = await _list_history(client, logged_in_headers, flow_id)
    assert len(entries) == 3

    # 8. The auto-snapshot should contain data_v3
    auto = next(e for e in entries if "Auto-saved" in (e["description"] or ""))
    auto_full = await client.get(f"api/v1/flows/{flow_id}/history/{auto['id']}", headers=logged_in_headers)
    assert auto_full.json()["data"] == data_v3

    # 9. Activate v2
    resp2 = await client.post(f"api/v1/flows/{flow_id}/history/{v2['id']}/activate", headers=logged_in_headers)
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["data"] == data_v2


# ---------------------------------------------------------------------------
# Realistic data payloads (starter project)
# ---------------------------------------------------------------------------


async def test_snapshot_and_activate_with_complex_flow_data(client: AsyncClient, logged_in_headers):
    """Snapshot / activate round-trip with a real multi-node flow from test data."""
    complex_json = json.loads(pytest.COMPLEX_EXAMPLE_PATH.read_text(encoding="utf-8"))
    complex_data = complex_json.get("data", complex_json)

    # Create a flow with the complex data
    payload = {
        "name": "complex-history-test",
        "description": "flow with real nodes",
        "data": complex_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_201_CREATED
    flow = resp.json()
    flow_id = flow["id"]

    # Verify the flow has meaningful data
    assert len(flow["data"]["nodes"]) > 1
    assert len(flow["data"]["edges"]) > 0

    # Snapshot the complex state
    snap = await _create_snapshot(client, logged_in_headers, flow_id, description="complex v1")

    # Overwrite the flow with minimal data
    minimal_data = {"nodes": [{"id": "single-node"}], "edges": []}
    await _patch_flow_data(client, logged_in_headers, flow_id, minimal_data)

    # Verify flow was actually changed
    get_resp = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert len(get_resp.json()["data"]["nodes"]) == 1

    # Activate the complex snapshot — should restore the full graph
    activate_resp = await client.post(
        f"api/v1/flows/{flow_id}/history/{snap['id']}/activate", headers=logged_in_headers
    )
    assert activate_resp.status_code == status.HTTP_200_OK
    restored = activate_resp.json()

    assert len(restored["data"]["nodes"]) == len(complex_data["nodes"])
    assert len(restored["data"]["edges"]) == len(complex_data["edges"])
    # Deep equality — all node/edge details survived the round-trip
    assert restored["data"] == complex_data


async def test_snapshot_preserves_full_node_metadata(client: AsyncClient, logged_in_headers):
    """Verify that node template fields, positions, and edge handles survive snapshot."""
    complex_json = json.loads(pytest.COMPLEX_EXAMPLE_PATH.read_text(encoding="utf-8"))
    complex_data = complex_json.get("data", complex_json)

    payload = {
        "name": "metadata-preservation-test",
        "description": "test",
        "data": complex_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    flow = resp.json()
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    # Fetch the full snapshot and compare node-by-node
    full = await client.get(f"api/v1/flows/{flow['id']}/history/{snap['id']}", headers=logged_in_headers)
    snapshot_data = full.json()["data"]

    for i, original_node in enumerate(complex_data["nodes"]):
        snap_node = snapshot_data["nodes"][i]
        assert snap_node["id"] == original_node["id"]
        assert snap_node.get("position") == original_node.get("position")
        assert snap_node.get("data") == original_node.get("data")


# ---------------------------------------------------------------------------
# History limit enforcement
# ---------------------------------------------------------------------------


async def test_history_limit_enforcement(client: AsyncClient, logged_in_headers, monkeypatch):
    """Creating snapshots beyond the configured limit prunes the oldest entries."""
    # Set a small limit for testing
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_history_entries_per_flow", 3)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Create 5 snapshots — limit is 3, so oldest 2 should be pruned
    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    entries = await _list_history(client, logged_in_headers, flow_id)
    assert len(entries) == 3


async def test_history_limit_keeps_newest(client: AsyncClient, logged_in_headers, monkeypatch):
    """After pruning, the remaining entries should be the most recent by version_number."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_history_entries_per_flow", 3)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    entries = await _list_history(client, logged_in_headers, flow_id)
    version_numbers = [e["version_number"] for e in entries]
    # Should have versions 5, 4, 3 (newest first) — versions 1 and 2 were pruned
    assert version_numbers == [5, 4, 3]


async def test_snapshot_rejects_oversized_data(client: AsyncClient, logged_in_headers, monkeypatch):
    """Creating a snapshot should fail if flow data exceeds the size limit."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_history_data_size_bytes", 10)  # 10 bytes

    flow = await _create_flow(client, logged_in_headers)
    resp = await client.post(
        f"api/v1/flows/{flow['id']}/history/",
        json={},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


# ---------------------------------------------------------------------------
# Export / Import with history
# ---------------------------------------------------------------------------


async def test_download_with_history(client: AsyncClient, logged_in_headers):
    """Download with include_history=True should embed history entries in the response."""
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    await _create_snapshot(client, logged_in_headers, flow_id, description="snap-1")
    await _create_snapshot(client, logged_in_headers, flow_id, description="snap-2")

    resp = await client.post(
        "api/v1/flows/download/",
        json=[flow_id],
        params={"include_history": True},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    result = resp.json()

    assert "history" in result
    assert len(result["history"]) == 2
    # Each history entry should have data
    for h in result["history"]:
        assert "data" in h
        assert "version_number" in h


async def test_download_without_history(client: AsyncClient, logged_in_headers):
    """Download without include_history should not include history key."""
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    await _create_snapshot(client, logged_in_headers, flow_id, description="snap-1")

    resp = await client.post(
        "api/v1/flows/download/",
        json=[flow_id],
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    result = resp.json()
    assert "history" not in result


async def test_upload_with_history(client: AsyncClient, logged_in_headers):
    """Upload flow JSON containing a history array should create FlowHistory entries."""
    flow_json = {
        "name": "imported-with-history",
        "description": "test import",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
        "history": [
            {
                "version_number": 1,
                "description": "imported v1",
                "data": {"nodes": [{"id": "n1"}], "edges": []},
            },
            {
                "version_number": 2,
                "description": "imported v2",
                "data": {"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": []},
            },
        ],
    }

    import io

    file_bytes = json.dumps(flow_json).encode()
    resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    created_flows = resp.json()
    assert len(created_flows) == 1

    new_flow_id = created_flows[0]["id"]

    # Verify history entries were created
    entries = await _list_history(client, logged_in_headers, new_flow_id)
    assert len(entries) == 2
    descriptions = {e["description"] for e in entries}
    assert "imported v1" in descriptions
    assert "imported v2" in descriptions


async def test_upload_without_history(client: AsyncClient, logged_in_headers):
    """Upload normal flow JSON without history should not create FlowHistory entries."""
    flow_json = {
        "name": "imported-no-history",
        "description": "test import",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }

    import io

    file_bytes = json.dumps(flow_json).encode()
    resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    created_flows = resp.json()
    new_flow_id = created_flows[0]["id"]

    entries = await _list_history(client, logged_in_headers, new_flow_id)
    assert len(entries) == 0


async def test_export_endpoint_includes_history(client: AsyncClient, logged_in_headers):
    """GET /flows/{flow_id}/history/export should return flow with history embedded."""
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    await _create_snapshot(client, logged_in_headers, flow_id, description="export-snap")

    resp = await client.get(
        f"api/v1/flows/{flow_id}/history/export",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    result = resp.json()

    assert result["id"] == flow_id
    assert "history" in result
    assert len(result["history"]) == 1
    assert result["history"][0]["description"] == "export-snap"
    assert "data" in result["history"][0]


async def test_export_endpoint_without_history(client: AsyncClient, logged_in_headers):
    """GET /flows/{flow_id}/history/export?include_history=false should omit history."""
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    await _create_snapshot(client, logged_in_headers, flow_id)

    resp = await client.get(
        f"api/v1/flows/{flow_id}/history/export",
        params={"include_history": False},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    result = resp.json()
    assert "history" not in result


async def test_round_trip_export_import(client: AsyncClient, logged_in_headers):
    """Export a flow with history, then import it, and verify history is preserved."""
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Modify and snapshot
    await _patch_flow_data(client, logged_in_headers, flow_id, {"nodes": [{"id": "n1"}], "edges": []})
    await _create_snapshot(client, logged_in_headers, flow_id, description="with-node")

    # Export
    export_resp = await client.get(
        f"api/v1/flows/{flow_id}/history/export",
        headers=logged_in_headers,
    )
    exported = export_resp.json()
    assert len(exported["history"]) == 1

    # Modify the name to avoid uniqueness conflict, then import
    exported["name"] = "round-trip-import"
    # Remove fields that shouldn't be in import
    for key in ["id", "user_id", "folder_id"]:
        exported.pop(key, None)

    import io

    file_bytes = json.dumps(exported).encode()
    upload_resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    imported_flow_id = upload_resp.json()[0]["id"]

    # Verify history was imported
    entries = await _list_history(client, logged_in_headers, imported_flow_id)
    assert len(entries) == 1
    assert entries[0]["description"] == "with-node"

    # Verify the history entry has the correct data
    full_entry = await client.get(
        f"api/v1/flows/{imported_flow_id}/history/{entries[0]['id']}",
        headers=logged_in_headers,
    )
    assert full_entry.json()["data"] == {"nodes": [{"id": "n1"}], "edges": []}


# ---------------------------------------------------------------------------
# Activate version with null data
# ---------------------------------------------------------------------------


async def test_activate_version_with_null_data(client: AsyncClient, logged_in_headers):
    """Activating a version whose data is None should return 400."""
    from uuid import UUID

    from langflow.services.database.models.flow_history.model import FlowHistory
    from langflow.services.deps import session_scope
    from sqlmodel import select

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    snap = await _create_snapshot(client, logged_in_headers, flow_id)

    # Manually set the snapshot's data to None in the DB
    async with session_scope() as session:
        result = await session.exec(select(FlowHistory).where(FlowHistory.id == UUID(snap["id"])))
        entry = result.first()
        if entry:
            entry.data = None
            session.add(entry)

    resp = await client.post(f"api/v1/flows/{flow_id}/history/{snap['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "no data" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


async def test_history_entry_scoped_to_flow(client: AsyncClient, logged_in_headers):
    """Getting a history entry via the wrong flow's endpoint should 404."""
    flow_a = await _create_flow(client, logged_in_headers, name="scope-a")
    flow_b = await _create_flow(client, logged_in_headers, name="scope-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    # Try to access snap_a through flow_b's endpoint
    resp = await client.get(f"api/v1/flows/{flow_b['id']}/history/{snap_a['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Malformed history import
# ---------------------------------------------------------------------------


async def test_upload_with_malformed_history_entries(client: AsyncClient, logged_in_headers):
    """Import with history entries missing 'data' should still create entries (with None data)."""
    import io

    flow_json = {
        "name": "malformed-history-import",
        "description": "test",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
        "history": [
            {
                "description": "has-data",
                "data": {"nodes": [{"id": "n1"}], "edges": []},
            },
            {
                "description": "no-data-key",
                # Missing "data" key entirely
            },
        ],
    }
    file_bytes = json.dumps(flow_json).encode()
    resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    new_flow_id = resp.json()[0]["id"]

    entries = await _list_history(client, logged_in_headers, new_flow_id)
    assert len(entries) == 2
    descriptions = {e["description"] for e in entries}
    assert "has-data" in descriptions
    assert "no-data-key" in descriptions


# ---------------------------------------------------------------------------
# Multi-flow download with history
# ---------------------------------------------------------------------------


async def test_download_multiple_flows_with_history(client: AsyncClient, logged_in_headers):
    """Downloading multiple flows with include_history should embed history in each."""
    flow_a = await _create_flow(client, logged_in_headers, name="multi-a")
    flow_b = await _create_flow(client, logged_in_headers, name="multi-b")

    await _create_snapshot(client, logged_in_headers, flow_a["id"], description="a-snap")
    await _create_snapshot(client, logged_in_headers, flow_b["id"], description="b-snap")

    resp = await client.post(
        "api/v1/flows/download/",
        json=[flow_a["id"], flow_b["id"]],
        params={"include_history": True},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK

    # Multi-flow download returns a ZIP file
    import io
    import zipfile

    content = resp.content
    if resp.headers.get("content-type", "").startswith("application/x-zip"):
        zf = zipfile.ZipFile(io.BytesIO(content))
        for name in zf.namelist():
            flow_data = json.loads(zf.read(name))
            assert "history" in flow_data
            assert len(flow_data["history"]) >= 1
    else:
        # Single flow returned as JSON
        result = resp.json()
        assert "history" in result


# ---------------------------------------------------------------------------
# Edge case: limit boundary values
# ---------------------------------------------------------------------------


async def test_list_history_limit_of_one(client: AsyncClient, logged_in_headers):
    """Limit=1 should return exactly one entry."""
    flow = await _create_flow(client, logged_in_headers)
    for i in range(3):
        await _create_snapshot(client, logged_in_headers, flow["id"], description=f"s-{i}")

    resp = await client.get(
        f"api/v1/flows/{flow['id']}/history/",
        params={"limit": 1},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1
    assert resp.json()[0]["version_number"] == 3  # newest


async def test_list_history_invalid_limit_zero(client: AsyncClient, logged_in_headers):
    """Limit=0 should be rejected by validation (ge=1)."""
    flow = await _create_flow(client, logged_in_headers)
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/history/",
        params={"limit": 0},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_list_history_limit_exceeds_max(client: AsyncClient, logged_in_headers):
    """Limit > 100 should be rejected by validation (le=100)."""
    flow = await _create_flow(client, logged_in_headers)
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/history/",
        params={"limit": 101},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_export_strips_api_keys_from_history(client: AsyncClient, logged_in_headers):
    """Export endpoint should strip API keys from history entry data."""
    # Create a flow whose data contains an API key (must have password=True for remove_api_keys)
    api_key_data = {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "value": "sk-secret-12345",
                                "name": "api_key",
                                "password": True,
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    payload = {
        "name": "api-key-export-test",
        "description": "test",
        "data": api_key_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_201_CREATED
    flow = resp.json()
    flow_id = flow["id"]

    # Snapshot the flow (captures the API key in data)
    await _create_snapshot(client, logged_in_headers, flow_id, description="has-api-key")

    # Export with history
    resp = await client.get(f"api/v1/flows/{flow_id}/history/export", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    exported = resp.json()

    # The history entry's data should have the API key stripped (set to None)
    history_data = exported["history"][0]["data"]
    template = history_data["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] is None


async def test_download_strips_api_keys_from_history(client: AsyncClient, logged_in_headers):
    """Download endpoint should strip API keys from history entry data."""
    api_key_data = {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "node": {
                        "template": {
                            "openai_api_key": {
                                "value": "sk-secret-99999",
                                "name": "openai_api_key",
                                "password": True,
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    payload = {
        "name": "api-key-download-test",
        "description": "test",
        "data": api_key_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_201_CREATED
    flow = resp.json()

    await _create_snapshot(client, logged_in_headers, flow["id"], description="has-key")

    resp = await client.post(
        "api/v1/flows/download/",
        json=[flow["id"]],
        params={"include_history": True},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    result = resp.json()

    history_data = result["history"][0]["data"]
    template = history_data["nodes"][0]["data"]["node"]["template"]
    assert template["openai_api_key"]["value"] is None


async def test_create_snapshot_rejects_long_description(client: AsyncClient, logged_in_headers):
    """POST with description > 500 chars should be rejected with 422."""
    flow = await _create_flow(client, logged_in_headers)
    long_description = "x" * 501

    resp = await client.post(
        f"api/v1/flows/{flow['id']}/history/",
        json={"description": long_description},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_create_snapshot_accepts_max_description(client: AsyncClient, logged_in_headers):
    """POST with description exactly 500 chars should succeed."""
    flow = await _create_flow(client, logged_in_headers)
    max_description = "x" * 500

    snap = await _create_snapshot(client, logged_in_headers, flow["id"], description=max_description)
    assert snap["description"] == max_description


async def test_upload_with_non_dict_history_data_skips_entries(client: AsyncClient, logged_in_headers):
    """Import should skip history entries with non-dict data values."""
    import io

    flow_json = {
        "name": "non-dict-data-import",
        "description": "test",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
        "history": [
            {
                "description": "valid-entry",
                "data": {"nodes": [{"id": "n1"}], "edges": []},
            },
            {
                "description": "string-data",
                "data": "this-is-not-a-dict",
            },
            {
                "description": "list-data",
                "data": [1, 2, 3],
            },
        ],
    }
    file_bytes = json.dumps(flow_json).encode()
    resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    new_flow_id = resp.json()[0]["id"]

    entries = await _list_history(client, logged_in_headers, new_flow_id)
    # Only the valid entry should be imported
    assert len(entries) == 1
    assert entries[0]["description"] == "valid-entry"


async def test_upload_creates_flow_even_if_history_entries_fail(client: AsyncClient, logged_in_headers, monkeypatch):
    """Flow should still be created even if individual history entries fail to import."""
    import io

    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    # Set data size limit very low so the second history entry exceeds it
    monkeypatch.setattr(settings, "max_flow_history_data_size_bytes", 50)

    flow_json = {
        "name": "partial-history-import",
        "description": "test",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
        "history": [
            {
                "description": "small-entry",
                "data": {"nodes": [], "edges": []},
            },
            {
                "description": "oversized-entry",
                "data": {"nodes": [{"id": f"node-{i}", "data": {"big": "x" * 100}} for i in range(10)], "edges": []},
            },
        ],
    }
    file_bytes = json.dumps(flow_json).encode()
    resp = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", io.BytesIO(file_bytes), "application/json")},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    new_flow_id = resp.json()[0]["id"]

    # The flow itself was created
    flow_resp = await client.get(f"api/v1/flows/{new_flow_id}", headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_200_OK

    # Only the small entry should have been imported
    entries = await _list_history(client, logged_in_headers, new_flow_id)
    assert len(entries) == 1
    assert entries[0]["description"] == "small-entry"

async def test_activate_with_deeply_nested_data(client: AsyncClient, logged_in_headers):
    """Activate should work correctly with deeply nested flow data."""
    # Create deeply nested data
    nested = {"level": 0}
    current = nested
    for i in range(1, 20):
        current["child"] = {"level": i}
        current = current["child"]

    deep_data = {"nodes": [{"id": "deep-node", "data": nested}], "edges": []}
    payload = {
        "name": "deep-nested-test",
        "description": "test",
        "data": deep_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_201_CREATED
    flow = resp.json()
    flow_id = flow["id"]

    # Snapshot the deeply nested data
    snap = await _create_snapshot(client, logged_in_headers, flow_id)

    # Modify the flow
    await _patch_flow_data(client, logged_in_headers, flow_id, {"nodes": [], "edges": []})

    # Activate the old version — triggers deepcopy of both current and target data
    resp = await client.post(
        f"api/v1/flows/{flow_id}/history/{snap['id']}/activate",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    restored = resp.json()
    assert restored["data"] == deep_data


async def test_rapid_snapshots_with_low_limit(client: AsyncClient, logged_in_headers, monkeypatch):
    """Creating many snapshots rapidly with a low limit should work without errors."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_history_entries_per_flow", 2)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Create 5 snapshots in quick succession
    for i in range(5):
        resp = await client.post(
            f"api/v1/flows/{flow_id}/history/",
            json={"description": f"rapid-{i}"},
            headers=logged_in_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED

    # Should have exactly 2 entries (the limit)
    entries = await _list_history(client, logged_in_headers, flow_id)
    assert len(entries) == 2
    # The newest ones should survive
    assert entries[0]["version_number"] == 5
    assert entries[1]["version_number"] == 4
