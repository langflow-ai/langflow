"""Regression tests for LE-2240 and LE-2649.

Flow and project export paths must not emit cleartext secrets. The legacy
``remove_api_keys`` scrubber only nulled fields that were *both* marked
``password`` and named like an API key, so a ``password``-marked field under an
ordinary name (``plain_password``, ``service_token``) and a credential-bearing
connection string were exported verbatim.

LE-2649: the export paths must still keep global-variable bindings. A
``load_from_db`` field stores the variable *name*, not the secret, and the
importing instance resolves the credential by that name. A bound value is kept
only when it names one of the flow owner's global variables, so a name-shaped
literal behind a stale ``load_from_db`` flag is still nulled.

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
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.utils.flow_secrets import strip_flow_secrets, strip_secret_field_values
from lfx.services.deps import session_scope

# Values that must never survive an export.
_SECRET_PASSWORD = "secret-pass"  # noqa: S105  # pragma: allowlist secret
_SECRET_TOKEN = "tok-DEADBEEF"  # noqa: S105  # pragma: allowlist secret
_SECRET_API_KEY = "sk-SUPERSECRET"  # noqa: S105  # pragma: allowlist secret
_SECRET_DSN = "postgresql://user:pass@db/app"  # noqa: S105  # pragma: allowlist secret

_LEAKED_VALUES = (_SECRET_PASSWORD, _SECRET_TOKEN, _SECRET_API_KEY, _SECRET_DSN)

# Global-variable names referenced by bound fields; these must survive an export.
_BOUND_VARIABLE_NAME = "repro-binding"
_BOUND_OPENAI_VARIABLE_NAME = "OPENAI_API_KEY"
_BOUND_VARIABLE_NAMES = frozenset({_BOUND_VARIABLE_NAME, _BOUND_OPENAI_VARIABLE_NAME})
# A credential-shaped literal behind a stale ``load_from_db`` flag is still a secret.
_MISLABELLED_API_KEY = "sk-MISLABELLEDSECRET"  # pragma: allowlist secret
# Passes the variable-name shape check but names no global variable.
_NAME_SHAPED_SECRET = "sk_live_NAMESHAPEDSECRET"  # noqa: S105  # pragma: allowlist secret


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


def _bound_flow_data() -> dict:
    """Flow data whose password fields are bound to global variables."""
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
                            # The LE-2649 repro field: bound to a Credential variable.
                            "secret_token": {
                                "_input_type": "SecretStrInput",
                                "name": "secret_token",
                                "password": True,
                                "load_from_db": True,
                                "value": _BOUND_VARIABLE_NAME,
                                "type": "str",
                            },
                            # api_key-named fields lost their binding even before LE-2240.
                            "api_key": {
                                "_input_type": "SecretStrInput",
                                "name": "api_key",
                                "password": True,
                                "load_from_db": True,
                                "value": _BOUND_OPENAI_VARIABLE_NAME,
                                "type": "str",
                            },
                            # A literal secret is still nulled.
                            "plain_password": {
                                "_input_type": "SecretStrInput",
                                "name": "password",
                                "password": True,
                                "load_from_db": False,
                                "value": _SECRET_PASSWORD,
                                "type": "str",
                            },
                            # A credential-shaped value cannot be a variable name.
                            "service_token": {
                                "_input_type": "SecretStrInput",
                                "name": "service_token",
                                "password": True,
                                "load_from_db": True,
                                "value": _MISLABELLED_API_KEY,
                                "type": "str",
                            },
                            # A name-shaped literal that names no variable of the owner.
                            "stripe_key": {
                                "_input_type": "SecretStrInput",
                                "name": "stripe_key",
                                "password": True,
                                "load_from_db": True,
                                "value": _NAME_SHAPED_SECRET,
                                "type": "str",
                            },
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


def _assert_bindings_kept(flow_dict: dict) -> None:
    """Variable names survive the export while literal secrets are still nulled."""
    template = flow_dict["data"]["nodes"][0]["data"]["node"]["template"]

    assert template["secret_token"]["value"] == _BOUND_VARIABLE_NAME
    assert template["secret_token"]["load_from_db"] is True
    assert template["api_key"]["value"] == _BOUND_OPENAI_VARIABLE_NAME
    assert template["api_key"]["load_from_db"] is True
    assert template["plain_password"]["value"] is None
    assert template["service_token"]["value"] is None
    assert template["stripe_key"]["value"] is None

    serialized = json.dumps(flow_dict)
    assert _SECRET_PASSWORD not in serialized
    assert _MISLABELLED_API_KEY not in serialized
    assert _NAME_SHAPED_SECRET not in serialized


async def _create_bound_variables(active_user) -> None:
    """Create the owner's global variables that the bound fields reference."""
    variable_service = get_variable_service()
    async with session_scope() as session:
        existing = set(await variable_service.list_variables(user_id=active_user.id, session=session))
        for name in _BOUND_VARIABLE_NAMES - existing:
            await variable_service.create_variable(
                active_user.id,
                name,
                "stored-credential",  # pragma: allowlist secret
                default_fields=[],
                type_=CREDENTIAL_TYPE,
                session=session,
            )


async def _create_flow(active_user, *, folder_id=None, data=None, name="le2240-export-secret-flow") -> str:
    async with session_scope() as session:
        flow_create = FlowCreate(
            name=name,
            description="regression flow for export secret sanitization",
            data=data if data is not None else _secret_flow_data(),
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


@pytest.mark.usefixtures("active_user")
async def test_flows_download_keeps_global_variable_bindings(client: AsyncClient, logged_in_headers, active_user):
    """LE-2649: POST /api/v1/flows/download/ keeps the variable name of bound fields."""
    await _create_bound_variables(active_user)
    flow_id = await _create_flow(active_user, data=_bound_flow_data())

    read_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert read_response.status_code == status.HTTP_200_OK
    stored_template = read_response.json()["data"]["nodes"][0]["data"]["node"]["template"]
    assert stored_template["secret_token"]["value"] == _BOUND_VARIABLE_NAME

    response = await client.post("api/v1/flows/download/", json=[flow_id], headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    _assert_bindings_kept(response.json())


@pytest.mark.usefixtures("active_user")
async def test_flows_download_zip_keeps_global_variable_bindings(client: AsyncClient, logged_in_headers, active_user):
    """LE-2649: the multi-flow ZIP export keeps bindings in every flow file."""
    await _create_bound_variables(active_user)
    flow_ids = [
        await _create_flow(active_user, data=_bound_flow_data(), name=f"le2649-bound-flow-{index}")
        for index in range(2)
    ]

    response = await client.post("api/v1/flows/download/", json=flow_ids, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_file:
        names = zip_file.namelist()
        assert names
        for name in names:
            _assert_bindings_kept(json.loads(zip_file.read(name)))


@pytest.mark.usefixtures("active_user")
async def test_flows_download_nulls_bindings_to_missing_variables(client: AsyncClient, logged_in_headers, active_user):
    """A bound value that names none of the owner's variables is not exported."""
    flow_id = await _create_flow(active_user, data=_bound_flow_data(), name="le2649-unbound-flow")

    response = await client.post("api/v1/flows/download/", json=[flow_id], headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    # ``api_key`` is not asserted: login may create ``OPENAI_API_KEY`` from the environment.
    template = response.json()["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["secret_token"]["value"] is None
    assert template["stripe_key"]["value"] is None
    serialized = json.dumps(response.json())
    assert _BOUND_VARIABLE_NAME not in serialized
    assert _NAME_SHAPED_SECRET not in serialized


@pytest.mark.usefixtures("active_user")
async def test_project_download_keeps_global_variable_bindings(client: AsyncClient, logged_in_headers, active_user):
    """LE-2649: GET /api/v1/projects/download/{project_id} keeps the variable name of bound fields."""
    create_response = await client.post(
        "api/v1/projects/",
        json={"name": "le2649-project", "description": "", "components_list": [], "flows_list": []},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    project_id = create_response.json()["id"]

    await _create_bound_variables(active_user)
    await _create_flow(active_user, folder_id=project_id, data=_bound_flow_data())

    response = await client.get(f"api/v1/projects/download/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_file:
        names = zip_file.namelist()
        assert len(names) == 1
        _assert_bindings_kept(json.loads(zip_file.read(names[0])))


def test_strip_flow_secrets_keeps_bindings_without_mutating_input():
    """The export scrubber keeps bindings on a detached copy of the envelope."""
    flow = {"name": "bound", "data": _bound_flow_data()}

    scrubbed = strip_flow_secrets(flow, known_variable_names=_BOUND_VARIABLE_NAMES)

    _assert_bindings_kept(scrubbed)
    template = flow["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["plain_password"]["value"] == _SECRET_PASSWORD
    assert template["service_token"]["value"] == _MISLABELLED_API_KEY
    assert template["stripe_key"]["value"] == _NAME_SHAPED_SECRET


def test_strip_flow_secrets_nulls_bindings_without_known_variables():
    """Without the owner's variable names, the export scrubber keeps no bound value."""
    scrubbed = strip_flow_secrets({"name": "bound", "data": _bound_flow_data()})

    template = scrubbed["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["secret_token"]["value"] is None
    assert template["api_key"]["value"] is None
    assert template["stripe_key"]["value"] is None


def test_strip_secret_field_values_still_nulls_bindings():
    """The default scrubber, used by anonymous public-flow reads, still nulls variable names."""
    stripped = strip_secret_field_values(_bound_flow_data())

    template = stripped["nodes"][0]["data"]["node"]["template"]
    assert template["secret_token"]["value"] is None
    assert template["api_key"]["value"] is None


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
