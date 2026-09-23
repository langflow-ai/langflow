"""End-to-end RBAC enforcement tests driven by an in-test allow/deny enforcer.

The OSS authorization service is a pass-through (``enforce()`` always allows and
``supports_cross_user_fetch()`` is False), so allow/deny semantics cannot be
asserted against it directly. These tests install :class:`PolicyTestAuthorizationService`
(see ``_policy_double``) with ``AUTHZ_ENABLED=True`` / ``AUTHZ_SUPERUSER_BYPASS=False``
and exercise the *real* flow routes over HTTP, validating that:

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

import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from langflow.api.v1.knowledge_bases import KBStorageHelper
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


async def _make_flow(
    owner_id: UUID,
    name: str,
    *,
    workspace_id: UUID | None = None,
    folder_id: UUID | None = None,
    data: dict | None = None,
    is_component: bool = False,
) -> UUID:
    """Insert a minimal flow owned by ``owner_id`` and return its id."""
    async with session_scope() as session:
        flow = Flow(
            name=name,
            user_id=owner_id,
            workspace_id=workspace_id,
            folder_id=folder_id,
            data=data if data is not None else {"nodes": [], "edges": []},
            is_component=is_component,
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
        assert (await client.delete(f"api/v1/flows/{flow_id}", headers=headers)).status_code == 200
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


async def test_shared_flow_reads_strip_owner_credentials_without_mutating_owner_view(client):
    """A share grants flow access, but never the owner's persisted password fields."""
    settings = get_settings_service()
    alice_username = f"alice_{uuid4().hex}"
    bob_username = f"bob_{uuid4().hex}"
    alice_id = await _make_user(alice_username)
    bob_id = await _make_user(bob_username)
    folder_id = await _make_project(alice_id, f"secrets_{uuid4().hex}")
    secret_value = "test-only-credential-value"  # noqa: S105  # pragma: allowlist secret
    flow_data = {
        "nodes": [
            {
                "id": "model-node",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {"name": "api_key", "password": True, "value": secret_value},
                            "model_name": {"name": "model_name", "value": "test-model"},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    flow_id = await _make_flow(
        alice_id, f"aliceflow_{uuid4().hex}", folder_id=folder_id, data=flow_data, is_component=True
    )
    alice_headers = await _login(client, alice_username)
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
        await create_user_share(
            session,
            resource_type="project",
            resource_id=folder_id,
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    def value(response):
        assert response.status_code == 200, response.text
        return response.json()["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]

    with install_policy_authz(settings):
        assert value(await client.get(f"api/v1/flows/{flow_id}", headers=alice_headers)) == secret_value
        assert value(await client.get(f"api/v1/flows/{flow_id}", headers=bob_headers)) is None

        listed = await client.get("api/v1/flows/", headers=bob_headers)
        assert listed.status_code == 200, listed.text
        shared = next(flow for flow in listed.json() if flow["id"] == str(flow_id))
        assert shared["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None

        headers = await client.get("api/v1/flows/", headers=bob_headers, params={"header_flows": "true"})
        assert headers.status_code == 200, headers.text
        shared_header = next(flow for flow in headers.json() if flow["id"] == str(flow_id))
        assert shared_header["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None

        paged = await client.get(
            "api/v1/flows/", headers=bob_headers, params={"get_all": "false", "folder_id": str(folder_id)}
        )
        assert paged.status_code == 200, paged.text
        shared_page = next(flow for flow in paged.json()["items"] if flow["id"] == str(flow_id))
        assert shared_page["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None

        project = await client.get(f"api/v1/projects/{folder_id}", headers=bob_headers)
        assert project.status_code == 200, project.text
        shared_project_flow = next(flow for flow in project.json()["flows"] if flow["id"] == str(flow_id))
        assert shared_project_flow["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None

        paged_project = await client.get(
            f"api/v1/projects/{folder_id}", headers=bob_headers, params={"page": 1, "size": 10}
        )
        assert paged_project.status_code == 200, paged_project.text
        shared_project_page = next(
            flow for flow in paged_project.json()["flows"]["items"] if flow["id"] == str(flow_id)
        )
        assert shared_project_page["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None
        assert value(await client.get(f"api/v1/flows/{flow_id}", headers=alice_headers)) == secret_value


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


async def test_oss_create_flow_keeps_foreign_project_owner_scoped(client):
    """The OSS service must not widen a foreign project merely because authz is enabled."""
    project_owner_id = await _make_user(f"project_owner_{uuid4().hex}")
    foreign_project_id = await _make_project(project_owner_id, f"foreign_project_{uuid4().hex}")
    creator_username = f"creator_{uuid4().hex}"
    creator_id = await _make_user(creator_username)
    headers = await _login(client, creator_username)

    settings = get_settings_service()
    authz = get_authorization_service()
    assert await authz.supports_cross_user_fetch() is False
    saved_authz_enabled = settings.auth_settings.AUTHZ_ENABLED
    settings.auth_settings.AUTHZ_ENABLED = True
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

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["folder_id"] != str(foreign_project_id)
    async with session_scope() as session:
        destination = await session.get(Folder, UUID(created["folder_id"]))
    assert destination is not None
    assert destination.user_id == creator_id


async def test_cross_user_destination_resolution_does_not_widen_flow_moves(client):
    """Cross-user destination fetch is limited to CREATE and cannot bypass move authorization."""
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

    assert move.status_code == 200, move.text
    assert move.json()["folder_id"] == original_folder_id
    assert move.json()["folder_id"] != str(foreign_project_id)


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
    # viewer scoped to workspace A only.
    _viewer_id, headers = await _role_user(client, "viewer", role_ids, domain_type="workspace", domain_id=workspace_a)

    with install_policy_authz(get_settings_service()):
        # flow A resolves to domain workspace:{A} -> grant covers -> read allowed.
        assert (await client.get(f"api/v1/flows/{flow_a}", headers=headers)).status_code == 200
        # flow B resolves to workspace:{B} -> grant does NOT cover -> denied -> 404.
        # (If domain resolution regressed to '*', the workspace-A grant would stop
        # matching flow A and the assertion above would fail instead.)
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
