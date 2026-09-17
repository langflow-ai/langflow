"""INT-14 GA: import preserves nodes whose connections are unavailable locally.

The connection contract requires that a flow imported into an environment where
its connection handle (or even its component type) does not exist keeps the node
and the handle verbatim: nothing is resolved, substituted, or stripped at import
time. Execution fails closed later with the typed error vocabulary; the saved
flow is never silently rewritten.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient

# A connection handle that exists in the export's origin environment but not in
# this one: no row is ever created for it in these tests.
UNAVAILABLE_HANDLE = "google_workspace/origin_env_only"
UNAVAILABLE_COMPONENT = "GoogleDriveListComponentNoLongerInstalled"


def _flow_data() -> dict:
    return {
        "nodes": [
            {
                "id": f"{UNAVAILABLE_COMPONENT}-node1",
                "data": {
                    "type": UNAVAILABLE_COMPONENT,
                    "node": {
                        "display_name": "Drive listing",
                        "template": {
                            "_type": "Component",
                            "connection": {
                                "name": "connection",
                                "type": "connection_ref",
                                "provider": "google_workspace",
                                "value": UNAVAILABLE_HANDLE,
                                "required_scopes": ["drive.readonly"],
                                "show": True,
                            },
                            "query": {
                                "name": "query",
                                "type": "str",
                                "value": "quarterly reports",
                                "show": True,
                            },
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


def _flow_payload() -> dict:
    return {"name": f"imported-{uuid.uuid4().hex[:8]}", "data": _flow_data()}


def _stored_template(flow: dict) -> dict:
    return flow["data"]["nodes"][0]["data"]["node"]["template"]


def _assert_node_preserved_verbatim(flow: dict) -> None:
    nodes = flow["data"]["nodes"]
    assert len(nodes) == 1
    # The unavailable component type and the unavailable handle both survive.
    assert nodes[0]["data"]["type"] == UNAVAILABLE_COMPONENT
    template = _stored_template(flow)
    assert template["connection"]["value"] == UNAVAILABLE_HANDLE
    assert template["connection"]["required_scopes"] == ["drive.readonly"]
    assert template["query"]["value"] == "quarterly reports"


async def test_create_preserves_a_node_referencing_an_unavailable_connection(
    client: AsyncClient, logged_in_headers: dict[str, str]
) -> None:
    created = await client.post("api/v1/flows/", json=_flow_payload(), headers=logged_in_headers)
    assert created.status_code == status.HTTP_201_CREATED, created.text
    flow = created.json()
    _assert_node_preserved_verbatim(flow)

    fetched = await client.get(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    assert fetched.status_code == status.HTTP_200_OK
    _assert_node_preserved_verbatim(fetched.json())


async def test_upload_preserves_unavailable_nodes_and_connection_handles(
    client: AsyncClient, logged_in_headers: dict[str, str]
) -> None:
    payload = _flow_payload()
    uploaded = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", json.dumps(payload), "application/json")},
        headers=logged_in_headers,
    )
    assert uploaded.status_code == status.HTTP_201_CREATED, uploaded.text
    flows = uploaded.json()
    assert len(flows) == 1
    _assert_node_preserved_verbatim(flows[0])

    fetched = await client.get(f"api/v1/flows/{flows[0]['id']}", headers=logged_in_headers)
    assert fetched.status_code == status.HTTP_200_OK
    _assert_node_preserved_verbatim(fetched.json())


async def test_import_does_not_create_or_require_a_connection_row(
    client: AsyncClient, logged_in_headers: dict[str, str]
) -> None:
    """Importing a flow must not provision, probe, or require the named connection."""
    created = await client.post("api/v1/flows/", json=_flow_payload(), headers=logged_in_headers)
    assert created.status_code == status.HTTP_201_CREATED, created.text

    listed = await client.get("api/v1/connections", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_200_OK
    handles = {f"{row['provider_key']}/{row['name']}" for row in listed.json()}
    assert UNAVAILABLE_HANDLE not in handles
