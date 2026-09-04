"""Tests for the flow version comparison endpoint.

Covers the two sides a diff can take (a stored version, or the live draft),
scoping and authorization, and the security property that motivates computing the
diff server-side at all: a rotated credential is reported as a change without
either value appearing in the response.
"""

import pytest
from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict, name: str = "diff-test-flow") -> dict:
    """Create a minimal flow and return the JSON response."""
    payload = {
        "name": name,
        "description": "flow for version diff tests",
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


async def _patch_flow_data(client: AsyncClient, headers: dict, flow_id: str, data: dict) -> dict:
    """PATCH the flow to change its data (simulates canvas auto-save)."""
    resp = await client.patch(f"api/v1/flows/{flow_id}", json={"data": data}, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()


async def _get_diff(client: AsyncClient, headers: dict, flow_id: str, version_id: str, against: str | None = None):
    params = {"against": against} if against is not None else None
    return await client.get(f"api/v1/flows/{flow_id}/versions/{version_id}/diff", headers=headers, params=params)


def _node(node_id: str, template: dict, display_name: str = "Node") -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {
            "id": node_id,
            "type": "Component",
            "node": {"display_name": display_name, "template": template},
        },
    }


def _flow_data(nodes: list | None = None, edges: list | None = None) -> dict:
    return {"nodes": nodes or [], "edges": edges or []}


def _text_template(value: str) -> dict:
    return {"_type": "Component", "prompt": {"name": "prompt", "type": "str", "value": value}}


async def test_diff_against_draft_reports_changes_made_since_the_snapshot(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("before"))]))
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("after"))]))

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"], against="draft")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["base"]["kind"] == "version"
    assert body["base"]["version_tag"] == "v1"
    assert body["target"]["kind"] == "draft"
    assert body["identical"] is False
    change = body["nodes"]["modified"][0]["field_changes"][0]
    assert change["before"] == "before"
    assert change["after"] == "after"


async def test_against_defaults_to_the_draft(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"])

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["target"]["kind"] == "draft"


async def test_diff_between_two_versions(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("v1"))]))
    first = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("v2"))]))
    second = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], first["id"], against=second["id"])

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["target"]["kind"] == "version"
    assert body["target"]["version_tag"] == "v2"
    change = body["nodes"]["modified"][0]["field_changes"][0]
    assert change["before"] == "v1"
    assert change["after"] == "v2"


async def test_comparing_a_version_with_itself_is_identical(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("same"))]))
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"], against=snap["id"])

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["identical"] is True
    assert body["summary"]["nodes_unchanged"] == 1


async def test_unknown_base_version_returns_404(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    missing = "00000000-0000-0000-0000-000000000000"

    resp = await _get_diff(client, logged_in_headers, flow["id"], missing)

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_unknown_target_version_returns_404(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])
    missing = "00000000-0000-0000-0000-000000000000"

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"], against=missing)

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_target_version_from_another_flow_returns_404(client: AsyncClient, logged_in_headers):
    """A version id is only meaningful within its own flow."""
    flow_a = await _create_flow(client, logged_in_headers, name="diff-scope-a")
    flow_b = await _create_flow(client, logged_in_headers, name="diff-scope-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])
    snap_b = await _create_snapshot(client, logged_in_headers, flow_b["id"])

    resp = await _get_diff(client, logged_in_headers, flow_a["id"], snap_a["id"], against=snap_b["id"])

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_base_version_from_another_flow_returns_404(client: AsyncClient, logged_in_headers):
    flow_a = await _create_flow(client, logged_in_headers, name="diff-base-a")
    flow_b = await _create_flow(client, logged_in_headers, name="diff-base-b")
    snap_a = await _create_snapshot(client, logged_in_headers, flow_a["id"])

    resp = await _get_diff(client, logged_in_headers, flow_b["id"], snap_a["id"])

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_malformed_against_value_returns_422(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"], against="not-a-uuid")

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_unauthenticated_request_is_rejected(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"

    resp = await client.get(f"api/v1/flows/{fake_id}/versions/{fake_id}/diff")

    assert resp.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


async def test_secret_values_never_appear_in_the_response(client: AsyncClient, logged_in_headers):
    """The reason this endpoint exists server-side.

    Both scrubbed values are None, so a client-side diff would report the
    rotation as "unchanged". The endpoint reports it as a redacted change and
    discloses neither value.
    """
    old_key = "sk-secret-99999"
    new_key = "sk-secret-11111"
    flow = await _create_flow(client, logged_in_headers)

    def key_template(value: str) -> dict:
        return {"_type": "Component", "api_key": {"name": "api_key", "password": True, "value": value}}

    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", key_template(old_key))]))
    first = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", key_template(new_key))]))
    second = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], first["id"], against=second["id"])

    assert resp.status_code == status.HTTP_200_OK
    assert old_key not in resp.text
    assert new_key not in resp.text

    body = resp.json()
    change = body["nodes"]["modified"][0]["field_changes"][0]
    assert change["name"] == "api_key"
    assert change["redacted"] is True
    assert "before" not in change
    assert "after" not in change
    assert body["summary"]["secrets_changed"] == 1


async def test_version_with_no_data_is_comparable(client: AsyncClient, logged_in_headers):
    """A snapshot of an empty flow is a legitimate comparison base, not a 400."""
    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(client, logged_in_headers, flow["id"], _flow_data([_node("n1", _text_template("new"))]))

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"], against="draft")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["summary"]["nodes_added"] == 1


async def test_diff_does_not_touch_deployment_attachments(client: AsyncClient, logged_in_headers, monkeypatch):
    """The diff is a read path and must never trigger a provider sync."""
    from langflow.api.v1 import flow_version as flow_version_module

    def _explode(*_args, **_kwargs):
        msg = "diff must not sync deployment attachments"
        raise AssertionError(msg)

    monkeypatch.setattr(flow_version_module, "sync_flow_version_attachments", _explode)

    flow = await _create_flow(client, logged_in_headers)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])

    resp = await _get_diff(client, logged_in_headers, flow["id"], snap["id"])

    assert resp.status_code == status.HTTP_200_OK
    assert "is_deployed" not in resp.text


async def test_edge_rewiring_is_reported_as_a_removal_and_an_addition(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    nodes = [_node("n1", _text_template("a")), _node("n2", _text_template("b")), _node("n3", _text_template("c"))]
    before = _flow_data(nodes, [{"id": "e1", "source": "n1", "target": "n2"}])
    after = _flow_data(nodes, [{"id": "e2", "source": "n1", "target": "n3"}])

    await _patch_flow_data(client, logged_in_headers, flow["id"], before)
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(client, logged_in_headers, flow["id"], after)

    body = (await _get_diff(client, logged_in_headers, flow["id"], snap["id"])).json()

    assert body["summary"]["edges_added"] == 1
    assert body["summary"]["edges_removed"] == 1


async def test_code_change_in_a_realistic_payload(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    def code_template(body: str) -> dict:
        return {"_type": "Component", "code": {"name": "code", "type": "code", "value": body}}

    await _patch_flow_data(
        client, logged_in_headers, flow["id"], _flow_data([_node("n1", code_template("def run():\n    return 1\n"))])
    )
    snap = await _create_snapshot(client, logged_in_headers, flow["id"])
    await _patch_flow_data(
        client,
        logged_in_headers,
        flow["id"],
        _flow_data([_node("n1", code_template("def run():\n    return 2\n\n# note\n"))]),
    )

    body = (await _get_diff(client, logged_in_headers, flow["id"], snap["id"])).json()

    code_change = body["nodes"]["modified"][0]["code_changes"][0]
    assert code_change["added_lines"] == 3
    assert code_change["removed_lines"] == 1
    assert "return 2" in code_change["unified_diff"]
    assert body["summary"]["code_fields_changed"] == 1


class TestDiffEndpointStaysOutOfTheSchema:
    """The whole versions router is intentionally hidden from the OpenAPI spec."""

    def test_diff_route_is_not_published(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langflow.api.v1 import flow_version_router

        app = FastAPI()
        app.include_router(flow_version_router)

        schema = TestClient(app).get("/openapi.json").json()

        assert schema["paths"] == {}


@pytest.mark.usefixtures("client")
def test_draft_sentinel_is_not_a_valid_uuid():
    """Guards the sentinel against ever colliding with a real version id."""
    from uuid import UUID

    from langflow.api.v1.flow_version import DRAFT_COMPARISON_TARGET

    with pytest.raises(ValueError, match="badly formed"):
        UUID(DRAFT_COMPARISON_TARGET)


def test_diff_response_omits_unset_values_but_keeps_explicit_nulls():
    """exclude_unset, not exclude_none: a value cleared to null is not a redaction."""
    from langflow.api.v1.schemas.flow_version_diff import DiffFieldChange

    redacted = DiffFieldChange.model_validate(
        {"name": "api_key", "status": "modified", "redacted": True, "display_name": None}
    )
    cleared = DiffFieldChange.model_validate(
        {"name": "prompt", "status": "modified", "redacted": False, "before": "hi", "after": None}
    )

    redacted_dump = redacted.model_dump(exclude_unset=True)
    cleared_dump = cleared.model_dump(exclude_unset=True)

    assert "before" not in redacted_dump
    assert "after" not in redacted_dump
    assert cleared_dump["before"] == "hi"
    assert "after" in cleared_dump
    assert cleared_dump["after"] is None
