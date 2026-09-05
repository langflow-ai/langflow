"""Route-level tests for the pre-creation hook call points.

Covers the ``project`` hook (POST /projects/, the create branch of
PUT /projects/{id}, and POST /projects/upload/), the ``user`` hook
(POST /users/, both the admin flow and public signup) and the ``role`` hook
(POST /authz/roles).

Testing library and framework: pytest
"""

import io
import json
import zipfile
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Response, status
from httpx import AsyncClient
from langflow.services.creation_hooks import (
    ERROR_CODE_HEADER,
    RESOURCE_PROJECT,
    RESOURCE_ROLE,
    RESOURCE_USER,
    PreCreationContext,
    PreCreationDenied,
    _pre_creation_hooks,
    register_pre_creation_hook,
)
from langflow.services.database.models.auth import AuthzRole
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select

NEW_CREDENTIAL = "new" + "password123"
LIMIT_MESSAGE = "Your plan allows 3 projects."
LIMIT_DETAILS = {"resource": "projects", "limit": 3, "current": 3, "tier": "trial"}


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = {resource: list(hooks) for resource, hooks in _pre_creation_hooks.items()}
    yield
    for resource, hooks in saved.items():
        _pre_creation_hooks[resource][:] = hooks


@pytest.fixture
def seen_contexts() -> list[PreCreationContext]:
    return []


def _register_denying_hook(resource: str, seen: list[PreCreationContext]) -> None:
    async def deny(context: PreCreationContext) -> None:
        seen.append(context)
        raise PreCreationDenied(LIMIT_MESSAGE, details=LIMIT_DETAILS)

    register_pre_creation_hook(resource, deny)


def _register_http_refusing_hook(resource: str, *, status_code: int = 429) -> None:
    """A hook that answers with its own response instead of a PreCreationDenied."""

    async def refuse(_context: PreCreationContext) -> None:
        raise HTTPException(
            status_code=status_code,
            detail={"error_code": "tier_limit_reached", "message": LIMIT_MESSAGE},
            headers={ERROR_CODE_HEADER: "tier_limit_reached"},
        )

    register_pre_creation_hook(resource, refuse)


def _deny_rows(audit: AsyncMock) -> list[dict[str, Any]]:
    """The audit rows the route wrote with ``result="deny"``."""
    return [call.kwargs for call in audit.await_args_list if call.kwargs.get("result") == "deny"]


def _register_crashing_hook(resource: str) -> None:
    async def broken(_context: PreCreationContext) -> None:
        msg = "hook is broken"
        raise RuntimeError(msg)

    register_pre_creation_hook(resource, broken)


def _assert_denial_response(response) -> None:
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers[ERROR_CODE_HEADER] == "tier_limit_reached"
    assert response.json()["detail"] == {
        "error_code": "tier_limit_reached",
        "message": LIMIT_MESSAGE,
        **LIMIT_DETAILS,
    }


# =====================================================================
# project
# =====================================================================


@pytest.fixture
def basic_project() -> dict[str, Any]:
    return {"name": "Hooked Project", "description": "", "flows_list": [], "components_list": []}


async def test_create_project_denied_by_hook(client: AsyncClient, logged_in_headers, basic_project, seen_contexts):
    _register_denying_hook(RESOURCE_PROJECT, seen_contexts)

    response = await client.post("api/v1/projects/", json=basic_project, headers=logged_in_headers)

    _assert_denial_response(response)
    assert len(seen_contexts) == 1
    assert seen_contexts[0].resource == RESOURCE_PROJECT
    assert seen_contexts[0].requested_name == "Hooked Project"
    assert seen_contexts[0].actor_user_id is not None
    assert seen_contexts[0].session is not None

    async with session_scope() as session:
        rows = (await session.exec(select(Folder).where(Folder.name == "Hooked Project"))).all()
    assert rows == []


async def test_upsert_project_create_branch_denied_by_hook(
    client: AsyncClient, logged_in_headers, basic_project, seen_contexts
):
    _register_denying_hook(RESOURCE_PROJECT, seen_contexts)
    project_id = str(uuid4())

    response = await client.put(f"api/v1/projects/{project_id}", json=basic_project, headers=logged_in_headers)

    _assert_denial_response(response)
    async with session_scope() as session:
        assert await session.get(Folder, UUID(project_id)) is None


async def test_upload_project_denied_by_hook(client: AsyncClient, logged_in_headers, seen_contexts):
    _register_denying_hook(RESOURCE_PROJECT, seen_contexts)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("hooked-flow.json", json.dumps({"name": "hooked-flow", "description": "", "data": {}}))
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": ("Uploaded Project.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )

    # The upload route builds the Folder itself instead of going through ``_new_project``:
    # without its own hook call the project limit would be bypassable by uploading an export.
    _assert_denial_response(response)
    assert len(seen_contexts) == 1
    assert seen_contexts[0].requested_name == "Uploaded Project"

    async with session_scope() as session:
        rows = (await session.exec(select(Folder).where(Folder.name == "Uploaded Project"))).all()
    assert rows == []


async def test_create_project_survives_a_crashing_hook(client: AsyncClient, logged_in_headers, basic_project):
    """A hook that raises anything but PreCreationDenied or an HTTPException fails open."""
    _register_crashing_hook(RESOURCE_PROJECT)

    response = await client.post("api/v1/projects/", json=basic_project, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED


async def test_create_project_honours_an_http_exception_from_a_hook(client: AsyncClient, logged_in_headers):
    """A hook may refuse with its own response; fail-open must not swallow it.

    LE-2488's enterprise hook is described as raising an HTTPException directly, so a
    deliberate refusal in that shape has to reach the client verbatim.
    """
    _register_http_refusing_hook(RESOURCE_PROJECT)

    response = await client.post(
        "api/v1/projects/",
        json={"name": "Refused Project", "description": "", "flows_list": [], "components_list": []},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.headers[ERROR_CODE_HEADER] == "tier_limit_reached"
    async with session_scope() as session:
        assert (await session.exec(select(Folder).where(Folder.name == "Refused Project"))).all() == []


# =====================================================================
# user
# =====================================================================


async def test_public_signup_denied_by_hook(client: AsyncClient, seen_contexts):
    _register_denying_hook(RESOURCE_USER, seen_contexts)
    async with session_scope() as session:
        folders_before = len((await session.exec(select(Folder))).all())

    response = await client.post("api/v1/users/", json={"username": "hookeduser", "password": NEW_CREDENTIAL})

    _assert_denial_response(response)
    assert len(seen_contexts) == 1
    assert seen_contexts[0].resource == RESOURCE_USER
    assert seen_contexts[0].requested_name == "hookeduser"
    assert seen_contexts[0].is_public_signup is True

    async with session_scope() as session:
        assert (await session.exec(select(User).where(User.username == "hookeduser"))).first() is None
        # The denial rolls back before any write, so no default project is left behind either.
        assert len((await session.exec(select(Folder))).all()) == folders_before


async def test_admin_add_user_denied_by_hook(client: AsyncClient, logged_in_headers_super_user, seen_contexts):
    _register_denying_hook(RESOURCE_USER, seen_contexts)

    response = await client.post(
        "api/v1/users/",
        json={"username": "hookedadminuser", "password": NEW_CREDENTIAL},
        headers=logged_in_headers_super_user,
    )

    _assert_denial_response(response)
    assert seen_contexts[0].is_public_signup is False
    assert seen_contexts[0].actor_user_id is not None


async def test_user_denial_writes_an_audit_deny_row(client: AsyncClient, seen_contexts, monkeypatch):
    """The denial path audits the refusal, naming the actor snapshotted before the rollback."""
    from langflow.api.v1 import users

    audit = AsyncMock()
    monkeypatch.setattr(users, "audit_decision", audit)
    _register_denying_hook(RESOURCE_USER, seen_contexts)

    response = await client.post("api/v1/users/", json={"username": "auditeduser", "password": NEW_CREDENTIAL})

    _assert_denial_response(response)
    rows = _deny_rows(audit)
    assert len(rows) == 1
    assert rows[0]["action"] == "user:create"
    assert rows[0]["obj"] == "user:*"
    assert rows[0]["details"]["reason"] == "tier_limit_reached"
    assert rows[0]["details"]["status_code"] == 403
    # Public signup has no authenticated actor; the snapshot is taken all the same.
    assert rows[0]["user_id"] is None


async def test_user_creation_honours_an_http_exception_from_a_hook(client: AsyncClient, monkeypatch):
    """A hook's own response is passed through, and the refusal is still rolled back and audited."""
    from langflow.api.v1 import users

    audit = AsyncMock()
    monkeypatch.setattr(users, "audit_decision", audit)
    _register_http_refusing_hook(RESOURCE_USER)

    response = await client.post("api/v1/users/", json={"username": "refuseduser", "password": NEW_CREDENTIAL})

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.headers[ERROR_CODE_HEADER] == "tier_limit_reached"
    rows = _deny_rows(audit)
    assert len(rows) == 1
    assert rows[0]["details"]["status_code"] == 429
    assert rows[0]["details"]["reason"] == "tier_limit_reached"
    async with session_scope() as session:
        assert (await session.exec(select(User).where(User.username == "refuseduser"))).first() is None


async def test_user_creation_survives_a_crashing_hook(client: AsyncClient):
    _register_crashing_hook(RESOURCE_USER)

    response = await client.post("api/v1/users/", json={"username": "survivinguser", "password": NEW_CREDENTIAL})

    assert response.status_code == status.HTTP_201_CREATED


async def test_project_hook_does_not_gate_the_default_project(client: AsyncClient, seen_contexts):
    """``get_or_create_default_folder`` is not an API creation and must stay unhooked."""
    _register_denying_hook(RESOURCE_PROJECT, seen_contexts)

    response = await client.post("api/v1/users/", json={"username": "defaultfolderuser", "password": NEW_CREDENTIAL})

    assert response.status_code == status.HTTP_201_CREATED
    assert seen_contexts == []
    async with session_scope() as session:
        created = (await session.exec(select(User).where(User.username == "defaultfolderuser"))).first()
        assert created is not None
        folders = (await session.exec(select(Folder).where(Folder.user_id == created.id))).all()
    assert folders, "the new user's default project must still be created"


# =====================================================================
# role
# =====================================================================


class _FakeAsyncSession:
    """Minimal async-session stand-in that records writes, commits and rollbacks."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = 0

    async def get(self, _model: type, _key: UUID, **_kwargs: Any) -> Any:
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def refresh(self, _obj: Any) -> None:
        return None


class _StubAuthz:
    async def acquire_identity_mutation_lock(self, *, session, **_request) -> None:
        del session

    async def stage_identity_mutation(self, *, session, event) -> None:
        del session, event

    async def identity_mutation_committed(self, event) -> None:
        del event

    async def can_administer(self, *, user_id: UUID, resource: str) -> bool:
        del user_id, resource
        return True

    async def is_enabled(self) -> bool:
        return False


@pytest.fixture
def role_route(monkeypatch):
    from langflow.api.v1 import authz_roles

    monkeypatch.setattr(authz_roles, "get_authorization_service", lambda: _StubAuthz())
    return authz_roles


async def test_create_role_denied_by_hook(role_route, seen_contexts):
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    _register_denying_hook(RESOURCE_ROLE, seen_contexts)
    session = _FakeAsyncSession()
    user = SimpleNamespace(id=uuid4(), is_superuser=True, username="admin")
    payload = RoleCreate(name="capped", description=None, permissions=["flow:read"])

    with pytest.raises(HTTPException) as excinfo:
        await role_route.create_role(payload=payload, current_user=user, session=session, response=Response())

    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
    assert excinfo.value.headers == {ERROR_CODE_HEADER: "tier_limit_reached"}
    assert excinfo.value.detail["message"] == LIMIT_MESSAGE
    assert session.added == []
    assert session.committed == 0
    # The actor id is snapshotted before the rollback, so the audit row can name it.
    assert session.rolled_back == 1
    assert seen_contexts[0].resource == RESOURCE_ROLE
    assert seen_contexts[0].requested_name == "capped"
    assert seen_contexts[0].actor_user_id == user.id


async def test_create_role_survives_a_crashing_hook(role_route):
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    _register_crashing_hook(RESOURCE_ROLE)
    session = _FakeAsyncSession()
    user = SimpleNamespace(id=uuid4(), is_superuser=True, username="admin")
    payload = RoleCreate(name="uncapped", description=None, permissions=["flow:read"])

    result = await role_route.create_role(payload=payload, current_user=user, session=session, response=Response())

    assert result.name == "uncapped"
    assert len(session.added) == 1
    assert session.committed == 1


async def test_create_role_denied_by_hook_over_http(
    client: AsyncClient, logged_in_headers_super_user, seen_contexts, monkeypatch
):
    """The role denial over the real route: status, header, body, no row, audit row.

    The direct-call test above pins the rollback and the context; this one pins what the
    caller actually receives once FastAPI has rendered the mapped HTTPException.
    """
    from langflow.api.v1 import authz_roles

    audit = AsyncMock()
    monkeypatch.setattr(authz_roles, "audit_decision", audit)
    _register_denying_hook(RESOURCE_ROLE, seen_contexts)

    response = await client.post(
        "api/v1/authz/roles/",
        json={"name": "capped-role", "permissions": ["flow:read"]},
        headers=logged_in_headers_super_user,
    )

    _assert_denial_response(response)
    assert seen_contexts[0].resource == RESOURCE_ROLE
    assert seen_contexts[0].requested_name == "capped-role"
    assert seen_contexts[0].actor_user_id is not None

    async with session_scope() as session:
        assert (await session.exec(select(AuthzRole).where(AuthzRole.name == "capped-role"))).first() is None

    rows = _deny_rows(audit)
    assert len(rows) == 1
    assert rows[0]["action"] == "role:create"
    assert rows[0]["details"]["reason"] == "tier_limit_reached"
    assert rows[0]["details"]["status_code"] == 403
    assert rows[0]["user_id"] is not None
