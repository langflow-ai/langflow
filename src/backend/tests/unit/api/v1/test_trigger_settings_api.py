"""The API the triggers settings page (TRG-7, B2 and B3) is built on.

Three things the per-flow trigger routes did not provide:

* a list across every flow the caller can read, carrying the flow's name, plus
  a superuser view across every user that carries the owner;
* operator bulk pause and resume, filtered by provider, for incident response,
  leaving a distinct ``paused_by_admin`` reason the owner can see;
* server-computed ``allowed_actions`` / ``blocked_actions`` / ``reason`` on
  every ``TriggerRead``, so the UI renders what the server allows.

Everything runs against the real database the ``client`` fixture stands up.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from langflow.services.triggers.reconciliation import NODE_REMOVED_ERROR, reconcile_flow_triggers
from sqlmodel import select

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

_PASSWORD = "operator-test-password"  # noqa: S105  # pragma: allowlist secret
_SCHEDULE = {"cron": "0 8 * * 1-5", "timezone": "Europe/Lisbon"}


async def _user(*, superuser: bool = False) -> tuple[UUID, str]:
    username = f"{'admin' if superuser else 'user'}-{uuid4().hex[:8]}"
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_auth_service().get_password_hash(_PASSWORD),
            is_active=True,
            is_superuser=superuser,
        )
        session.add(user)
        await session.flush()
        return user.id, username


async def _login(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post("api/v1/login", data={"username": username, "password": _PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _flow(owner_id: UUID, name: str | None = None) -> UUID:
    async with session_scope() as session:
        flow = Flow(name=name or f"flow-{uuid4().hex[:6]}", user_id=owner_id)
        session.add(flow)
        await session.flush()
        return flow.id


async def _trigger(flow_id: UUID, owner_id: UUID, *, state: str = "active", **fields) -> UUID:
    fields.setdefault("kind", "schedule")
    fields.setdefault("config", dict(_SCHEDULE))
    async with session_scope() as session:
        row = Trigger(
            flow_id=flow_id,
            user_id=owner_id,
            name=fields.pop("name", f"trigger-{uuid4().hex[:6]}"),
            provider_state={},
            state=state,
            concurrency_limit=1,
            max_attempts=5,
            **fields,
        )
        session.add(row)
        await session.flush()
        return row.id


async def _stored(trigger_id: UUID) -> Trigger:
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        assert row is not None
        session.expunge(row)
        return row


# --------------------------------------------------------------------------- #
# Cross-flow list (B2)
# --------------------------------------------------------------------------- #


async def test_listing_without_a_flow_returns_the_callers_triggers_with_flow_names(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    digest_flow = await _flow(active_user.id, "Daily digest")
    inbox_flow = await _flow(active_user.id, "Inbox to CRM")
    digest = await _trigger(digest_flow, active_user.id)
    inbox = await _trigger(inbox_flow, active_user.id, state="paused")
    stranger_id, _ = await _user()
    hidden = await _trigger(await _flow(stranger_id), stranger_id)

    response = await client.get("api/v1/triggers", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()}
    assert set(rows) == {str(digest), str(inbox)}
    assert str(hidden) not in rows
    assert rows[str(digest)]["flow_name"] == "Daily digest"
    assert rows[str(inbox)]["flow_name"] == "Inbox to CRM"
    # The owner is only named in the operator view.
    assert rows[str(digest)]["owner_username"] is None


async def test_the_list_filters_by_provider_and_state(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    flow_id = await _flow(active_user.id)
    slack_active = await _trigger(flow_id, active_user.id, provider="slack")
    await _trigger(flow_id, active_user.id, provider="slack", state="paused")
    await _trigger(flow_id, active_user.id, provider="google")

    response = await client.get("api/v1/triggers?provider=slack&state=active", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [str(slack_active)]


async def test_the_flow_scoped_list_still_works_and_now_names_the_flow(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    flow_id = await _flow(active_user.id, "Named flow")
    trigger_id = await _trigger(flow_id, active_user.id)
    await _trigger(await _flow(active_user.id), active_user.id)

    response = await client.get(f"api/v1/triggers?flow_id={flow_id}", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert [(row["id"], row["flow_name"]) for row in response.json()] == [(str(trigger_id), "Named flow")]


async def test_the_all_users_view_is_superuser_only(client: AsyncClient, logged_in_headers: dict[str, str]) -> None:
    response = await client.get("api/v1/triggers?scope=all", headers=logged_in_headers)
    assert response.status_code == 403, response.text


async def test_the_all_users_view_names_each_owner(client: AsyncClient) -> None:
    owner_id, owner_name = await _user()
    other_id, other_name = await _user()
    _, admin_name = await _user(superuser=True)
    first = await _trigger(await _flow(owner_id, "Support triage"), owner_id, provider="slack")
    second = await _trigger(await _flow(other_id, "Incident bridge"), other_id, provider="slack")
    admin_headers = await _login(client, admin_name)

    response = await client.get("api/v1/triggers?scope=all&provider=slack", headers=admin_headers)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()}
    assert rows[str(first)]["owner_username"] == owner_name
    assert rows[str(first)]["flow_name"] == "Support triage"
    assert rows[str(second)]["owner_username"] == other_name
    # The operator cannot reach someone else's trigger through the per-trigger
    # routes (they are flow-scoped), so none of those actions is offered; the
    # operator acts through the bulk routes instead.
    assert rows[str(first)]["allowed_actions"] == []
    assert rows[str(first)]["blocked_actions"]["pause"] == "insufficient_permission"


# --------------------------------------------------------------------------- #
# allowed_actions / reason on every TriggerRead
# --------------------------------------------------------------------------- #


async def test_every_trigger_read_carries_server_allowed_actions(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    flow_id = await _flow(active_user.id)
    trigger_id = await _trigger(flow_id, active_user.id, kind="inbound_webhook", config={})

    single = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)
    assert single.status_code == 200, single.text
    body = single.json()
    assert body["reason"] is None
    assert body["allowed_actions"] == ["pause", "test", "replay", "delete", "rotate_secret"]
    assert body["blocked_actions"] == {}

    paused = await client.post(f"api/v1/triggers/{trigger_id}/disable", headers=logged_in_headers)
    assert paused.status_code == 200, paused.text
    body = paused.json()
    assert body["reason"] == "paused"
    assert body["allowed_actions"] == ["resume", "delete", "rotate_secret"]
    assert body["blocked_actions"] == {"test": "paused", "replay": "paused"}


@pytest.mark.parametrize(
    ("granted", "allowed", "blocked"),
    [
        pytest.param(
            {"read"},
            [],
            {
                "pause": "insufficient_permission",
                "test": "insufficient_permission",
                "replay": "insufficient_permission",
                "delete": "insufficient_permission",
            },
            id="reader",
        ),
        pytest.param(
            {"read", "write"},
            ["pause", "delete"],
            {"test": "insufficient_permission", "replay": "insufficient_permission"},
            id="writer",
        ),
    ],
)
async def test_a_collaborator_is_offered_exactly_what_their_role_allows(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user, monkeypatch, granted, allowed, blocked
) -> None:
    """Under an authorization plugin, each control follows the caller's grant on someone else's flow."""
    from langflow.services.authorization import fetch, guards
    from langflow.services.deps import get_settings_service

    owner_id, _ = await _user()
    flow_id = await _flow(owner_id)
    trigger_id = await _trigger(flow_id, owner_id)

    class Granted:
        async def supports_cross_user_fetch(self):
            return True

        async def is_enabled(self):
            return True

        async def enforce(self, *, user_id, domain, obj, act, context):  # noqa: ARG002
            assert user_id == active_user.id
            return obj == f"flow:{flow_id}" and act in granted

    authz = Granted()
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(fetch, "get_authorization_service", lambda: authz)
    monkeypatch.setattr(guards, "get_authorization_service", lambda: authz)

    response = await client.get(f"api/v1/triggers/{trigger_id}", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allowed_actions"] == allowed
    assert body["blocked_actions"] == blocked


@pytest.mark.parametrize(("authz_enabled", "cross_user"), [(True, True), (True, False), (False, True)])
async def test_fallback_visibility_filters_before_pagination(
    client, logged_in_headers, active_user, monkeypatch, authz_enabled, cross_user
):
    from langflow.services.authorization import fetch, guards, listing
    from langflow.services.deps import get_settings_service

    other_id, _ = await _user()
    denied_flow = await _flow(other_id)
    shared_flow = await _flow(other_id)
    own_flow = await _flow(active_user.id)
    denied = await _trigger(
        denied_flow, other_id, provider="slack", created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)
    )
    shared = await _trigger(
        shared_flow, other_id, provider="slack", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
    )
    own = await _trigger(
        own_flow, active_user.id, provider="slack", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    # More denied rows than one bounded candidate batch must not hide the
    # visible rows or leave a hole in the page window.
    async with session_scope() as session:
        session.add_all(
            [
                Trigger(
                    flow_id=denied_flow,
                    user_id=other_id,
                    name=f"denied-{index}",
                    kind="schedule",
                    provider="slack",
                    state="active",
                    config=dict(_SCHEDULE),
                    concurrency_limit=1,
                    max_attempts=5,
                    created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
                )
                for index in range(200)
            ]
        )

    class ReadShared:
        async def supports_cross_user_fetch(self):
            return cross_user

        async def is_enabled(self):
            return authz_enabled

        async def get_resource_visibility(self, **_kwargs):
            return None

        async def enforce(self, *, obj, act, **_kwargs):
            return obj == f"flow:{shared_flow}" and act == "read"

        async def batch_enforce(self, *, requests, **_kwargs):
            return [obj == f"flow:{shared_flow}" and act == "read" for obj, act in requests]

    authz = ReadShared()
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", authz_enabled)
    for module in (fetch, guards, listing):
        monkeypatch.setattr(module, "get_authorization_service", lambda: authz)

    expected = [shared, own] if authz_enabled and cross_user else [own]
    for offset in range(len(expected) + 1):
        response = await client.get(
            f"api/v1/triggers?provider=slack&limit=1&offset={offset}", headers=logged_in_headers
        )
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()] == [str(value) for value in expected[offset : offset + 1]]
        assert all(row["id"] != str(denied) for row in response.json())


# --------------------------------------------------------------------------- #
# Operator bulk pause and resume (B3)
# --------------------------------------------------------------------------- #


async def test_bulk_pause_and_resume_are_superuser_only(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    trigger_id = await _trigger(await _flow(active_user.id), active_user.id, provider="slack")

    for action in ("pause", "resume"):
        response = await client.post(
            f"api/v1/triggers/bulk/{action}", json={"provider": "slack"}, headers=logged_in_headers
        )
        assert response.status_code == 403, response.text
    assert (await _stored(trigger_id)).state == "active"


async def test_bulk_requires_a_filter(client: AsyncClient) -> None:
    """An empty body must not mean "every trigger on the instance"."""
    _, admin_name = await _user(superuser=True)
    admin_headers = await _login(client, admin_name)

    response = await client.post("api/v1/triggers/bulk/pause", json={}, headers=admin_headers)

    assert response.status_code == 422, response.text


async def test_bulk_pause_by_provider_pauses_only_armed_triggers_across_users(client: AsyncClient) -> None:
    owner_id, owner_name = await _user()
    other_id, _ = await _user()
    _, admin_name = await _user(superuser=True)
    owner_flow, other_flow = await _flow(owner_id), await _flow(other_id)
    active = await _trigger(owner_flow, owner_id, provider="slack")
    errored = await _trigger(other_flow, other_id, provider="slack", state="error", last_error="boom")
    owner_paused = await _trigger(owner_flow, owner_id, provider="slack", state="paused")
    never_enabled = await _trigger(owner_flow, owner_id, provider="slack", state="pending")
    other_provider = await _trigger(owner_flow, owner_id, provider="google")
    admin_headers = await _login(client, admin_name)

    preview = await client.post(
        "api/v1/triggers/bulk/pause", json={"provider": "slack", "dry_run": True}, headers=admin_headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["dry_run"] is True
    assert set(preview.json()["changed"]) == {str(active), str(errored)}
    assert (await _stored(active)).state == "active", "a dry run changes nothing"

    response = await client.post("api/v1/triggers/bulk/pause", json={"provider": "slack"}, headers=admin_headers)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["action"] == "pause"
    assert result["matched"] == 4
    assert set(result["changed"]) == {str(active), str(errored)}
    assert set(result["unchanged"]) == {str(owner_paused), str(never_enabled)}
    assert result["owners"] == 2
    assert result["failed"] == []
    for trigger_id in (active, errored):
        row = await _stored(trigger_id)
        assert row.state == "paused"
        assert row.admin_paused_at is not None
    assert (await _stored(owner_paused)).admin_paused_at is None
    assert (await _stored(never_enabled)).state == "pending"
    assert (await _stored(other_provider)).state == "active"

    # The owner sees that an administrator paused it, not that they did.
    owner_headers = await _login(client, owner_name)
    seen = (await client.get(f"api/v1/triggers/{active}", headers=owner_headers)).json()
    assert seen["state"] == "paused"
    assert seen["reason"] == "paused_by_admin"
    assert "resume" in seen["allowed_actions"]
    mine = (await client.get(f"api/v1/triggers/{owner_paused}", headers=owner_headers)).json()
    assert mine["reason"] == "paused"


async def test_bulk_resume_rearms_only_what_an_administrator_paused(client: AsyncClient) -> None:
    """A trigger the owner paused stays paused: an incident ending is not the owner's consent."""
    owner_id, _ = await _user()
    _, admin_name = await _user(superuser=True)
    flow_id = await _flow(owner_id)
    admin_paused = await _trigger(flow_id, owner_id, provider="slack")
    owner_paused = await _trigger(flow_id, owner_id, provider="slack", state="paused")
    admin_headers = await _login(client, admin_name)
    paused = await client.post("api/v1/triggers/bulk/pause", json={"provider": "slack"}, headers=admin_headers)
    assert paused.status_code == 200, paused.text

    response = await client.post("api/v1/triggers/bulk/resume", json={"provider": "slack"}, headers=admin_headers)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["changed"] == [str(admin_paused)]
    assert result["unchanged"] == [str(owner_paused)]
    resumed = await _stored(admin_paused)
    assert (resumed.state, resumed.admin_paused_at) == ("active", None)
    assert (await _stored(owner_paused)).state == "paused"


async def test_bulk_can_target_explicit_trigger_ids(client: AsyncClient) -> None:
    owner_id, _ = await _user()
    _, admin_name = await _user(superuser=True)
    flow_id = await _flow(owner_id)
    chosen = await _trigger(flow_id, owner_id, provider="slack")
    spared = await _trigger(flow_id, owner_id, provider="slack")
    admin_headers = await _login(client, admin_name)

    response = await client.post(
        "api/v1/triggers/bulk/pause", json={"trigger_ids": [str(chosen)]}, headers=admin_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["changed"] == [str(chosen)]
    assert (await _stored(spared)).state == "active"


async def test_a_failed_resume_releases_the_hold_and_says_why(client: AsyncClient) -> None:
    """The administrator released it; the owner sees a plain pause with the reason it could not start."""
    owner_id, _ = await _user()
    _, admin_name = await _user(superuser=True)
    flow_id = await _flow(owner_id)
    broken = await _trigger(
        flow_id,
        owner_id,
        provider="slack",
        state="paused",
        admin_paused_at=datetime.now(timezone.utc),
        config={"cron": "not a cron", "timezone": "UTC"},
    )
    admin_headers = await _login(client, admin_name)

    response = await client.post("api/v1/triggers/bulk/resume", json={"provider": "slack"}, headers=admin_headers)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["changed"] == []
    assert [failure["trigger_id"] for failure in result["failed"]] == [str(broken)]
    row = await _stored(broken)
    assert (row.state, row.admin_paused_at) == ("paused", None)
    assert row.last_error


async def test_the_owner_can_resume_an_admin_paused_trigger(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    trigger_id = await _trigger(
        await _flow(active_user.id), active_user.id, state="paused", admin_paused_at=datetime.now(timezone.utc)
    )

    response = await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert (response.json()["state"], response.json()["reason"]) == ("active", None)
    assert (await _stored(trigger_id)).admin_paused_at is None


async def test_an_admin_pause_survives_the_owner_saving_the_flow(trigger_owner_flow) -> None:
    """A canvas save copies configuration onto the row; it must not erase who paused it."""
    owner_id, flow_id, node = trigger_owner_flow
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": [node], "edges": []}
        )
    async with session_scope() as session:
        stored = (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()
        trigger_id = stored.id
        stored.state = "paused"
        stored.admin_paused_at = datetime.now(timezone.utc)
        session.add(stored)

    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": [node], "edges": []}
        )

    row = await _stored(trigger_id)
    assert (row.state, row.admin_paused_at is not None) == ("paused", True)


async def test_removing_the_node_hands_an_operator_pause_to_the_owner(client: AsyncClient, trigger_owner_flow) -> None:
    """The operator's bulk resume must never re-arm a trigger whose node was deleted."""
    owner_id, flow_id, node = trigger_owner_flow
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": [node], "edges": []}
        )
    async with session_scope() as session:
        stored = (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()
        trigger_id = stored.id
        stored.state = "paused"
        stored.provider = "slack"
        stored.admin_paused_at = datetime.now(timezone.utc)
        session.add(stored)

    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data={"nodes": [], "edges": []})

    row = await _stored(trigger_id)
    assert (row.state, row.admin_paused_at, row.last_error) == ("paused", None, NODE_REMOVED_ERROR)
    _, admin_name = await _user(superuser=True)
    resumed = await client.post(
        "api/v1/triggers/bulk/resume", json={"trigger_ids": [str(trigger_id)]}, headers=await _login(client, admin_name)
    )
    assert resumed.json()["unchanged"] == [str(trigger_id)]
    assert (await _stored(trigger_id)).state == "paused"


async def test_one_failure_does_not_undo_or_stop_the_rest_of_a_bulk_pause(client: AsyncClient, monkeypatch) -> None:
    """Every change commits with its audit on its own; a failing trigger is reported, not fatal."""
    from langflow.services.triggers.service import TriggerService

    owner_id, _ = await _user()
    _, admin_name = await _user(superuser=True)
    flow_id = await _flow(owner_id)
    first = await _trigger(flow_id, owner_id, provider="slack")
    broken = await _trigger(flow_id, owner_id, provider="slack")
    last = await _trigger(flow_id, owner_id, provider="slack")
    real_admin_pause = TriggerService.admin_pause

    async def admin_pause(self, session, *, row):
        if row.id == broken:
            msg = "simulated database failure"
            raise RuntimeError(msg)
        return await real_admin_pause(self, session, row=row)

    monkeypatch.setattr(TriggerService, "admin_pause", admin_pause)

    response = await client.post(
        "api/v1/triggers/bulk/pause", json={"provider": "slack"}, headers=await _login(client, admin_name)
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert set(result["changed"]) == {str(first), str(last)}
    assert [failure["trigger_id"] for failure in result["failed"]] == [str(broken)]
    assert "simulated" not in result["failed"][0]["detail"], "internal errors are not echoed to the caller"
    assert [(await _stored(t)).state for t in (first, broken, last)] == ["paused", "active", "paused"]


@pytest.fixture
async def trigger_owner_flow(client):  # noqa: ARG001
    owner_id, _ = await _user()
    flow_id = await _flow(owner_id)
    node = {
        "id": "ScheduleTrigger-admin",
        "data": {
            "type": "ScheduleTrigger",
            "node": {
                "template": {
                    "cron_expression": {"value": "0 8 * * 1-5"},
                    "timezone": {"value": "Europe/Lisbon"},
                }
            },
        },
    }
    return owner_id, flow_id, node


# --------------------------------------------------------------------------- #
# Polling interval (constraint 2)
# --------------------------------------------------------------------------- #


async def test_config_reports_the_trigger_polling_interval(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
) -> None:
    from lfx.services.deps import get_settings_service

    default = await client.get("api/v1/config", headers=logged_in_headers)
    assert default.status_code == 200, default.text
    assert default.json()["trigger_polling_interval"] == 5000

    monkeypatch.setattr(get_settings_service().settings, "trigger_polling_interval", 2000)
    tuned = await client.get("api/v1/config", headers=logged_in_headers)
    assert tuned.json()["trigger_polling_interval"] == 2000


async def test_public_config_does_not_carry_the_trigger_polling_interval(client: AsyncClient) -> None:
    response = await client.get("api/v1/config")
    assert response.status_code == 200, response.text
    assert "trigger_polling_interval" not in response.json()
