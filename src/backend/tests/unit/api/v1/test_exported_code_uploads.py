"""Downloaded flows retain executable code and report invalid lines as validation errors."""

import io
import json
import zipfile
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.parametrize(
    ("route", "file_format"),
    [("flows", "single"), ("flows", "batch"), ("flows", "zip"), ("projects", "batch"), ("projects", "zip")],
)
@pytest.mark.parametrize("invalid", [False, True])
async def test_upload_exported_code(client: AsyncClient, logged_in_headers, route, file_format, invalid):
    name = f"exported-{uuid4()}"
    code = "def build(self):\n    return 'exported'\n"
    flow = {
        "name": name,
        "data": {
            "nodes": [
                {
                    "id": "ChatInput-node",
                    "data": {
                        "type": "ChatInput",
                        "node": {
                            "template": {
                                "code": {"type": "code", "value": ["source", None] if invalid else code.split("\n")},
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    }
    if file_format == "zip":
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("flow.json", json.dumps(flow))
        upload = ("flows.zip", archive.getvalue(), "application/zip")
    else:
        payload = flow if file_format == "single" else {"folder_name": name, "flows": [flow]}
        upload = ("flows.json", json.dumps(payload), "application/json")

    response = await client.post(f"api/v1/{route}/upload/", files={"file": upload}, headers=logged_in_headers)

    if invalid:
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "Code lines must all be strings" in response.text
        listed = await client.get("api/v1/flows/", headers=logged_in_headers)
        assert all(item["name"] != name for item in listed.json())
    else:
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()[0]["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == code
