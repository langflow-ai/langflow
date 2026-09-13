"""HTTP coverage for production authorization and isolated plugin route guards.

Casbin-service cases use real identities, committed grants, and database writes.
The compatibility cases retain :class:`PolicyTestAuthorizationService`
(see ``_policy_double``) as an interface-isolation fixture and exercise the
*real* flow routes over HTTP, validating that:

* the per-route guards (``ensure_flow_permission`` via the ``Authorized*Flow``
  dependencies) actually gate read/write/delete/create/execute by role,
* cross-user denials are masked as 404 (not 403) on fetch routes, while
  write and delete denials on readable flows return an explicit 403,
* the share-aware fetch + ``authz_share`` rows grant cross-user access, and
* domain resolution (``_resolve_authz_domain``) scopes a domain-bound grant.

Removing a guard or regressing domain resolution flips one of these assertions.
Everything runs against the OSS package only — no EE Casbin enforcer required.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from langflow.api.v1.knowledge_bases import KBStorageHelper
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.authorization.casbin.service import CasbinAuthorizationService
from langflow.services.database.models.auth import AuthzTeam
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import (
    get_auth_service,
    get_authorization_service,
    get_settings_service,
    session_scope,
)

from ._policy_double import (
    assign_role,
    create_user_share,
    install_policy_authz,
    seed_system_roles,
)

_PASSWORD = "testpassword"  # noqa: S105 — test-only credential  # pragma: allowlist secret


@pytest.fixture
def casbin_authorization(client, monkeypatch):  # noqa: ARG001 - initialize the real application before enabling authz
    """Use the application's registered production service, never the policy double."""
    service = get_authorization_service()
    assert type(service) is CasbinAuthorizationService
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_DURABLE", True)
    return service


async def _make_user(username: str) -> UUID:
    """Insert an active, non-superuser user and return its id."""
    async with session_scope() as session:
        user = User(username=username, password=get_auth_service().get_password_hash(_PASSWORD), is_active=True)
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
    return user_id


async def _login(client, username: str) -> dict[str, str]:
    """Log in and return an Authorization header for ``username``."""
    response = await client.post("api/v1/login", data={"username": username, "password": _PASSWORD})
    assert response.status_code == 200, f"login failed for {username}: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _make_flow(owner_id: UUID, name: str, *, workspace_id: UUID | None = None) -> UUID:
    """Insert a valid project-backed flow owned by ``owner_id`` and return its id."""
    async with session_scope() as session:
        project = Folder(name=f"{name}_project", user_id=owner_id, workspace_id=workspace_id)
        session.add(project)
        await session.flush()
        flow = Flow(
            name=name,
            user_id=owner_id,
            folder_id=project.id,
            workspace_id=project.workspace_id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        await session.commit()
    return flow_id


async def _make_project(owner_id: UUID, name: str, *, workspace_id: UUID | None = None) -> UUID:
    """Insert a project owned by ``owner_id`` and return its id."""
    async with session_scope() as session:
        project = Folder(name=name, user_id=owner_id, workspace_id=workspace_id)
        session.add(project)
        await session.flush()
        assert project.id is not None
        project_id = project.id
        await session.commit()
    return project_id


async def _seed_roles() -> dict[str, UUID]:
    async with session_scope() as session:
        return await seed_system_roles(session)


async def _role_user(
    client,
    role_name: str,
    role_ids: dict[str, UUID],
    *,
    domain_type: str = "global",
    domain_id: UUID | None = None,
) -> tuple[UUID, dict[str, str]]:
    """Create a user, assign ``role_name`` (optionally domain-scoped), return (id, headers)."""
    username = f"{role_name}_{uuid4().hex}"
    user_id = await _make_user(username)
    async with session_scope() as session:
        await assign_role(
            session,
            user_id=user_id,
            role_id=role_ids[role_name],
            domain_type=domain_type,
            domain_id=domain_id,
        )
    headers = await _login(client, username)
    return user_id, headers


# --------------------------------------------------------------------------- #
# Role matrix (Phase 1.11): viewer / developer / admin on flow routes.
# Flows are owned by a separate user so the guards' owner-override does not mask
# the role decision — these assertions exercise the *role*, not ownership.
# --------------------------------------------------------------------------- #


async def test_viewer_can_read_and_execute_but_not_write_delete_or_create(client):
    role_ids = await _seed_roles()
    owner_id = await _make_user(f"owner_{uuid4().hex}")
    flow_id = await _make_flow(owner_id, f"flow_{uuid4().hex}")
    _viewer_id, headers = await _role_user(client, "viewer", role_ids)

    with install_policy_authz(get_settings_service()):
        # read -> allowed
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=headers)).status_code == 200
        # execute (build) -> allowed (viewer has flow:execute)
        build = await client.post(f"api/v1/build/{flow_id}/flow", headers=headers, json={})
        assert build.status_code == 200, build.text
        # write -> denied, but the flow is readable so return an edit-permission 403.
        patch = await client.patch(f"api/v1/flows/{flow_id}", headers=headers, json={"name": f"x_{uuid4().hex}"})
        assert patch.status_code == 403
        assert patch.json()["detail"] == "You don't have permission to edit this flow."
        # delete -> denied, but the flow is readable so return a delete-permission 403.
        delete = await client.delete(f"api/v1/flows/{flow_id}", headers=headers)
        assert delete.status_code == 403
        assert delete.json()["detail"] == "You don't have permission to delete this flow."
        # create into the *owner's* project -> denied; 403 is correct here (no
        # existing resource UUID to protect).
        owner_project_id = await _make_project(owner_id, f"owner_project_{uuid4().hex}")
        create_elsewhere = await client.post(
            "api/v1/flows/",
            headers=headers,
            json={
                "name": f"new_{uuid4().hex}",
                "data": {"nodes": [], "edges": []},
                "folder_id": str(owner_project_id),
            },
        )
        assert create_elsewhere.status_code == 403
        # create into a project the viewer owns -> allowed by owner override.
        # Ownership is checked before any policy rule, and a project is the
        # only ownership a not-yet-created flow can inherit. Without this a
        # read-only role cannot use the default project created for them
        # (LE-1905 finding 11).
        create_own = await client.post(
            "api/v1/flows/", headers=headers, json={"name": f"new_{uuid4().hex}", "data": {"nodes": [], "edges": []}}
        )
        assert create_own.status_code == 201, create_own.text


async def test_developer_can_write_and_create_but_not_delete(client):
    role_ids = await _seed_roles()
    owner_id = await _make_user(f"owner_{uuid4().hex}")
    flow_id = await _make_flow(owner_id, f"flow_{uuid4().hex}")
    _dev_id, headers = await _role_user(client, "developer", role_ids)

    with install_policy_authz(get_settings_service()):
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=headers)).status_code == 200
        # write someone else's flow -> allowed via the developer role (not ownership)
        patch = await client.patch(f"api/v1/flows/{flow_id}", headers=headers, json={"name": f"renamed_{uuid4().hex}"})
        assert patch.status_code == 200, patch.text
        # create -> allowed
        create = await client.post(
            "api/v1/flows/", headers=headers, json={"name": f"dev_{uuid4().hex}", "data": {"nodes": [], "edges": []}}
        )
        assert create.status_code == 201, create.text
        # delete -> denied (developer lacks flow:delete) but readable -> 403
        delete = await client.delete(f"api/v1/flows/{flow_id}", headers=headers)
        assert delete.status_code == 403
        assert delete.json()["detail"] == "You don't have permission to delete this flow."


async def test_admin_has_full_flow_access(client):
    role_ids = await _seed_roles()
    owner_id = await _make_user(f"owner_{uuid4().hex}")
    flow_id = await _make_flow(owner_id, f"flow_{uuid4().hex}")
    _admin_id, headers = await _role_user(client, "admin", role_ids)

    with install_policy_authz(get_settings_service()):
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=headers)).status_code == 200
        patch = await client.patch(f"api/v1/flows/{flow_id}", headers=headers, json={"name": f"a_{uuid4().hex}"})
        assert patch.status_code == 200, patch.text
        create = await client.post(
            "api/v1/flows/", headers=headers, json={"name": f"adm_{uuid4().hex}", "data": {"nodes": [], "edges": []}}
        )
        assert create.status_code == 201, create.text
        # delete -> allowed (admin has flow:delete)
        delete = await client.delete(f"api/v1/flows/{flow_id}", headers=headers)
        assert delete.status_code == 200, delete.text
        # the flow is gone -> now 404 for everyone (sanity)
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=headers)).status_code == 404


# --------------------------------------------------------------------------- #
# Share lifecycle (Phase 3.13): Alice shares a flow with Bob.
# --------------------------------------------------------------------------- #


async def test_share_grants_cross_user_access_and_absence_is_404(client):
    settings = get_settings_service()
    alice_id = await _make_user(f"alice_{uuid4().hex}")
    bob_username = f"bob_{uuid4().hex}"
    bob_id = await _make_user(bob_username)
    flow_id = await _make_flow(alice_id, f"aliceflow_{uuid4().hex}")
    bob_headers = await _login(client, bob_username)

    # Without a share, Bob cannot reach Alice's flow at all — and the denial is a
    # 404 (UUID-privacy mask), not a 403, on every fetch route.
    with install_policy_authz(settings):
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=bob_headers)).status_code == 404
        assert (
            await client.patch(f"api/v1/flows/{flow_id}", headers=bob_headers, json={"name": "x"})
        ).status_code == 404
        assert (await client.delete(f"api/v1/flows/{flow_id}", headers=bob_headers)).status_code == 404
        assert (await client.post(f"api/v1/build/{flow_id}/flow", headers=bob_headers, json={})).status_code == 404

    # Alice grants Bob an admin-level share (read + write + execute).
    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="flow",
            resource_id=flow_id,
            target_user_id=bob_id,
            permission_level="admin",
            created_by=alice_id,
        )

    with install_policy_authz(settings):
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=bob_headers)).status_code == 200
        patch = await client.patch(f"api/v1/flows/{flow_id}", headers=bob_headers, json={"name": f"bob_{uuid4().hex}"})
        assert patch.status_code == 200, patch.text
        build = await client.post(f"api/v1/build/{flow_id}/flow", headers=bob_headers, json={})
        assert build.status_code == 200, build.text


async def test_read_only_share_allows_get_but_denies_write_and_execute(client):
    """A read-level share grants GET but neither PATCH nor build — permission_level is enforced, not mere presence."""
    settings = get_settings_service()
    alice_id = await _make_user(f"alice_{uuid4().hex}")
    bob_username = f"bob_{uuid4().hex}"
    bob_id = await _make_user(bob_username)
    flow_id = await _make_flow(alice_id, f"aliceflow_{uuid4().hex}")
    bob_headers = await _login(client, bob_username)

    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="flow",
            resource_id=flow_id,
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    with install_policy_authz(settings):
        assert (await client.get(f"api/v1/flows/{flow_id}", headers=bob_headers)).status_code == 200
        # write is not granted by a read-level share, but the flow is readable
        # so return an edit-permission 403 instead of a "not found" mask.
        patch = await client.patch(f"api/v1/flows/{flow_id}", headers=bob_headers, json={"name": "nope"})
        assert patch.status_code == 403
        assert patch.json()["detail"] == "You don't have permission to edit this flow."
        # delete is likewise denied on a readable flow -> delete-permission 403,
        # matching the write behavior (LE-1738 B9: a flow the caller can GET must
        # not flip to 404 on a denied DELETE).
        delete = await client.delete(f"api/v1/flows/{flow_id}", headers=bob_headers)
        assert delete.status_code == 403
        assert delete.json()["detail"] == "You don't have permission to delete this flow."
        # execute is modeled independently from write — a read-level share must
        # not grant build either -> deny -> 404
        build = await client.post(f"api/v1/build/{flow_id}/flow", headers=bob_headers, json={})
        # execute -> denied. Bob can read this flow, so answering "not found"
        # would hide a resource he has already opened and send him to debug a
        # flow id that is correct (LE-1905 finding 8).
        assert build.status_code == 403
        assert build.json()["detail"] == "You don't have permission to execute this flow."


# --------------------------------------------------------------------------- #
# Flow create destinations: plugin grants may target a foreign-owned project,
# while the OSS pass-through must keep its existing owner-scoped fallback.
# --------------------------------------------------------------------------- #


async def test_project_scoped_developer_can_create_flow_in_foreign_project(client):
    """A plugin-authorized non-owner must retain the project destination it was granted."""
    role_ids = await _seed_roles()
    project_owner_id = await _make_user(f"project_owner_{uuid4().hex}")
    workspace_id = uuid4()
    project_id = await _make_project(
        project_owner_id,
        f"shared_project_{uuid4().hex}",
        workspace_id=workspace_id,
    )
    developer_id, headers = await _role_user(
        client,
        "developer",
        role_ids,
        domain_type="project",
        domain_id=project_id,
    )

    with install_policy_authz(get_settings_service()):
        response = await client.post(
            "api/v1/flows/",
            headers=headers,
            json={
                "name": f"shared_project_flow_{uuid4().hex}",
                "folder_id": str(project_id),
                "data": {"nodes": [], "edges": []},
            },
        )
        assert response.status_code == 201, response.text
        created = response.json()
        edit = await client.patch(
            f"api/v1/flows/{created['id']}",
            headers=headers,
            json={"name": f"edited_shared_project_flow_{uuid4().hex}"},
        )
        upload = await client.post(
            "api/v1/flows/upload/",
            headers=headers,
            files={
                "file": (
                    "shared-project-flow.json",
                    json.dumps(
                        {
                            "id": created["id"],
                            "name": f"uploaded_shared_project_flow_{uuid4().hex}",
                        }
                    ),
                    "application/json",
                )
            },
        )

    assert created["user_id"] == str(developer_id)
    assert created["folder_id"] == str(project_id)
    assert created["workspace_id"] == str(workspace_id)
    assert edit.status_code == 200, edit.text
    assert edit.json()["folder_id"] == str(project_id)
    assert edit.json()["workspace_id"] == str(workspace_id)
    assert upload.status_code == 201, upload.text
    assert upload.json()[0]["id"] == created["id"]
    assert upload.json()[0]["folder_id"] == str(project_id)
    assert upload.json()[0]["workspace_id"] == str(workspace_id)


async def test_disabled_registered_authz_rejects_explicit_foreign_project(client, casbin_authorization):
    """Disabled enforcement never redirects an explicit foreign destination."""
    project_owner_id = await _make_user(f"project_owner_{uuid4().hex}")
    foreign_project_id = await _make_project(project_owner_id, f"foreign_project_{uuid4().hex}")
    creator_username = f"creator_{uuid4().hex}"
    await _make_user(creator_username)
    headers = await _login(client, creator_username)

    settings = get_settings_service()
    authz = get_authorization_service()
    assert authz is casbin_authorization
    assert await authz.supports_cross_user_fetch() is True
    saved_authz_enabled = settings.auth_settings.AUTHZ_ENABLED
    settings.auth_settings.AUTHZ_ENABLED = False
    try:
        response = await client.post(
            "api/v1/flows/",
            headers=headers,
            json={
                "name": f"oss_owner_scoped_flow_{uuid4().hex}",
                "folder_id": str(foreign_project_id),
                "data": {"nodes": [], "edges": []},
            },
        )
    finally:
        settings.auth_settings.AUTHZ_ENABLED = saved_authz_enabled

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Folder not found"


async def test_cross_user_destination_resolution_requires_create_permission_for_move(client):
    """Resolving a foreign destination cannot bypass destination authorization."""
    project_owner_id = await _make_user(f"move_project_owner_{uuid4().hex}")
    foreign_project_id = await _make_project(project_owner_id, f"move_target_{uuid4().hex}")
    creator_username = f"move_creator_{uuid4().hex}"
    await _make_user(creator_username)
    headers = await _login(client, creator_username)

    create = await client.post(
        "api/v1/flows/",
        headers=headers,
        json={"name": f"move_source_{uuid4().hex}", "data": {"nodes": [], "edges": []}},
    )
    assert create.status_code == 201, create.text
    original_folder_id = create.json()["folder_id"]

    with install_policy_authz(get_settings_service()):
        move = await client.patch(
            f"api/v1/flows/{create.json()['id']}",
            headers=headers,
            json={"folder_id": str(foreign_project_id)},
        )

    assert move.status_code == 404, move.text
    assert move.json()["detail"] == "Flow not found"
    async with session_scope() as session:
        unchanged = await session.get(Flow, UUID(create.json()["id"]))
    assert unchanged is not None
    assert str(unchanged.folder_id) == original_folder_id


# --------------------------------------------------------------------------- #
# Domain resolution: a workspace-scoped grant must only apply in its workspace.
# --------------------------------------------------------------------------- #


async def test_domain_scoped_role_applies_only_in_matching_domain(client):
    role_ids = await _seed_roles()
    owner_id = await _make_user(f"owner_{uuid4().hex}")
    workspace_a = uuid4()
    workspace_b = uuid4()
    flow_a = await _make_flow(owner_id, f"a_{uuid4().hex}", workspace_id=workspace_a)
    flow_b = await _make_flow(owner_id, f"b_{uuid4().hex}", workspace_id=workspace_b)
    async with session_scope() as session:
        flow_a_row = await session.get(Flow, flow_a)
        flow_b_row = await session.get(Flow, flow_b)
    assert flow_a_row is not None
    assert flow_a_row.folder_id is not None
    assert flow_b_row is not None
    assert flow_b_row.folder_id is not None
    # The project domain is the most specific canonical scope for a
    # project-backed flow. A viewer grant on project A must not bleed into B.
    _viewer_id, headers = await _role_user(
        client,
        "viewer",
        role_ids,
        domain_type="project",
        domain_id=flow_a_row.folder_id,
    )

    with install_policy_authz(get_settings_service()):
        # flow A resolves to project A -> grant covers -> read allowed.
        assert (await client.get(f"api/v1/flows/{flow_a}", headers=headers)).status_code == 200
        # flow B resolves to project B -> the project-A grant does not cover it.
        assert (await client.get(f"api/v1/flows/{flow_b}", headers=headers)).status_code == 404


# --------------------------------------------------------------------------- #
# File / Knowledge Base create guards (QA BUG-2).
# Create has no existing resource owner, so the prospective owner must not
# trigger the existing-resource owner override before the policy service runs.
# --------------------------------------------------------------------------- #


def _knowledge_base_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
        "embedding_provider": "OpenAI",
        "embedding_model": "text-embedding-3-small",
        "backend_type": "chroma",
        "backend_config": {},
    }


async def test_roleless_user_cannot_create_files_or_knowledge_bases(client, monkeypatch, tmp_path):
    username = f"roleless_{uuid4().hex}"
    await _make_user(username)
    headers = await _login(client, username)

    monkeypatch.setattr(KBStorageHelper, "get_root_path", lambda: tmp_path)
    monkeypatch.setattr(KBStorageHelper, "get_fresh_chroma_client", lambda _path: MagicMock())
    monkeypatch.setattr(KBStorageHelper, "release_chroma_resources", lambda _path: None)

    with install_policy_authz(get_settings_service()):
        upload = await client.post(
            "api/v2/files",
            headers=headers,
            files={"file": ("roleless.txt", b"not allowed", "text/plain")},
        )
        test_connection = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=headers,
            json={"backend_type": "chroma", "backend_config": {}},
        )
        create = await client.post(
            "api/v1/knowledge_bases",
            headers=headers,
            json=_knowledge_base_payload(f"Roleless_{uuid4().hex}"),
        )
        preview = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=headers,
            files={"files": ("roleless.txt", b"not allowed", "text/plain")},
        )

        assert {
            "file upload": upload.status_code,
            "knowledge-base test connection": test_connection.status_code,
            "knowledge-base create": create.status_code,
            "knowledge-base preview chunks": preview.status_code,
        } == {
            "file upload": 403,
            "knowledge-base test connection": 403,
            "knowledge-base create": 403,
            "knowledge-base preview chunks": 403,
        }


async def test_developer_can_create_files_and_knowledge_bases(client, monkeypatch, tmp_path):
    role_ids = await _seed_roles()
    _developer_id, headers = await _role_user(client, "developer", role_ids)

    monkeypatch.setattr(KBStorageHelper, "get_root_path", lambda: tmp_path)
    chroma_client = MagicMock()
    monkeypatch.setattr(KBStorageHelper, "get_fresh_chroma_client", lambda _path: chroma_client)
    monkeypatch.setattr(KBStorageHelper, "release_chroma_resources", lambda _path: None)

    with install_policy_authz(get_settings_service()):
        upload = await client.post(
            "api/v2/files",
            headers=headers,
            files={"file": ("developer.txt", b"allowed", "text/plain")},
        )
        assert upload.status_code == 201, upload.text

        test_connection = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=headers,
            json={"backend_type": "chroma", "backend_config": {}},
        )
        assert test_connection.status_code == 200, test_connection.text

        create = await client.post(
            "api/v1/knowledge_bases",
            headers=headers,
            json=_knowledge_base_payload(f"Developer_{uuid4().hex}"),
        )
        assert create.status_code == 201, create.text

        preview = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=headers,
            files={"files": ("developer.txt", b"allowed", "text/plain")},
        )
        assert preview.status_code == 200, preview.text


@pytest.mark.parametrize("resource_type", ["flow", "project"])
@pytest.mark.parametrize("method", ["PATCH", "PUT"])
@pytest.mark.parametrize("no_op", [False, True])
async def test_casbin_collaborator_save_response_keeps_owner_credentials_private(
    client, casbin_authorization, resource_type, method, no_op, monkeypatch
):
    assert await casbin_authorization.is_enabled()
    owner_name, editor_name = f"owner_{uuid4().hex}", f"editor_{uuid4().hex}"
    owner_id, editor_id = await _make_user(owner_name), await _make_user(editor_name)
    owner_headers, editor_headers = await _login(client, owner_name), await _login(client, editor_name)
    secret = "synthetic-owner-credential-for-redaction"  # noqa: S105  # pragma: allowlist secret
    if resource_type == "flow":
        resource_id = await _make_flow(owner_id, f"SecretFlow_{uuid4().hex}")
        async with session_scope() as session:
            row = await session.get(Flow, resource_id)
            row.data = {
                "nodes": [
                    {
                        "id": "TextInput-secret",
                        "data": {
                            "type": "TextInput",
                            "node": {
                                "template": {"input_value": {"name": "input_value", "password": True, "value": secret}},
                            },
                        },
                    }
                ],
                "edges": [],
            }
            await session.commit()
        path = f"api/v1/flows/{resource_id}"
    else:
        resource_id = await _make_project(owner_id, f"SecretProject_{uuid4().hex}")
        async with session_scope() as session:
            row = await session.get(Folder, resource_id)
            row.auth_settings = encrypt_auth_settings({"auth_type": "apikey", "api_key": secret})
            await session.commit()
        path = f"api/v1/projects/{resource_id}"

    grant = await client.post(
        "api/v1/authz/shares",
        headers=owner_headers,
        json={
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "scope": "user",
            "target_id": str(editor_id),
            "permission_level": "write",
        },
    )
    assert grant.status_code == 201, grant.text
    observed = await client.get(path, headers=editor_headers)
    assert observed.status_code == 200, observed.text
    assert secret not in observed.text
    original = observed.json()
    payload = {"name": original["name"]}
    if not no_op:
        payload["description"] = "A collaborator's content edit"

    from langflow.services.authorization.casbin import store

    def content_must_not_compile(*_args, **_kwargs):
        pytest.fail("Content-only saves must not compile the complete authorization policy")

    # Scope this guard to content requests; shutdown can delete the unused
    # bootstrap identity and must reconcile that separate policy mutation.
    with monkeypatch.context() as content_patch:
        content_patch.setattr(store, "compile_policy", content_must_not_compile)
        saved = await client.request(
            method, path, headers={**editor_headers, "If-Match": observed.headers["etag"]}, json=payload
        )
        assert saved.status_code == 200, saved.text
        assert secret not in saved.text
        if resource_type == "project":
            assert saved.json()["auth_settings"] is None
        assert saved.json()["edit_revision"] == original["edit_revision"] + (0 if no_op else 1)
        owner_read = await client.get(path, headers=owner_headers)
        assert owner_read.status_code == 200, owner_read.text
        if resource_type == "flow":
            assert secret in owner_read.text
        else:
            assert owner_read.json()["auth_settings"] is not None


@pytest.mark.parametrize("resource_type", ["flow", "project"])
async def test_casbin_unready_service_rejects_owner_writes_and_permission_discovery(
    client, casbin_authorization, resource_type
):
    username = f"unready_owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)
    resource_id = await (
        _make_flow(owner_id, "Unready flow") if resource_type == "flow" else _make_project(owner_id, "Unready project")
    )
    path = f"api/v1/{'flows' if resource_type == 'flow' else 'projects'}/{resource_id}"
    observed = await client.get(path, headers=headers)
    assert observed.status_code == 200
    # Actual invalid canonical data makes the production readiness probe fail.
    invalid_team = AuthzTeam(team_name="Unrepaired legacy team", adom_name=uuid4().hex)
    async with session_scope() as session:
        session.add(invalid_team)
        await session.commit()
    try:
        assert await casbin_authorization.collaboration_ready() is False
        for write_headers in (headers, {**headers, "If-Match": observed.headers["etag"]}):
            saved = await client.patch(path, headers=write_headers, json={"description": "Must not persist"})
            assert saved.status_code == 503, saved.text
            assert saved.json()["detail"]["code"] == "AUTHORIZATION_NOT_READY"
        permissions = await client.post(
            "api/v1/authz/me/permissions",
            headers=headers,
            json={
                "resource_type": resource_type,
                "resource_ids": [str(resource_id)],
            },
        )
        assert permissions.status_code == 503, permissions.text
        async with session_scope() as session:
            stored = await session.get(Flow if resource_type == "flow" else Folder, resource_id)
            assert stored.description != "Must not persist"
            assert stored.edit_revision == observed.json()["edit_revision"]
    finally:
        # Remove the deliberately invalid test input before normal lifecycle
        # shutdown, which must reject rather than publish invalid policy.
        from langflow.services.authorization.casbin import store

        async with session_scope() as session:
            await store.acquire_writer_lock(session)
            await session.delete(await session.get(AuthzTeam, invalid_team.id))
            await store.reconcile_policy(session)


@pytest.mark.parametrize("resource_type", ["flow", "project"])
async def test_casbin_effective_permissions_never_invents_owner_actions(client, casbin_authorization, resource_type):
    assert await casbin_authorization.is_enabled()
    username = f"action_owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)
    resource_id = await (
        _make_flow(owner_id, "Action flow") if resource_type == "flow" else _make_project(owner_id, "Action project")
    )
    response = await client.post(
        "api/v1/authz/me/permissions",
        headers=headers,
        json={
            "resource_type": resource_type,
            "resource_ids": [str(resource_id)],
            "actions": ["read", "unknown", "execute"],
        },
    )
    assert response.status_code == 200, response.text
    allowed = response.json()["permissions"][str(resource_id)]
    assert "read" in allowed
    assert "unknown" not in allowed
    assert ("execute" in allowed) is (resource_type == "flow")


@pytest.mark.parametrize("operation", ["create", "rename", "delete"])
async def test_casbin_project_mcp_changes_rollback_with_the_project(
    client, casbin_authorization, monkeypatch, operation
):
    """A failure after MCP staging cannot commit project, server or credential changes."""
    from langflow.api.v1 import projects
    from langflow.services.database.models import MCPServer
    from langflow.services.database.models.api_key.model import ApiKey
    from sqlmodel import select

    assert await casbin_authorization.is_enabled()
    monkeypatch.setattr(get_settings_service().settings, "add_projects_to_mcp_servers", True)
    username = f"mcp_owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)
    name = f"mcp_{uuid4().hex[:8]}"
    created = await client.post("api/v1/projects/", headers=headers, json={"name": name})
    assert created.status_code == 201, created.text
    project_id = UUID(created.json()["id"])
    path = f"api/v1/projects/{project_id}"

    async def persisted():
        async with session_scope() as session:
            folders = (await session.exec(select(Folder).where(Folder.user_id == owner_id))).all()
            servers = (await session.exec(select(MCPServer).where(MCPServer.user_id == owner_id))).all()
            keys = (await session.exec(select(ApiKey.id).where(ApiKey.user_id == owner_id))).all()
            return (
                sorted((str(row.id), row.name, row.edit_revision) for row in folders),
                sorted((str(row.id), row.name, row.version) for row in servers),
                sorted(str(key) for key in keys),
            )

    before = await persisted()
    assert before[1], "The test must exercise an actual persisted MCP server"
    helper_name = {"create": "_new_project", "rename": "_apply_project_update", "delete": "cleanup_mcp_on_delete"}[
        operation
    ]
    original = getattr(projects, helper_name)

    async def fail_after_staging(*args, **kwargs):
        await original(*args, **kwargs)
        msg = "injected failure after MCP staging"
        raise RuntimeError(msg)

    monkeypatch.setattr(projects, helper_name, fail_after_staging)
    if operation == "create":
        failed = await client.post("api/v1/projects/", headers=headers, json={"name": name + " second"})
    else:
        observed = await client.get(path, headers=headers)
        write_headers = {**headers, "If-Match": observed.headers["etag"]}
        failed = await (
            client.patch(path, headers=write_headers, json={"name": name + " renamed"})
            if operation == "rename"
            else client.delete(path, headers=write_headers)
        )
    assert failed.status_code == 500, failed.text
    assert await persisted() == before


@pytest.mark.parametrize("resource_type", ["flow", "project"])
@pytest.mark.parametrize("audit_enabled", [False, True])
async def test_casbin_concurrent_writes_accept_exactly_one_observed_revision(
    client, casbin_authorization, monkeypatch, resource_type, audit_enabled
):
    assert await casbin_authorization.is_enabled()
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", audit_enabled)
    username = f"concurrent_owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)
    resource_id = await (
        _make_flow(owner_id, "Concurrent flow")
        if resource_type == "flow"
        else _make_project(owner_id, "Concurrent project")
    )
    path = f"api/v1/{'flows' if resource_type == 'flow' else 'projects'}/{resource_id}"
    observed = await client.get(path, headers=headers)
    assert observed.status_code == 200
    write_headers = {**headers, "If-Match": observed.headers["etag"]}
    outcomes = await asyncio.gather(
        *(
            client.patch(path, headers=write_headers, json={"description": description})
            for description in ("First edit", "Second edit")
        )
    )
    assert sorted(response.status_code for response in outcomes) == [200, 412], [response.text for response in outcomes]
    winner = next(response.json() for response in outcomes if response.status_code == 200)
    persisted = await client.get(path, headers=headers)
    assert persisted.status_code == 200
    assert persisted.json()["description"] == winner["description"]
    assert persisted.json()["edit_revision"] == observed.json()["edit_revision"] + 1


@pytest.mark.parametrize("resource_type", ["flow", "bulk_flow", "project"])
@pytest.mark.parametrize("audit_enabled", [False, True])
async def test_casbin_delete_cannot_remove_a_concurrently_updated_revision(
    client, casbin_authorization, monkeypatch, resource_type, audit_enabled
):
    assert await casbin_authorization.is_enabled()
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", audit_enabled)
    username = f"delete_race_owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)
    is_project = resource_type == "project"
    resource_id = await (
        _make_project(owner_id, "Delete race project") if is_project else _make_flow(owner_id, "Delete race flow")
    )
    path = f"api/v1/{'projects' if is_project else 'flows'}/{resource_id}"
    observed = await client.get(path, headers=headers)
    assert observed.status_code == 200, observed.text
    write_headers = {**headers, "If-Match": observed.headers["etag"]}
    if resource_type == "bulk_flow":
        delete = client.request(
            "DELETE",
            "api/v1/flows/",
            headers=headers,
            json={
                "flow_ids": [str(resource_id)],
                "expected_edit_revision": {str(resource_id): observed.json()["edit_revision"]},
            },
        )
    else:
        delete = client.delete(path, headers=write_headers)
    saved, deleted = await asyncio.gather(
        client.patch(path, headers=write_headers, json={"description": "Concurrent edit must survive stale deletion"}),
        delete,
    )
    if saved.status_code == 200:
        assert deleted.status_code == 412, deleted.text
        persisted = await client.get(path, headers=headers)
        assert persisted.status_code == 200, persisted.text
        assert persisted.json()["description"] == saved.json()["description"]
    else:
        assert saved.status_code == 404, saved.text
        assert deleted.status_code in {200, 204}, deleted.text
        assert (await client.get(path, headers=headers)).status_code == 404
