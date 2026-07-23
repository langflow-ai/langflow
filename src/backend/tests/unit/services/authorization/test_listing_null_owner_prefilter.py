"""Regression: the DB-layer authz prefilter must apply the same null-owner semantics as the fallback.

The list endpoints (``read_projects`` / ``read_flows``) build two query paths:

* **prefilter active** (a registered plugin returned a concrete visible-id set):
  ``restrict_to_owned_or_visible(select(Model), owner_clause=<owned-only>, visible_ids=...)``
* **fallback** (OSS pass-through declines): owner-scoped query + ``filter_visible_resources``

A *null-owner* row — a legacy/manually-seeded project, or any flow under
AUTO_LOGIN — must be policy-checked on BOTH paths. The fallback already does
this: ``filter_visible_resources``'s ``owner_extractor`` returns ``None`` for a
null owner, which never equals a real user id, so the row is routed through
``batch_enforce``. The prefilter path used to diverge by folding a
``user_id IS NULL`` term into the owner clause, so every null-owner row came back
unconditionally (the reviewer's compiled
``... OR folder.user_id = :uid OR folder.user_id IS NULL``).

These tests install an authorization double whose ``list_visible_resource_ids``
returns a concrete list (so the endpoints take the prefilter branch — the path
:class:`PolicyTestAuthorizationService` does not exercise, since it leaves the
base ``None``) and assert a null-owner row appears ONLY when the plugin lists its
id — identical to what the fallback would decide.
"""

from __future__ import annotations

import contextlib
import gzip
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from lfx.services.authorization.base import BaseAuthorizationService, ResourceVisibilityScope
from sqlmodel import select

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from lfx.services.settings.service import SettingsService

_PASSWORD = "testpassword"  # noqa: S105 — test-only credential  # pragma: allowlist secret


class _PrefilterAuthorizationService(BaseAuthorizationService):
    """Authz double that returns a fixed visible-id set per resource type.

    This is what forces the list endpoints onto the DB-layer prefilter branch:
    ``list_visible_resource_ids`` yields a concrete list instead of the base
    ``None``. ``enforce`` / ``batch_enforce`` are allow-all because the prefilter
    path is authoritative and never calls them (asserting that invariant too).
    """

    SUPPORTS_CROSS_USER_FETCH = True

    def __init__(
        self,
        settings_service: SettingsService,
        visible_by_type: dict[str, list[UUID]],
        scope_by_type: dict[str, ResourceVisibilityScope] | None = None,
    ) -> None:
        super().__init__()
        self.settings_service = settings_service
        self._visible_by_type = visible_by_type
        self._scope_by_type = scope_by_type or {}
        self.batch_calls = 0
        self.set_ready()

    async def is_enabled(self) -> bool:
        return bool(self.settings_service.auth_settings.AUTHZ_ENABLED)

    async def enforce(self, **_kwargs: Any) -> bool:
        return True

    async def batch_enforce(self, *, requests: Sequence[tuple[str, str]], **_kwargs: Any) -> list[bool]:
        # Should never run on the prefilter path; recorded so a test can assert it.
        self.batch_calls += 1
        return [True] * len(list(requests))

    async def list_visible_resource_ids(self, *, resource_type: str, **_kwargs: Any) -> list[UUID] | None:
        return list(self._visible_by_type.get(resource_type, []))

    async def get_resource_visibility(self, *, resource_type: str, **kwargs: Any) -> ResourceVisibilityScope | None:
        if resource_type in self._scope_by_type:
            return self._scope_by_type[resource_type]
        return await super().get_resource_visibility(resource_type=resource_type, **kwargs)


@contextlib.contextmanager
def _install_prefilter_authz(
    settings_service: SettingsService,
    visible_by_type: dict[str, list[UUID]],
    *,
    auto_login: bool = False,
    scope_by_type: dict[str, ResourceVisibilityScope] | None = None,
) -> Iterator[_PrefilterAuthorizationService]:
    """Install the prefilter double + enable AUTHZ (and optionally AUTO_LOGIN); restore on exit."""
    from langflow.services.schema import ServiceType
    from lfx.services.manager import get_service_manager

    auth_settings = settings_service.auth_settings
    saved_enabled = auth_settings.AUTHZ_ENABLED
    saved_bypass = auth_settings.AUTHZ_SUPERUSER_BYPASS
    saved_auto_login = auth_settings.AUTO_LOGIN

    service_manager = get_service_manager()
    previous_service = service_manager.services.get(ServiceType.AUTHORIZATION_SERVICE)

    auth_settings.AUTHZ_ENABLED = True
    auth_settings.AUTHZ_SUPERUSER_BYPASS = False
    auth_settings.AUTO_LOGIN = auto_login
    double = _PrefilterAuthorizationService(settings_service, visible_by_type, scope_by_type)
    service_manager.services[ServiceType.AUTHORIZATION_SERVICE] = double
    try:
        yield double
    finally:
        if previous_service is not None:
            service_manager.services[ServiceType.AUTHORIZATION_SERVICE] = previous_service
        else:
            service_manager.services.pop(ServiceType.AUTHORIZATION_SERVICE, None)
        auth_settings.AUTHZ_ENABLED = saved_enabled
        auth_settings.AUTHZ_SUPERUSER_BYPASS = saved_bypass
        auth_settings.AUTO_LOGIN = saved_auto_login


async def _make_user(username: str) -> UUID:
    async with session_scope() as session:
        user = User(username=username, password=get_auth_service().get_password_hash(_PASSWORD), is_active=True)
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
    return user_id


async def _login(client, username: str) -> dict[str, str]:
    response = await client.post("api/v1/login", data={"username": username, "password": _PASSWORD})
    assert response.status_code == 200, f"login failed for {username}: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _make_folder(name: str, *, user_id: UUID | None, workspace_id: UUID | None = None) -> UUID:
    async with session_scope() as session:
        folder = Folder(name=name, user_id=user_id, workspace_id=workspace_id)
        session.add(folder)
        await session.flush()
        folder_id = folder.id
        await session.commit()
    return folder_id


async def _make_flow(
    name: str,
    *,
    user_id: UUID | None,
    folder_id: UUID | None = None,
    workspace_id: UUID | None = None,
) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=name,
            user_id=user_id,
            folder_id=folder_id,
            workspace_id=workspace_id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        await session.commit()
    return flow_id


def _project_ids(response) -> set[UUID]:
    assert response.status_code == 200, response.text
    return {UUID(p["id"]) for p in response.json()}


def _flow_ids(response) -> set[UUID]:
    assert response.status_code == 200, response.text
    body = response.content
    # ``read_flows`` (get_all) gzips its body; httpx usually decodes it, but decode
    # defensively in case the transport leaves it compressed.
    if response.headers.get("content-encoding") == "gzip":
        with contextlib.suppress(OSError):
            body = gzip.decompress(body)
    return {UUID(f["id"]) for f in json.loads(body)}


def _project_flow_ids(response, *, paginated: bool) -> set[UUID]:
    assert response.status_code == 200, response.text
    body = response.json()
    rows = body["flows"]["items"] if paginated else body["flows"]
    return {UUID(flow["id"]) for flow in rows}


# --------------------------------------------------------------------------- #
# Projects: a non-starter null-owner project must not leak through the prefilter.
# --------------------------------------------------------------------------- #


async def test_projects_prefilter_excludes_unlisted_null_owner_project(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    other_id = await _make_user(f"other_{uuid4().hex}")
    headers = await _login(client, username)

    owned_id = await _make_folder(f"owned_{uuid4().hex}", user_id=owner_id)
    foreign_id = await _make_folder(f"foreign_{uuid4().hex}", user_id=other_id)
    # A legacy / manually-seeded null-owner project (NOT the starter folder, so the
    # name filter in read_projects does not mask the bug being guarded here).
    orphan_id = await _make_folder(f"orphan_{uuid4().hex}", user_id=None)

    # Plugin reports only the foreign project visible — orphan is NOT listed.
    with _install_prefilter_authz(settings, {"project": [foreign_id]}) as authz:
        ids = _project_ids(await client.get("api/v1/projects/", headers=headers))

    # Owner-override keeps the caller's own project; the plugin widens to the
    # foreign one; the null-owner project is gone (it used to leak via IS NULL).
    assert owned_id in ids
    assert foreign_id in ids
    assert orphan_id not in ids
    # Prefilter path is authoritative: no per-row in-memory enforce ran.
    assert authz.batch_calls == 0


async def test_projects_prefilter_includes_null_owner_project_when_plugin_lists_it(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)

    owned_id = await _make_folder(f"owned_{uuid4().hex}", user_id=owner_id)
    orphan_id = await _make_folder(f"orphan_{uuid4().hex}", user_id=None)

    # Now the plugin explicitly grants the null-owner project — it must appear,
    # proving it is reachable by policy, not unreachable by the fix.
    with _install_prefilter_authz(settings, {"project": [orphan_id]}):
        ids = _project_ids(await client.get("api/v1/projects/", headers=headers))

    assert owned_id in ids
    assert orphan_id in ids


# --------------------------------------------------------------------------- #
# Flows under AUTO_LOGIN: the null-owner term is AUTO_LOGIN-only, and AUTHZ_ENABLED
# is an independent flag, so both can be set — the prefilter must still policy-check
# null-owner flows rather than blanket-including them.
# --------------------------------------------------------------------------- #


async def test_flows_prefilter_excludes_unlisted_null_owner_flow_under_auto_login(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    other_id = await _make_user(f"other_{uuid4().hex}")
    # Log in BEFORE flipping AUTO_LOGIN so current_user resolves from the token
    # (get_current_user short-circuits on a present token regardless of AUTO_LOGIN).
    headers = await _login(client, username)

    owned_id = await _make_flow(f"owned_{uuid4().hex}", user_id=owner_id)
    foreign_id = await _make_flow(f"foreign_{uuid4().hex}", user_id=other_id)
    null_id = await _make_flow(f"orphan_{uuid4().hex}", user_id=None)

    with _install_prefilter_authz(settings, {"flow": [foreign_id]}, auto_login=True) as authz:
        ids = _flow_ids(await client.get("api/v1/flows/", headers=headers))

    assert owned_id in ids
    assert foreign_id in ids
    # Under AUTO_LOGIN the owner clause used to include ``Flow.user_id IS NULL``,
    # leaking this row through the prefilter union; the fix keeps it out.
    assert null_id not in ids
    assert authz.batch_calls == 0


async def test_flows_prefilter_includes_null_owner_flow_when_plugin_lists_it(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    owner_id = await _make_user(username)
    headers = await _login(client, username)

    owned_id = await _make_flow(f"owned_{uuid4().hex}", user_id=owner_id)
    null_id = await _make_flow(f"orphan_{uuid4().hex}", user_id=None)

    with _install_prefilter_authz(settings, {"flow": [null_id]}, auto_login=True):
        ids = _flow_ids(await client.get("api/v1/flows/", headers=headers))

    assert owned_id in ids
    assert null_id in ids


async def test_flow_workspace_prefilter_uses_project_workspace_not_denormalized_flow_value(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    await _make_user(username)
    other_id = await _make_user(f"other_{uuid4().hex}")
    headers = await _login(client, username)
    visible_workspace = uuid4()
    hidden_workspace = uuid4()
    hidden_project = await _make_folder(
        f"hidden_project_{uuid4().hex}",
        user_id=other_id,
        workspace_id=hidden_workspace,
    )
    visible_project = await _make_folder(
        f"visible_project_{uuid4().hex}",
        user_id=other_id,
        workspace_id=visible_workspace,
    )
    spoofed_visible = await _make_flow(
        f"spoofed_{uuid4().hex}",
        user_id=other_id,
        folder_id=hidden_project,
        workspace_id=visible_workspace,
    )
    canonical_visible = await _make_flow(
        f"canonical_{uuid4().hex}",
        user_id=other_id,
        folder_id=visible_project,
        workspace_id=hidden_workspace,
    )

    scope = ResourceVisibilityScope(workspace_ids=(visible_workspace,))
    with _install_prefilter_authz(settings, {}, scope_by_type={"flow": scope}):
        ids = _flow_ids(await client.get("api/v1/flows/", headers=headers))

    assert canonical_visible in ids
    assert spoofed_visible not in ids


async def test_shared_project_flow_listing_uses_project_workspace_for_both_response_shapes(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    await _make_user(username)
    other_id = await _make_user(f"other_{uuid4().hex}")
    headers = await _login(client, username)
    visible_workspace = uuid4()
    hidden_workspace = uuid4()
    hidden_project = await _make_folder(
        f"hidden_project_{uuid4().hex}",
        user_id=other_id,
        workspace_id=hidden_workspace,
    )
    visible_project = await _make_folder(
        f"visible_project_{uuid4().hex}",
        user_id=other_id,
        workspace_id=visible_workspace,
    )
    spoofed_visible = await _make_flow(
        f"spoofed_{uuid4().hex}",
        user_id=other_id,
        folder_id=hidden_project,
        workspace_id=visible_workspace,
    )
    canonical_visible = await _make_flow(
        f"canonical_{uuid4().hex}",
        user_id=other_id,
        folder_id=visible_project,
        workspace_id=hidden_workspace,
    )
    scope = ResourceVisibilityScope(workspace_ids=(visible_workspace,))

    with _install_prefilter_authz(settings, {}, scope_by_type={"flow": scope}):
        for paginated, params in ((False, {}), (True, {"page": 1, "size": 50})):
            hidden_ids = _project_flow_ids(
                await client.get(f"api/v1/projects/{hidden_project}", headers=headers, params=params),
                paginated=paginated,
            )
            visible_ids = _project_flow_ids(
                await client.get(f"api/v1/projects/{visible_project}", headers=headers, params=params),
                paginated=paginated,
            )
            assert spoofed_visible not in hidden_ids
            assert canonical_visible in visible_ids


async def test_shared_project_get_does_not_delete_flows_hidden_from_response(client):
    settings = get_settings_service()
    username = f"owner_{uuid4().hex}"
    await _make_user(username)
    other_id = await _make_user(f"other_{uuid4().hex}")
    headers = await _login(client, username)
    project_id = await _make_folder(
        f"shared_project_{uuid4().hex}",
        user_id=other_id,
        workspace_id=uuid4(),
    )
    visible_id = await _make_flow(f"visible_{uuid4().hex}", user_id=other_id, folder_id=project_id)
    hidden_id = await _make_flow(f"hidden_{uuid4().hex}", user_id=other_id, folder_id=project_id)
    scope = ResourceVisibilityScope(resource_ids=(visible_id,))

    with _install_prefilter_authz(settings, {}, scope_by_type={"flow": scope}):
        response_ids = _project_flow_ids(
            await client.get(f"api/v1/projects/{project_id}", headers=headers),
            paginated=False,
        )

    assert response_ids == {visible_id}
    async with session_scope() as session:
        persisted = set((await session.exec(select(Flow.id).where(Flow.folder_id == project_id))).all())
    assert persisted == {visible_id, hidden_id}
