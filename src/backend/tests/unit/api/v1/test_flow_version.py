"""Tests for the Flow Versions API endpoints.

Tests cover:
- Creating snapshots
- Listing version entries
- Getting a single version entry with full data
- Activating a version (auto-snapshot, overwrite)
- Deleting version entries
- Edge cases: empty versions, nonexistent IDs, cross-user isolation
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


async def _create_flow(client: AsyncClient, headers: dict, name: str = "version-test-flow") -> dict:
    """Create a minimal flow and return the JSON response."""
    payload = {
        "name": name,
        "description": "flow for version tests",
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _create_snapshot(client: AsyncClient, headers: dict, flow_id: str, description: str | None = None) -> dict:
    """POST a snapshot and return the JSON response."""
    body = {"description": description} if description else {}
    resp = await client.post(f"api/v1/flows/{flow_id}/versions/", json=body, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _list_versions(client: AsyncClient, headers: dict, flow_id: str) -> list[dict]:
    resp = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "entries" in body
    assert "max_entries" in body
    return body["entries"]


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


async def test_list_versions_empty(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    entries = await _list_versions(client, logged_in_headers, flow["id"])
    assert entries == []


async def test_list_versions_response_includes_max_entries(client: AsyncClient, logged_in_headers, monkeypatch):
    """The list endpoint should return max_entries from settings."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 25)

    flow = await _create_flow(client, logged_in_headers)
    await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert body["max_entries"] == 25
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) == 1


async def test_list_versions_returns_entries_newest_first(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    await _create_snapshot(client, logged_in_headers, flow["id"], description="first")
    await _create_snapshot(client, logged_in_headers, flow["id"], description="second")
    await _create_snapshot(client, logged_in_headers, flow["id"], description="third")

    entries = await _list_versions(client, logged_in_headers, flow["id"])
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


async def test_get_single_version_entry_includes_data(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await client.get(f"api/v1/flows/{flow['id']}/versions/{snap['id']}", headers=logged_in_headers)
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
    r1 = await client.get(f"api/v1/flows/{flow['id']}/versions/{s1['id']}", headers=logged_in_headers)
    r2 = await client.get(f"api/v1/flows/{flow['id']}/versions/{s2['id']}", headers=logged_in_headers)

    assert r1.json()["data"] == {"nodes": [], "edges": []}
    assert r2.json()["data"] == new_data


async def test_delete_version_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await client.delete(f"api/v1/flows/{flow['id']}/versions/{snap['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    entries = await _list_versions(client, logged_in_headers, flow["id"])
    assert len(entries) == 0


# ---------------------------------------------------------------------------
# Activate version
# ---------------------------------------------------------------------------


async def test_activate_version_overwrites_flow_data(client: AsyncClient, logged_in_headers):
    """Activating a saved version should replace the current flow.data."""
    flow = await _create_flow(client, logged_in_headers)
    original_data = flow["data"]  # {"nodes": [], "edges": []}

    # Snapshot the original state
    snap = await _create_snapshot(client, logged_in_headers, flow["id"], description="v1 original")

    # Modify the flow
    modified_data = {"nodes": [{"id": "added-node"}], "edges": []}
    await _patch_flow_data(client, logged_in_headers, flow["id"], modified_data)

    # Activate the old snapshot
    resp = await client.post(f"api/v1/flows/{flow['id']}/versions/{snap['id']}/activate", headers=logged_in_headers)
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
    await client.post(f"api/v1/flows/{flow['id']}/versions/{snap['id']}/activate", headers=logged_in_headers)

    entries = await _list_versions(client, logged_in_headers, flow["id"])
    # 1 manual snapshot + 1 auto-snapshot = 2
    assert len(entries) == 2

    auto_snap = next(e for e in entries if "Auto-saved" in (e["description"] or ""))
    assert auto_snap is not None


async def test_activate_skips_auto_snapshot_when_save_draft_false(client: AsyncClient, logged_in_headers):
    """Activation with save_draft=false should NOT create an auto-snapshot."""
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    # Modify flow so we can verify the draft was NOT saved
    await _patch_flow_data(client, logged_in_headers, flow["id"], {"nodes": [{"id": "x"}], "edges": []})

    # Activate with save_draft=false
    resp = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{snap['id']}/activate",
        params={"save_draft": False},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK

    entries = await _list_versions(client, logged_in_headers, flow["id"])
    # Only the 1 manual snapshot — no auto-snapshot created
    assert len(entries) == 1
    assert not any("Auto-saved" in (e["description"] or "") for e in entries)


# ---------------------------------------------------------------------------
# Cascade deletion
# ---------------------------------------------------------------------------


async def test_deleting_flow_cascades_to_versions(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await _create_snapshot(client, logged_in_headers, flow["id"])

    # Delete the flow
    resp = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK

    # Versions endpoint for the deleted flow should 404
    resp = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------


async def test_get_versions_for_nonexistent_flow(client: AsyncClient, logged_in_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{fake_id}/versions/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_nonexistent_version_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{flow['id']}/versions/{fake_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_activate_nonexistent_version_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(f"api/v1/flows/{flow['id']}/versions/{fake_id}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_nonexistent_version_entry(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.delete(f"api/v1/flows/{flow['id']}/versions/{fake_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_activate_entry_belonging_to_different_flow(client: AsyncClient, logged_in_headers):
    """A version entry from flow A should not be activatable on flow B."""
    flow_a = await _create_flow(client, logged_in_headers, name="flow-a")
    flow_b = await _create_flow(client, logged_in_headers, name="flow-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    # Try to activate snap_a on flow_b
    resp = await client.post(f"api/v1/flows/{flow_b['id']}/versions/{snap_a['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_entry_belonging_to_different_flow(client: AsyncClient, logged_in_headers):
    """A version entry from flow A should not be deletable via flow B's endpoint."""
    flow_a = await _create_flow(client, logged_in_headers, name="flow-a-del")
    flow_b = await _create_flow(client, logged_in_headers, name="flow-b-del")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    resp = await client.delete(f"api/v1/flows/{flow_b['id']}/versions/{snap_a['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_unauthenticated_request_is_rejected(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"api/v1/flows/{fake_id}/versions/")
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


async def test_list_versions_pagination(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    # Create 5 snapshots
    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow["id"], description=f"snap-{i}")

    # Fetch with limit=2
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"limit": 2, "offset": 0},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    page1 = resp.json()["entries"]
    assert len(page1) == 2
    assert page1[0]["version_number"] == 5  # newest first
    assert page1[1]["version_number"] == 4

    # Second page
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"limit": 2, "offset": 2},
        headers=logged_in_headers,
    )
    page2 = resp.json()["entries"]
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
    resp = await client.post(f"api/v1/flows/{flow_id}/versions/{v1['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    activated_flow = resp.json()
    assert activated_flow["data"] == initial_data

    # 7. Verify versions now has 3 entries: v1, v2, + auto-snapshot (v3)
    entries = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries) == 3

    # 8. The auto-snapshot should contain data_v3
    auto = next(e for e in entries if "Auto-saved" in (e["description"] or ""))
    auto_full = await client.get(f"api/v1/flows/{flow_id}/versions/{auto['id']}", headers=logged_in_headers)
    assert auto_full.json()["data"] == data_v3

    # 9. Activate v2
    resp2 = await client.post(f"api/v1/flows/{flow_id}/versions/{v2['id']}/activate", headers=logged_in_headers)
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
        "name": "complex-version-test",
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
        f"api/v1/flows/{flow_id}/versions/{snap['id']}/activate", headers=logged_in_headers
    )
    assert activate_resp.status_code == status.HTTP_200_OK
    restored = activate_resp.json()

    assert restored["data"] == complex_data


async def test_snapshot_preserves_full_node_metadata(client: AsyncClient, logged_in_headers):
    """Verify that node IDs, positions, and edge handles survive snapshot.

    Note: the GET endpoint strips API keys server-side, so template password
    field values will be None.  This test focuses on structural preservation
    (IDs, positions, edge count) rather than exact template value equality.
    """
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
    full = await client.get(f"api/v1/flows/{flow['id']}/versions/{snap['id']}", headers=logged_in_headers)
    snapshot_data = full.json()["data"]

    assert len(snapshot_data["nodes"]) == len(complex_data["nodes"])
    assert len(snapshot_data["edges"]) == len(complex_data["edges"])

    for i, original_node in enumerate(complex_data["nodes"]):
        snap_node = snapshot_data["nodes"][i]
        assert snap_node["id"] == original_node["id"]
        assert snap_node.get("position") == original_node.get("position")


# ---------------------------------------------------------------------------
# Version limit enforcement
# ---------------------------------------------------------------------------


async def test_version_limit_enforcement(client: AsyncClient, logged_in_headers, monkeypatch):
    """Creating snapshots beyond the configured limit prunes the oldest entries."""
    # Set a small limit for testing
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 3)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Create 5 snapshots — limit is 3, so oldest 2 should be pruned
    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    entries = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries) == 3


async def test_version_limit_keeps_newest(client: AsyncClient, logged_in_headers, monkeypatch):
    """After pruning, the remaining entries should be the most recent by version_number."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 3)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    entries = await _list_versions(client, logged_in_headers, flow_id)
    version_numbers = [e["version_number"] for e in entries]
    # Should have versions 5, 4, 3 (newest first) — versions 1 and 2 were pruned
    assert version_numbers == [5, 4, 3]


async def test_pruning_deletes_oldest_by_data_content(client: AsyncClient, logged_in_headers, monkeypatch):
    """Verify that pruned entries are truly the oldest by checking surviving data content."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 2)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Create 3 snapshots, each with distinct flow data so we can verify which survived.
    for i in range(3):
        data = {"nodes": [{"id": f"node-from-snap-{i}"}], "edges": []}
        await _patch_flow_data(client, logged_in_headers, flow_id, data)
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    # Only the 2 newest should survive (snap-1 and snap-2); snap-0 should be pruned.
    entries = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries) == 2
    assert entries[0]["description"] == "snap-2"
    assert entries[1]["description"] == "snap-1"

    # Fetch full data for each survivor and confirm it matches the expected snapshot data.
    for entry, expected_idx in zip(entries, [2, 1], strict=False):
        resp = await client.get(
            f"api/v1/flows/{flow_id}/versions/{entry['id']}",
            headers=logged_in_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["nodes"][0]["id"] == f"node-from-snap-{expected_idx}"


async def test_lowered_limit_prunes_excess_on_next_snapshot(client: AsyncClient, logged_in_headers, monkeypatch):
    """Lowering the limit after entries exist should prune excess on the next snapshot."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings

    # Start with a generous limit and create 5 snapshots.
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 10)
    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    for i in range(5):
        await _create_snapshot(client, logged_in_headers, flow_id, description=f"snap-{i}")

    entries = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries) == 5

    # Now lower the limit to 2 — existing entries remain untouched until next snapshot.
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 2)

    entries_before = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries_before) == 5  # Still 5 — no pruning yet

    # Create one more snapshot — should trigger pruning down to 2.
    await _create_snapshot(client, logged_in_headers, flow_id, description="after-limit-change")

    entries_after = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries_after) == 2

    # The two survivors should be the newest: "after-limit-change" and "snap-4"
    assert entries_after[0]["description"] == "after-limit-change"
    assert entries_after[1]["description"] == "snap-4"


# ---------------------------------------------------------------------------
# Activate version with null data
# ---------------------------------------------------------------------------


async def test_activate_version_with_null_data(client: AsyncClient, logged_in_headers):
    """Activating a version whose data is None should return 400."""
    from uuid import UUID

    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.deps import session_scope
    from sqlmodel import select

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    snap = await _create_snapshot(client, logged_in_headers, flow_id)

    # Manually set the snapshot's data to None in the DB
    async with session_scope() as session:
        result = await session.exec(select(FlowVersion).where(FlowVersion.id == UUID(snap["id"])))
        entry = result.first()
        if entry:
            entry.data = None
            session.add(entry)

    resp = await client.post(f"api/v1/flows/{flow_id}/versions/{snap['id']}/activate", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "no data" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


async def test_version_entry_scoped_to_flow(client: AsyncClient, logged_in_headers):
    """Getting a version entry via the wrong flow's endpoint should 404."""
    flow_a = await _create_flow(client, logged_in_headers, name="scope-a")
    flow_b = await _create_flow(client, logged_in_headers, name="scope-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    # Try to access snap_a through flow_b's endpoint
    resp = await client.get(f"api/v1/flows/{flow_b['id']}/versions/{snap_a['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Edge case: limit boundary values
# ---------------------------------------------------------------------------


async def test_list_versions_limit_of_one(client: AsyncClient, logged_in_headers):
    """Limit=1 should return exactly one entry."""
    flow = await _create_flow(client, logged_in_headers)
    for i in range(3):
        await _create_snapshot(client, logged_in_headers, flow["id"], description=f"s-{i}")

    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"limit": 1},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()["entries"]) == 1
    assert resp.json()["entries"][0]["version_number"] == 3  # newest


async def test_list_versions_invalid_limit_zero(client: AsyncClient, logged_in_headers):
    """Limit=0 should be rejected by validation (ge=1)."""
    flow = await _create_flow(client, logged_in_headers)
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"limit": 0},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_list_versions_limit_exceeds_max(client: AsyncClient, logged_in_headers):
    """Limit > 100 should be rejected by validation (le=100)."""
    flow = await _create_flow(client, logged_in_headers)
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/",
        params={"limit": 101},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_get_single_entry_strips_api_keys(client: AsyncClient, logged_in_headers):
    """GET /versions/{id} should strip API keys from the returned data.

    The single-entry endpoint is used by the frontend for previewing and
    per-version export. API keys are stripped server-side to prevent leakage
    through the preview path, matching the export endpoint's behaviour.
    """
    api_key_data = {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "value": "sk-secret-99999",
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
        "name": "single-entry-api-key-test",
        "description": "test",
        "data": api_key_data,
        "is_component": False,
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_201_CREATED
    flow = resp.json()

    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    # Fetch the single entry — API key should be stripped (value set to None)
    resp = await client.get(
        f"api/v1/flows/{flow['id']}/versions/{snap['id']}",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    entry_data = resp.json()["data"]
    template = entry_data["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] is None


async def test_create_snapshot_rejects_long_description(client: AsyncClient, logged_in_headers):
    """POST with description > 500 chars should be rejected with 422."""
    flow = await _create_flow(client, logged_in_headers)
    long_description = "x" * 501

    resp = await client.post(
        f"api/v1/flows/{flow['id']}/versions/",
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
        f"api/v1/flows/{flow_id}/versions/{snap['id']}/activate",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    restored = resp.json()
    assert restored["data"] == deep_data


async def test_version_number_is_always_positive(client: AsyncClient, logged_in_headers):
    """get_next_version_number always returns >= 1, even for a brand-new flow."""
    from langflow.services.database.models.flow_version.crud import get_next_version_number
    from langflow.services.deps import session_scope

    flow = await _create_flow(client, logged_in_headers)

    async with session_scope() as session:
        from uuid import UUID

        next_ver = await get_next_version_number(session, UUID(flow["id"]))
        assert next_ver >= 1

    # After creating a snapshot, next version should still be >= 1
    await _create_snapshot(client, logged_in_headers, flow["id"])
    async with session_scope() as session:
        next_ver = await get_next_version_number(session, UUID(flow["id"]))
        assert next_ver >= 1
        assert next_ver == 2


async def test_rapid_snapshots_with_low_limit(client: AsyncClient, logged_in_headers, monkeypatch):
    """Creating many snapshots rapidly with a low limit should work without errors."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "max_flow_version_entries_per_flow", 2)

    flow = await _create_flow(client, logged_in_headers)
    flow_id = flow["id"]

    # Create 5 snapshots in quick succession
    for i in range(5):
        resp = await client.post(
            f"api/v1/flows/{flow_id}/versions/",
            json={"description": f"rapid-{i}"},
            headers=logged_in_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED

    # Should have exactly 2 entries (the limit)
    entries = await _list_versions(client, logged_in_headers, flow_id)
    assert len(entries) == 2
    # The newest ones should survive
    assert entries[0]["version_number"] == 5
    assert entries[1]["version_number"] == 4
