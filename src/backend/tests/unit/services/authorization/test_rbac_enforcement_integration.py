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

from uuid import UUID, uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope

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


async def _make_flow(owner_id: UUID, name: str, *, workspace_id: UUID | None = None) -> UUID:
    """Insert a minimal flow owned by ``owner_id`` and return its id."""
    async with session_scope() as session:
        flow = Flow(name=name, user_id=owner_id, workspace_id=workspace_id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        await session.commit()
    return flow_id


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
        # create -> denied; 403 is correct here (no existing resource UUID to protect)
        create = await client.post(
            "api/v1/flows/", headers=headers, json={"name": f"new_{uuid4().hex}", "data": {"nodes": [], "edges": []}}
        )
        assert create.status_code == 403


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
        assert build.status_code == 404


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
