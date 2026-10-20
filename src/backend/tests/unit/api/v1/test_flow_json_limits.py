"""Every endpoint that stores a new flow refuses a graph the flow engine cannot read.

The engine refuses JSON with a lone surrogate or nesting deeper than 127
levels (src/lfx-native/fixtures/limit_cases.json). A save refuses such a graph
with 422 FLOW_GRAPH_INVALID and no violations; creating a flow records no
history, but it must refuse the same graphs, or every later save of the flow
is refused.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient

# JSON text for a node value. The flow is level 1 of its nesting and the
# value's first array is level 8, so 121 arrays reach level 128.
LIMIT_VALUES = {
    "a lone surrogate": '"\\ud800"',
    "nesting 128 levels deep": "[" * 121 + "]" * 121,
}
NORMAL_VALUE = '"hi"'


def _flow_json(value_json: str) -> str:
    """A flow as JSON text, holding one node whose field value is ``value_json``."""
    node = {
        "id": "a",
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": "a", "type": "Prompt", "node": {"template": {"text": {"type": "str", "value": "VALUE"}}}},
    }
    flow = {"name": f"limits-{uuid4().hex[:8]}", "data": {"nodes": [node], "edges": []}}
    return json.dumps(flow).replace('"VALUE"', value_json)


def _assert_refused_as_unreadable(response) -> None:
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    detail = response.json()["detail"]
    assert (detail["code"], detail["graph"], detail["violations"]) == ("FLOW_GRAPH_INVALID", "submitted", [])
    assert detail["message"].startswith("The submitted flow data is not valid JSON: ")


async def _create(client: AsyncClient, headers: dict, endpoint: str, flow_json: str):
    json_headers = {**headers, "Content-Type": "application/json"}
    if endpoint == "create":
        return await client.post("api/v1/flows/", content=flow_json, headers=json_headers)
    if endpoint == "batch create":
        return await client.post("api/v1/flows/batch/", content=f'{{"flows": [{flow_json}]}}', headers=json_headers)
    if endpoint == "upsert":
        return await client.put(f"api/v1/flows/{uuid4()}", content=flow_json, headers=json_headers)
    if endpoint == "upload":
        file = ("flow.json", flow_json, "application/json")
        return await client.post("api/v1/flows/upload/", files={"file": file}, headers=headers)
    if endpoint == "zip upload":
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("flow.json", flow_json)
        file = ("flows.zip", archive.getvalue(), "application/zip")
        return await client.post("api/v1/flows/upload/", files={"file": file}, headers=headers)
    if endpoint == "project upload":
        project = f'{{"folder_name": "limits-{uuid4().hex[:8]}", "flows": [{flow_json}]}}'
        file = ("project.json", project, "application/json")
        return await client.post("api/v1/projects/upload/", files={"file": file}, headers=headers)
    raise AssertionError(endpoint)


ENDPOINTS = ["create", "batch create", "upsert", "upload", "zip upload", "project upload"]
# A file upload reads the file with orjson, which refuses a lone surrogate
# itself: the upload answers 400 for a file that is not valid JSON before the
# engine reads it (a ZIP upload skips the file and finds no flow).
FILE_ENDPOINTS = {"upload", "zip upload", "project upload"}


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_a_normal_flow_is_created(client: AsyncClient, logged_in_headers, endpoint):
    response = await _create(client, logged_in_headers, endpoint, _flow_json(NORMAL_VALUE))

    assert response.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, response.text


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("value_json", LIMIT_VALUES.values(), ids=LIMIT_VALUES.keys())
async def test_a_flow_that_breaks_a_json_limit_is_not_created(
    client: AsyncClient, logged_in_headers, endpoint, value_json
):
    before = {flow["id"] for flow in (await client.get("api/v1/flows/", headers=logged_in_headers)).json()}

    response = await _create(client, logged_in_headers, endpoint, _flow_json(value_json))

    if endpoint in FILE_ENDPOINTS and value_json == LIMIT_VALUES["a lone surrogate"]:
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    else:
        _assert_refused_as_unreadable(response)
    after = {flow["id"] for flow in (await client.get("api/v1/flows/", headers=logged_in_headers)).json()}
    assert after == before
