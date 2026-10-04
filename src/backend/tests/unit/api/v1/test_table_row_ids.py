"""Table row ids belong to the flow's history: components and exported files never see them."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import status
from langflow.api.v1.endpoints import _raw_component_parameters
from langflow.api.v1.schemas import UpdateCustomComponentRequest

if TYPE_CHECKING:
    from httpx import AsyncClient

KEYED_ROWS = [
    {"_id": "r1", "_pos": "a0", "key": "Accept", "value": "json"},
    {"_id": "r2", "_pos": "a1", "key": "Auth", "value": "token"},
]
PLAIN_ROWS = [{"key": "Accept", "value": "json"}, {"key": "Auth", "value": "token"}]


def _table_field(rows: list[dict]) -> dict:
    return {"name": "headers", "type": "table", "_input_type": "TableInput", "value": rows}


def _flow_data(rows: list[dict]) -> dict:
    return {
        "nodes": [
            {
                "id": "api-1",
                "type": "genericNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": "api-1",
                    "type": "Probe",
                    "node": {
                        "template": {
                            "headers": _table_field(rows),
                            "url": {"name": "url", "type": "str", "value": "http://x"},
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


def test_component_parameters_leave_out_row_ids():
    template = {"headers": _table_field(KEYED_ROWS), "url": {"type": "str", "value": "http://x"}}

    params = _raw_component_parameters(template)
    refreshed = _raw_component_parameters(template, field="headers", field_value=KEYED_ROWS[:1])

    assert params["headers"] == PLAIN_ROWS
    assert params["url"] == "http://x"
    assert refreshed["headers"] == PLAIN_ROWS[:1]


PROBE_CODE = """
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, TableInput
from lfx.schema.message import Message


class RowsProbe(Component):
    display_name = "Rows Probe"
    inputs = [
        TableInput(
            name="headers",
            display_name="Headers",
            table_schema=[{"name": "key", "type": "str"}, {"name": "value", "type": "str"}],
            value=[],
        ),
        MessageTextInput(name="seen", display_name="Seen", real_time_refresh=True),
    ]
    outputs = [Output(display_name="Out", name="out", method="run")]

    def update_build_config(self, build_config, field_value, field_name=None):
        build_config["seen"]["value"] = repr(self.headers)
        return build_config

    def run(self) -> Message:
        return Message(text="")
"""


async def test_component_update_never_hands_row_ids_to_the_component(client: AsyncClient, logged_in_headers):
    template = {
        "headers": _table_field(KEYED_ROWS),
        "seen": {"name": "seen", "type": "str", "_input_type": "MessageTextInput", "value": ""},
    }
    request = UpdateCustomComponentRequest(
        code=PROBE_CODE,
        frontend_node={"outputs": []},
        field="seen",
        field_value="",
        template=template,
    )

    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    seen = response.json()["template"]["seen"]["value"]
    assert "Accept" in seen
    assert "_id" not in seen
    assert "_pos" not in seen


async def test_flow_download_leaves_out_row_ids(client: AsyncClient, logged_in_headers):
    payload = {"name": f"rows-{uuid4().hex[:8]}", "data": _flow_data(KEYED_ROWS)}
    created = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert created.status_code == status.HTTP_201_CREATED, created.text

    response = await client.post("api/v1/flows/download/", json=[created.json()["id"]], headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    template = response.json()["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["headers"]["value"] == PLAIN_ROWS
    # The stored flow keeps them.
    stored = await client.get(f"api/v1/flows/{created.json()['id']}", headers=logged_in_headers)
    assert stored.json()["data"]["nodes"][0]["data"]["node"]["template"]["headers"]["value"] == KEYED_ROWS
