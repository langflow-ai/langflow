"""Regression tests for LE-2240.

Flow and project export paths must not emit cleartext secrets. The legacy
``remove_api_keys`` scrubber only nulled fields that were *both* marked
``password`` and named like an API key, so a ``password``-marked field under an
ordinary name (``plain_password``, ``service_token``) and a credential-bearing
connection string were exported verbatim.

Covered export boundaries:

* ``POST /api/v1/flows/download/``            (``flows_helpers._build_flows_download_response``)
* ``GET  /api/v1/projects/download/{id}``     (``projects_files.download_project_flows``)
* flow-version reads with ``strip_keys=True`` (``flow_version.strip_version_data``)
"""

import io
import json
import zipfile

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.flow_version import strip_version_data
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.utils.flow_secrets import strip_flow_secrets, strip_secret_field_values
from lfx.services.deps import session_scope

# Values that must never survive an export.
_SECRET_PASSWORD = "secret-pass"  # noqa: S105  # pragma: allowlist secret
_SECRET_TOKEN = "tok-DEADBEEF"  # noqa: S105  # pragma: allowlist secret
_SECRET_API_KEY = "sk-SUPERSECRET"  # noqa: S105  # pragma: allowlist secret
_SECRET_DSN = "postgresql://user:pass@db/app"  # noqa: S105  # pragma: allowlist secret

_LEAKED_VALUES = (_SECRET_PASSWORD, _SECRET_TOKEN, _SECRET_API_KEY, _SECRET_DSN)


def _secret_flow_data() -> dict:
    """Flow data whose node carries secrets the legacy scrubber missed."""
    return {
        "nodes": [
            {
                "id": "node-1",
                "type": "genericNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "id": "node-1",
                    "type": "SomeComponent",
                    "node": {
                        "template": {
                            # password-marked, name does NOT match api/key/token
                            "plain_password": {
                                "name": "password",
                                "password": True,
                                "value": _SECRET_PASSWORD,
                                "type": "str",
                            },
                            # password-marked, secret-shaped name the legacy
                            # has_api_terms() check still rejects ("token"
                            # alone does not contain "api")
                            "service_token": {
                                "name": "service_token",
                                "password": True,
                                "value": _SECRET_TOKEN,
                                "type": "str",
                            },
                            # credential-bearing connection string, not marked password
                            "database_url": {
                                "name": "database_url",
                                "password": False,
                                "value": _SECRET_DSN,
                                "type": "str",
                            },
                            # the one case the legacy scrubber did handle
                            "api_key": {
                                "name": "api_key",
                                "password": True,
                                "value": _SECRET_API_KEY,
                                "type": "str",
                            },
                            # non-secret field must survive untouched
                            "base_url": {
                                "name": "base_url",
                                "password": False,
                                "value": "https://api.openai.com/v1",
                                "type": "str",
                            },
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


def _assert_scrubbed(flow_dict: dict) -> None:
    """Every secret value is nulled and the public field is preserved."""
    template = flow_dict["data"]["nodes"][0]["data"]["node"]["template"]

    assert template["plain_password"]["value"] is None
    assert template["service_token"]["value"] is None
    assert template["database_url"]["value"] is None
    assert template["api_key"]["value"] is None
    assert template["base_url"]["value"] == "https://api.openai.com/v1"

    # Belt-and-braces: no secret literal anywhere in the serialized payload.
    serialized = json.dumps(flow_dict)
    for secret in _LEAKED_VALUES:
        assert secret not in serialized


async def _create_flow(active_user, *, folder_id=None) -> str:
    async with session_scope() as session:
        flow_create = FlowCreate(
            name="le2240-export-secret-flow",
            description="regression flow for export secret sanitization",
            data=_secret_flow_data(),
            folder_id=folder_id,
            user_id=active_user.id,
        )
        flow = Flow.model_validate(flow_create.model_dump(exclude={"id"}))
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = str(flow.id)
        await session.commit()
    return flow_id


@pytest.mark.usefixtures("active_user")
async def test_flows_download_strips_non_api_password_fields(client: AsyncClient, logged_in_headers, active_user):
    """POST /api/v1/flows/download/ must not emit cleartext secrets."""
    flow_id = await _create_flow(active_user)

    response = await client.post("api/v1/flows/download/", json=[flow_id], headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    _assert_scrubbed(response.json())


@pytest.mark.usefixtures("active_user")
async def test_project_download_strips_non_api_password_fields(client: AsyncClient, logged_in_headers, active_user):
    """GET /api/v1/projects/download/{project_id} must not emit cleartext secrets."""
    create_response = await client.post(
        "api/v1/projects/",
        json={"name": "le2240-project", "description": "", "components_list": [], "flows_list": []},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    project_id = create_response.json()["id"]

    await _create_flow(active_user, folder_id=project_id)

    response = await client.get(f"api/v1/projects/download/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_file:
        names = zip_file.namelist()
        assert len(names) == 1
        _assert_scrubbed(json.loads(zip_file.read(names[0])))


def test_strip_version_data_strips_non_api_password_fields():
    """Flow-version reads with strip_keys=True must not emit cleartext secrets."""
    stripped = strip_version_data(_secret_flow_data())

    assert stripped is not None
    _assert_scrubbed({"data": stripped})


def test_strip_version_data_does_not_mutate_input():
    """The scrubber returns a detached copy rather than clearing stored data."""
    original = _secret_flow_data()
    strip_version_data(original)

    template = original["nodes"][0]["data"]["node"]["template"]
    assert template["plain_password"]["value"] == _SECRET_PASSWORD
    assert template["database_url"]["value"] == _SECRET_DSN


def test_strip_secret_field_values_detaches_empty_mapping():
    """An empty ``data`` mapping must still be copied, not aliased.

    ``strip_flow_secrets`` documents that the returned envelope's ``data`` is detached so
    the caller never mutates the ORM-backed payload it serialized from. A falsy-but-present
    mapping previously short-circuited and returned the caller's own object.
    """
    original: dict = {}

    result = strip_secret_field_values(original)

    assert result == {}
    assert result is not original
    result["injected"] = True
    assert original == {}


def test_strip_flow_secrets_detaches_empty_data():
    """The envelope wrapper must not alias an empty ``data`` mapping either."""
    flow = {"name": "empty", "data": {}}

    scrubbed = strip_flow_secrets(flow)

    assert scrubbed["data"] == {}
    assert scrubbed["data"] is not flow["data"]
    scrubbed["data"]["injected"] = True
    assert flow["data"] == {}


def test_strip_secret_field_values_still_passes_none_through():
    """``None`` remains a pass-through so callers can distinguish absent data."""
    assert strip_secret_field_values(None) is None
