"""Instance OAuth settings cannot enter the user-variable or sharing APIs."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable, VariableUpdate
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE, OAUTH_REGISTRATION_VARIABLE_PREFIX
from langflow.services.variable.service import DatabaseVariableService
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.variable import VariableNotFoundError
from lfx.services.variable.exceptions import RuntimeVariableError

pytestmark = pytest.mark.no_blockbuster

RESERVED_NAME = f"{OAUTH_REGISTRATION_VARIABLE_PREFIX}google-work"
NORMAL_NAME = "USER_CREDENTIAL"


@pytest.fixture
async def stored_variables(active_super_user):
    registration = {
        "provider": "google",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/google/callback",
        "scopes": ["openid"],
    }
    async with session_scope() as session:
        reserved = Variable(
            user_id=active_super_user.id,
            name=RESERVED_NAME,
            value=auth_utils.encrypt_api_key(json.dumps(registration)),
            type=CREDENTIAL_TYPE,
            default_fields=["api_key"],
        )
        ordinary = Variable(
            user_id=active_super_user.id,
            name=NORMAL_NAME,
            value=auth_utils.encrypt_api_key("ordinary-value"),
            type=CREDENTIAL_TYPE,
            default_fields=["api_key"],
        )
        session.add_all([reserved, ordinary])
        await session.flush()
        return SimpleNamespace(owner_id=active_super_user.id, reserved_id=reserved.id, ordinary_id=ordinary.id)


@pytest.fixture
def variable_service():
    return DatabaseVariableService(get_settings_service())


@pytest.fixture
async def registration_reader(client):
    async with session_scope() as session:
        user = User(
            username="registration-reader",
            password=auth_utils.get_auth_service().get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    response = await client.post("api/v1/login", data={"username": "registration-reader", "password": "testpassword"})
    assert response.status_code == 200
    yield SimpleNamespace(id=user_id, headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    async with session_scope() as session:
        await session.delete(await session.get(User, user_id))


@pytest.mark.parametrize("superuser", [False, True])
async def test_ordinary_variable_api_rejects_reserved_creation(
    client, registration_reader, logged_in_headers_super_user, superuser
):
    headers = logged_in_headers_super_user if superuser else registration_reader.headers
    response = await client.post(
        "api/v1/variables/",
        headers=headers,
        json={"name": RESERVED_NAME, "value": "replacement", "type": CREDENTIAL_TYPE, "default_fields": []},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_existing_registration_cannot_be_changed_through_variable_api(
    client, stored_variables, logged_in_headers_super_user, method
):
    kwargs = {"headers": logged_in_headers_super_user}
    if method == "patch":
        kwargs["json"] = {"id": str(stored_variables.reserved_id), "name": "RENAMED", "value": "replacement"}

    response = await getattr(client, method)(f"api/v1/variables/{stored_variables.reserved_id}", **kwargs)

    assert response.status_code == 404
    async with session_scope() as session:
        reserved = await session.get(Variable, stored_variables.reserved_id)
        assert reserved.name == RESERVED_NAME
        assert json.loads(auth_utils.decrypt_api_key(reserved.value))["client_id"] == "test-client"


async def test_shared_registration_cannot_be_changed_by_non_superuser(
    client, stored_variables, registration_reader, monkeypatch
):
    from langflow.services.authorization import fetch

    monkeypatch.setattr(fetch, "cross_user_fetch_enabled", AsyncMock(return_value=True))
    response = await client.patch(
        f"api/v1/variables/{stored_variables.reserved_id}",
        headers=registration_reader.headers,
        json={"id": str(stored_variables.reserved_id), "value": "replacement"},
    )

    assert response.status_code == 404


async def test_ordinary_variable_cannot_be_renamed_into_registration(
    client, stored_variables, logged_in_headers_super_user
):
    response = await client.patch(
        f"api/v1/variables/{stored_variables.ordinary_id}",
        headers=logged_in_headers_super_user,
        json={"id": str(stored_variables.ordinary_id), "name": RESERVED_NAME},
    )

    assert response.status_code == 422


async def test_registration_cannot_be_shared(
    client, stored_variables, registration_reader, logged_in_headers_super_user
):
    response = await client.post(
        "api/v1/authz/shares",
        headers=logged_in_headers_super_user,
        json={
            "resource_type": "variable",
            "resource_id": str(stored_variables.reserved_id),
            "scope": "user",
            "target_id": str(registration_reader.id),
            "permission_level": "write",
        },
    )

    assert response.status_code == 404


async def test_registration_is_hidden_from_variable_lists_and_bulk_runtime(
    client, stored_variables, logged_in_headers_super_user, variable_service
):
    response = await client.get("api/v1/variables/", headers=logged_in_headers_super_user)

    assert response.status_code == 200
    names = {row["name"] for row in response.json()}
    assert RESERVED_NAME not in names
    assert NORMAL_NAME in names
    async with session_scope() as session:
        assert RESERVED_NAME not in await variable_service.list_variables(stored_variables.owner_id, session)
        assert await variable_service.get_available_variable_names(
            stored_variables.owner_id, {RESERVED_NAME, NORMAL_NAME}, session
        ) == {NORMAL_NAME}
        bindings = dict(await variable_service.get_default_field_bindings(stored_variables.owner_id, session))
        assert RESERVED_NAME not in bindings
        assert bindings[NORMAL_NAME] == ["api_key"]
        values = await variable_service.get_all_decrypted_variables(stored_variables.owner_id, session)
        assert RESERVED_NAME not in values
        assert values[NORMAL_NAME] == "ordinary-value"


async def test_shared_registration_is_hidden_from_lists(stored_variables, registration_reader, variable_service):
    visibility = ResourceVisibilityScope(resource_ids=(stored_variables.reserved_id, stored_variables.ordinary_id))
    async with session_scope() as session:
        variables = await variable_service.get_all(registration_reader.id, session, visibility=visibility)

    names = {variable.name for variable in variables}
    assert RESERVED_NAME not in names
    assert NORMAL_NAME in names


@pytest.mark.parametrize("name", [RESERVED_NAME.lower(), RESERVED_NAME.replace("_", "X")])
async def test_ordinary_prefix_lookalike_remains_a_user_variable(stored_variables, variable_service, name):
    async with session_scope() as session:
        await variable_service.create_variable(stored_variables.owner_id, name, "ordinary-value", session=session)

        names = await variable_service.list_variables(stored_variables.owner_id, session)
        value = await variable_service.get_variable(stored_variables.owner_id, name, "api_key", session)

    assert name in names
    assert value.get_secret_value() == "ordinary-value"


async def test_runtime_cannot_read_registration_even_with_shared_access(
    stored_variables, registration_reader, variable_service, monkeypatch
):
    from langflow.services import deps

    authz = SimpleNamespace(
        is_enabled=AsyncMock(return_value=True),
        supports_cross_user_fetch=AsyncMock(return_value=True),
        get_resource_visibility=AsyncMock(
            return_value=ResourceVisibilityScope(resource_ids=(stored_variables.reserved_id,))
        ),
    )
    monkeypatch.setattr(deps, "get_authorization_service", lambda: authz)
    async with session_scope() as session:
        for user_id in (stored_variables.owner_id, registration_reader.id):
            with pytest.raises(RuntimeVariableError, match="unavailable to flow variables"):
                await variable_service.get_variable(user_id, RESERVED_NAME, "api_key", session)
            with pytest.raises(VariableNotFoundError):
                await variable_service.get_variable_object(user_id, RESERVED_NAME, session)
        value = await variable_service.get_variable(stored_variables.owner_id, NORMAL_NAME, "api_key", session)

    assert value.get_secret_value() == "ordinary-value"
    authz.get_resource_visibility.assert_not_awaited()


async def test_account_bulk_runtime_filters_reserved_names(variable_service, monkeypatch):
    from langflow.services.variable import service

    monkeypatch.setattr(
        service,
        "resolve_runtime_variables",
        AsyncMock(return_value={RESERVED_NAME: "registration-secret", NORMAL_NAME: "ordinary-value"}),
    )

    values = await variable_service.get_all_decrypted_variables("account", None)

    assert values == {NORMAL_NAME: "ordinary-value"}


@pytest.mark.parametrize("account_bound", [False, True])
async def test_mcp_discovery_does_not_receive_registration_values(stored_variables, monkeypatch, account_bound):
    from langflow.api.v2 import mcp
    from langflow.services.variable import runtime_policy

    @asynccontextmanager
    async def clients():
        yield None, None

    update_tools = AsyncMock(return_value=("streamable_http", [object()], None))
    monkeypatch.setattr(mcp, "update_tools", update_tools)
    monkeypatch.setattr(mcp, "discovery_clients", clients)
    monkeypatch.setattr(
        mcp, "get_server_list", AsyncMock(return_value={"mcpServers": {"test": {"url": "https://example.com/mcp"}}})
    )
    monkeypatch.setattr(
        runtime_policy,
        "resolve_runtime_variables",
        AsyncMock(
            return_value={RESERVED_NAME: "registration-secret", NORMAL_NAME: "ordinary-value"}
            if account_bound
            else None
        ),
    )
    async with session_scope() as session:
        result = await mcp.get_servers(
            SimpleNamespace(id=stored_variables.owner_id, is_superuser=True),
            session,
            None,
            get_settings_service(),
            action_count=True,
        )

    assert result == [{"name": "test", "mode": "streamable_http", "toolsCount": 1}]
    for key in ("request_variables", "url_variables"):
        variables = update_tools.await_args.kwargs[key]
        assert RESERVED_NAME not in variables
        assert variables[NORMAL_NAME] == "ordinary-value"


@pytest.mark.parametrize("operation", ["create", "update", "fields", "rename", "delete", "delete_by_id"])
async def test_service_rejects_registration_mutations(stored_variables, variable_service, operation):
    async with session_scope() as session:
        if operation == "create":
            mutation = variable_service.create_variable(
                stored_variables.owner_id, RESERVED_NAME, "replacement", session=session
            )
        elif operation == "update":
            mutation = variable_service.update_variable(
                stored_variables.owner_id, RESERVED_NAME, "replacement", session
            )
        elif operation in {"fields", "rename"}:
            variable_id = stored_variables.reserved_id if operation == "fields" else stored_variables.ordinary_id
            update = VariableUpdate(id=variable_id, name="RENAMED" if operation == "fields" else RESERVED_NAME)
            mutation = variable_service.update_variable_fields(stored_variables.owner_id, variable_id, update, session)
        elif operation == "delete":
            mutation = variable_service.delete_variable(stored_variables.owner_id, RESERVED_NAME, session)
        else:
            mutation = variable_service.delete_variable_by_id(
                stored_variables.owner_id, stored_variables.reserved_id, session
            )
        with pytest.raises(ValueError, match="managed from Connections settings"):
            await mutation


async def test_ordinary_variable_remains_editable(client, stored_variables, logged_in_headers_super_user):
    response = await client.patch(
        f"api/v1/variables/{stored_variables.ordinary_id}",
        headers=logged_in_headers_super_user,
        json={"id": str(stored_variables.ordinary_id), "name": "RENAMED", "value": "updated"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "RENAMED"
    response = await client.delete(
        f"api/v1/variables/{stored_variables.ordinary_id}", headers=logged_in_headers_super_user
    )
    assert response.status_code == 204


@pytest.mark.usefixtures("stored_variables")
async def test_dedicated_registration_api_remains_available(client, logged_in_headers_super_user):
    response = await client.get("api/v1/connections/oauth/registrations/saved", headers=logged_in_headers_super_user)

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["registrations"]] == ["google-work"]
