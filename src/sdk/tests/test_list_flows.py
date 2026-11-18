"""Response compatibility for sync and async flow listings."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest
import respx
from langflow_sdk import AsyncClient, Client, Flow
from langflow_sdk.exceptions import LangflowAuthError, LangflowConnectionError, LangflowValidationError
from pydantic import ValidationError

_BASE = "https://langflow.test"
_ID = "aaaaaaaa-0000-0000-0000-000000000001"
_FOLDER = "bbbbbbbb-0000-0000-0000-000000000001"
_RECORD = {"id": _ID, "name": "flow", "data": {"nodes": [], "edges": []}}


async def _list(client_kind, **kwargs):
    if client_kind == "sync":
        with Client(_BASE) as client:
            return client.list_flows(**kwargs)
    async with AsyncClient(_BASE) as client:
        return await client.list_flows(**kwargs)


@pytest.fixture(params=["sync", "async"])
def client_kind(request):
    return request.param


@pytest.mark.unit
@pytest.mark.parametrize("get_all", [False, True])
@pytest.mark.parametrize("envelope", [False, True])
@pytest.mark.parametrize("records", [[], [_RECORD], [_RECORD, _RECORD]])
async def test_flow_list_shapes(client_kind, get_all, envelope, records):
    payload = {"items": records, "total": 15, "page": 2, "size": 2, "pages": 8} if envelope else records
    with respx.mock as router:
        route = router.get(f"{_BASE}/api/v1/flows/").respond(200, json=payload)
        result = await _list(client_kind, get_all=get_all)
    assert result == [Flow.model_validate(record) for record in records]
    assert route.call_count == 1
    assert dict(route.calls[0].request.url.params) == {
        "remove_example_flows": "false",
        "components_only": "false",
        "get_all": str(get_all).lower(),
        "header_flows": "false",
        "page": "1",
        "size": "50",
    }
    if result:
        assert result[0].id == UUID(_ID)
        assert result[0].data == _RECORD["data"]


@pytest.mark.unit
@pytest.mark.parametrize("metadata", [{}, {"unexpected": "ignored"}])
async def test_list_envelope_does_not_require_metadata(client_kind, metadata):
    with respx.mock as router:
        route = router.get(f"{_BASE}/api/v1/flows/").respond(200, json={"items": [_RECORD], **metadata})
        result = await _list(client_kind)
    assert result == [Flow.model_validate(_RECORD)]
    assert route.call_count == 1


@pytest.mark.unit
async def test_all_flags_and_order_preserved(client_kind):
    records = [{**_RECORD, "name": "second"}, _RECORD, _RECORD]
    with respx.mock as router:
        route = router.get(f"{_BASE}/api/v1/flows/").respond(200, json={"items": records, "total": 100, "pages": 50})
        rows = await _list(
            client_kind,
            folder_id=UUID(_FOLDER),
            remove_example_flows=True,
            components_only=True,
            get_all=True,
            header_flows=True,
            page=2,
            size=3,
        )
    assert [row.name for row in rows] == ["second", "flow", "flow"]
    assert route.call_count == 1
    assert dict(route.calls[0].request.url.params) == {
        "folder_id": _FOLDER,
        "remove_example_flows": "true",
        "components_only": "true",
        "get_all": "true",
        "header_flows": "true",
        "page": "2",
        "size": "3",
    }


@pytest.mark.unit
@pytest.mark.parametrize("envelope", [False, True])
@pytest.mark.parametrize("data", [None, {"component": "source"}])
async def test_header_fields_and_defaults(client_kind, envelope, data):
    header = {"id": _ID, "name": "header", "data": data, "flow_type": "flow", "a2a_enabled": False}
    payload = {"items": [header]} if envelope else [header]
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, json=payload)
        rows = await _list(client_kind, header_flows=True)
    assert rows == [Flow.model_validate(header)]
    assert rows[0].data == data
    assert rows[0].is_component is False
    assert rows[0].mcp_enabled is False
    assert rows[0].locked is False
    assert rows[0].webhook is False
    assert rows[0].access_type == "PRIVATE"
    assert rows[0].user_id is None
    assert rows[0].icon is None
    assert not hasattr(rows[0], "flow_type")


@pytest.mark.unit
@pytest.mark.parametrize("payload", [{}, ""])
async def test_legacy_empty_iterables_unchanged(client_kind, payload):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, json=payload)
        assert await _list(client_kind) == []


@pytest.mark.unit
@pytest.mark.parametrize("payload", [None, 5, False])
async def test_legacy_non_iterables_unchanged(client_kind, payload):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, content=json.dumps(payload).encode())
        with pytest.raises(TypeError):
            await _list(client_kind)


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        {"total": 5},
        {"items": None},
        {"items": {}},
        {"items": ""},
        {"items": "bad"},
        {"items": 5},
        {"items": False},
        "bad",
    ],
)
async def test_malformed_envelopes_preserve_model_errors(client_kind, payload):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, json=payload)
        with pytest.raises(ValidationError) as caught:
            await _list(client_kind)
    assert [(error["type"], error["loc"]) for error in caught.value.errors()] == [("model_type", ())]


@pytest.mark.unit
@pytest.mark.parametrize("envelope", [False, True])
@pytest.mark.parametrize("field", ["id", "is_component", "mcp_enabled", "webhook", "locked", "access_type"])
async def test_invalid_records_are_not_hidden(client_kind, envelope, field):
    record = {**_RECORD, field: None}
    payload = {"items": [record]} if envelope else [record]
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, json=payload)
        with pytest.raises(ValidationError) as caught:
            await _list(client_kind)
    assert caught.value.errors()[0]["loc"] == (field,)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "error"), [(401, LangflowAuthError), (403, LangflowAuthError), (422, LangflowValidationError)]
)
async def test_http_errors_unchanged(client_kind, status, error):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(status, json={"detail": "rejected"})
        with pytest.raises(error):
            await _list(client_kind)


@pytest.mark.unit
async def test_connection_errors_unchanged(client_kind):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").mock(side_effect=httpx.ConnectError("unavailable"))
        with pytest.raises(LangflowConnectionError):
            await _list(client_kind)


@pytest.mark.unit
async def test_json_decode_error_unchanged(client_kind):
    with respx.mock as router:
        router.get(f"{_BASE}/api/v1/flows/").respond(200, content=b"not JSON")
        with pytest.raises(json.JSONDecodeError):
            await _list(client_kind)
