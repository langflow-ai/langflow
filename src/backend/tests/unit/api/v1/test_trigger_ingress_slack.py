"""Slack's Events API route: one Request URL per app, fanned out to triggers.

A Slack app has exactly one Request URL for every workspace it is installed in,
so a delivery names an app and a workspace, never a trigger. These tests drive
the real route, the real registration lookup, the real ledger and its unique
index with recorded Slack bodies, and pin the two properties that matter:
a verified event reaches every trigger it should and no other, and every refusal
looks like every other refusal.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from langflow.services.triggers.constants import MECHANISM_SLACK_SOCKET_MODE

from tests.unit.services.triggers import slack_fixtures as fx

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

URL = f"api/v1/triggers/ingress/slack/apps/{fx.REGISTRATION_ID}"
#: Test-only header the patched limiter key function reads as the client IP.
_CLIENT_IP_HEADER = "x-test-client-ip"


@pytest.fixture(autouse=True)
def _slack_app(monkeypatch):
    fx.use_registrations(monkeypatch)


def _key_client_ip_by_header(monkeypatch) -> None:
    """Let a request pick its client address; every test request otherwise shares one."""
    from langflow.services.rate_limit import service as rate_limit_service

    limiter = rate_limit_service.get_rate_limiter()
    monkeypatch.setattr(limiter, "_key_func", lambda request: request.headers.get(_CLIENT_IP_HEADER, "127.0.0.1"))


async def _deliver(client: AsyncClient, name_or_body, *, url: str = URL, headers: dict | None = None, **extra):
    body = name_or_body if isinstance(name_or_body, bytes) else fx.raw(name_or_body)
    signed = fx.sign(body)
    signed.update(headers or {})
    return await client.post(url, content=body, headers=signed, **extra)


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #


async def test_a_valid_slack_delivery_becomes_one_ledger_row(client: AsyncClient, active_user, flow) -> None:
    connection_id = await fx.make_oauth_connection(active_user.id)
    trigger_id = await fx.arm(flow.id, active_user.id, connection_id)

    response = await _deliver(client, "message_channel")

    assert response.status_code == 202, response.text
    rows = await fx.events_for(trigger_id)
    assert len(rows) == 1
    assert rows[0].dedupe_key == "slack:Ev0MSG00001"
    assert rows[0].payload["text"] == "The nightly deploy is failing again"
    assert rows[0].payload["session_key"] == "slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"
    # The request ran nothing: the dispatcher does that, afterwards.
    assert rows[0].state == "pending"
    assert rows[0].job_id is None


async def test_slack_retries_produce_exactly_one_run(client: AsyncClient, active_user, flow) -> None:
    """Slack retries at 0, 1 and 5 minutes when it misses an acknowledgement."""
    connection_id = await fx.make_oauth_connection(active_user.id)
    trigger_id = await fx.arm(flow.id, active_user.id, connection_id)

    statuses = []
    for retry in (None, "1", "2"):
        headers = {"X-Slack-Retry-Num": retry, "X-Slack-Retry-Reason": "http_timeout"} if retry else {}
        statuses.append((await _deliver(client, "message_channel", headers=headers)).status_code)

    # Every retry is acknowledged: answering an error would teach Slack to retry forever.
    assert statuses == [202, 202, 202]
    assert len(await fx.events_for(trigger_id)) == 1


async def test_the_request_url_handshake_succeeds_before_any_trigger_exists(client: AsyncClient) -> None:
    """An operator saves the Request URL in the Slack app config first, triggers later."""
    response = await _deliver(client, "url_verification")

    assert response.status_code == 200
    assert response.text == "please-echo-this-challenge-back"
    assert response.headers["content-type"].startswith("text/plain")


async def test_three_replies_in_a_thread_are_three_events_in_one_session(
    client: AsyncClient, active_user, flow
) -> None:
    from langflow.services.database.models.trigger.model import Trigger
    from langflow.services.deps import session_scope
    from langflow.services.triggers.correlation import derive_session_id

    connection_id = await fx.make_oauth_connection(active_user.id)
    trigger_id = await fx.arm(flow.id, active_user.id, connection_id)

    for body in fx.thread_replies(3):
        response = await _deliver(client, json.dumps(body).encode())
        assert response.status_code == 202, response.text

    rows = await fx.events_for(trigger_id)
    assert len(rows) == 3
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        sessions = {derive_session_id(trigger, row) for row in rows}
    assert sessions == {"slack:T0TEAM0001:C0SUPPORT1:1700000000.000100"}


# --------------------------------------------------------------------------- #
# Fan-out: every trigger it should reach, and no other
# --------------------------------------------------------------------------- #


async def test_one_delivery_reaches_every_matching_trigger_in_the_workspace(
    client: AsyncClient, active_user, flow
) -> None:
    """Two people in one workspace, each with their own installation and trigger."""
    mine = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    colleague = await fx.make_user()
    theirs = await fx.arm(
        await fx.make_flow(colleague), colleague, await fx.make_oauth_connection(colleague), kind="slack.message"
    )
    # Same workspace, but only listening to another channel.
    elsewhere = await fx.arm(
        flow.id, active_user.id, await fx.make_oauth_connection(active_user.id), config={"channels": ["C0RELEASE1"]}
    )
    # Same workspace, but a reaction trigger.
    reactions = await fx.arm(
        flow.id, active_user.id, await fx.make_oauth_connection(active_user.id), kind="slack.reaction"
    )

    response = await _deliver(client, "message_channel")

    assert response.status_code == 202, response.text
    assert len(await fx.events_for(mine)) == 1
    assert len(await fx.events_for(theirs)) == 1
    assert await fx.events_for(elsewhere) == []
    assert await fx.events_for(reactions) == []


async def test_a_workspace_never_sees_another_workspaces_events(client: AsyncClient, active_user, flow) -> None:
    ours = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    other_team = await fx.arm(
        flow.id, active_user.id, await fx.make_oauth_connection(active_user.id, team_id=fx.OTHER_TEAM_ID)
    )

    assert (await _deliver(client, "message_other_team")).status_code == 202
    assert await fx.events_for(ours) == []
    assert len(await fx.events_for(other_team)) == 1


async def test_a_slack_connect_message_reaches_only_the_installation_it_was_delivered_for(
    client: AsyncClient, active_user, flow
) -> None:
    """A shared-channel message names the sender's workspace in ``team_id``.

    The partner workspace has this app installed too, but Slack delivered the
    event for our installation - the partner's bot may not be in the channel -
    so the partner's trigger must not hear it.
    """
    ours = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    partner = await fx.arm(
        flow.id, active_user.id, await fx.make_oauth_connection(active_user.id, team_id=fx.OTHER_TEAM_ID)
    )

    assert (await _deliver(client, "message_slack_connect")).status_code == 202
    [row] = await fx.events_for(ours)
    assert row.payload["team_id"] == fx.OTHER_TEAM_ID
    assert await fx.events_for(partner) == []


@pytest.mark.parametrize(
    "shape",
    ["someone_elses_connection", "instance_connection", "revoked", "paused", "pending", "socket_mode", "other_app"],
)
async def test_triggers_that_must_not_hear_this_app_are_left_out(
    client: AsyncClient, active_user, flow, monkeypatch, shape: str
) -> None:
    """Armed state, ownership, connection health, mechanism and app all gate the fan-out."""
    fx.use_registrations(
        monkeypatch, {fx.REGISTRATION_ID: fx.registration(), "another-app": fx.registration(client_id="999.1")}
    )
    owner = active_user.id
    kwargs: dict = {}
    connection_kwargs: dict = {}
    if shape == "someone_elses_connection":
        connection_id = await fx.make_oauth_connection(await fx.make_user())
    elif shape == "instance_connection":
        connection_id = await fx.make_oauth_connection(owner, ownership_mode="instance")
    else:
        if shape == "revoked":
            connection_kwargs["status"] = "revoked"
        elif shape == "other_app":
            connection_kwargs["registration_id"] = "another-app"
        connection_id = await fx.make_oauth_connection(owner, **connection_kwargs)
    if shape in {"paused", "pending"}:
        kwargs["state"] = shape
    elif shape == "socket_mode":
        kwargs["mechanism"] = MECHANISM_SLACK_SOCKET_MODE
    trigger_id = await fx.arm(flow.id, owner, connection_id, **kwargs)

    response = await _deliver(client, "message_channel")

    assert response.status_code == 202, response.text
    assert await fx.events_for(trigger_id) == []


async def test_the_apps_own_reply_does_not_trigger_the_flow_again(client: AsyncClient, active_user, flow) -> None:
    trigger_id = await fx.arm(
        flow.id,
        active_user.id,
        await fx.make_oauth_connection(active_user.id),
        config={"include_bot_messages": True, "include_edits": True},
    )

    assert (await _deliver(client, "bot_self_echo")).status_code == 202
    assert await fx.events_for(trigger_id) == []


@pytest.mark.parametrize("name", ["app_rate_limited", "unsupported_event", "message_channel_join"])
async def test_deliveries_that_fire_nothing_are_still_acknowledged(
    client: AsyncClient, active_user, flow, name: str
) -> None:
    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))

    response = await _deliver(client, name)

    assert response.status_code in {200, 202}, response.text
    assert await fx.events_for(trigger_id) == []


# --------------------------------------------------------------------------- #
# Existence privacy: every refusal looks the same
# --------------------------------------------------------------------------- #


async def test_every_refusal_looks_identical_to_the_caller(client: AsyncClient, monkeypatch) -> None:
    """Unknown app, secretless app, user-profile app, forged, stale, unsigned: one answer."""
    fx.use_registrations(
        monkeypatch,
        {
            fx.REGISTRATION_ID: fx.registration(),
            "no-secret": fx.registration(signing_secret=None),
            "user-app": fx.registration(profile="user", signing_secret=None),
        },
    )
    body = fx.raw("message_channel")
    answers = [
        await client.post("api/v1/triggers/ingress/slack/apps/nobody", content=body, headers=fx.sign(body)),
        await client.post("api/v1/triggers/ingress/slack/apps/no-secret", content=body, headers=fx.sign(body)),
        await client.post("api/v1/triggers/ingress/slack/apps/user-app", content=body, headers=fx.sign(body)),
        await client.post(URL, content=body, headers=fx.sign(body, secret="wrong")),  # noqa: S106 - deliberately wrong
        await client.post(URL, content=body, headers=fx.sign(body, timestamp=1_000_000_000)),
        await client.post(URL, content=body),
        # The Graph handshake is Microsoft's alone; it is not a bypass here.
        await client.post(f"{URL}?validationToken=tok-1", content=b'{"type":"url_verification","challenge":"x"}'),
    ]

    assert {answer.status_code for answer in answers} == {404}
    assert {answer.text for answer in answers} == {answers[0].text}


async def test_a_disabled_ingress_answers_like_an_unknown_app(client: AsyncClient, monkeypatch) -> None:
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_enabled", False)

    response = await _deliver(client, "url_verification")

    assert response.status_code == 404


async def test_a_workspace_over_its_budget_is_refused_like_everything_else(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_slack_team_rate_limit_per_hour", 1)
    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))

    first = await _deliver(client, "message_channel")
    second = await _deliver(client, "message_im")
    unknown = await client.post("api/v1/triggers/ingress/slack/apps/nobody", content=b"{}")

    assert first.status_code == 202
    assert second.status_code == 404
    assert second.text == unknown.text
    assert len(await fx.events_for(trigger_id)) == 1


async def test_unsigned_requests_cannot_spend_the_apps_budget(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    """The Request URL names an operator's registration; it is not a secret.

    So before the signature is checked a sender spends only its own budget. A
    flood of unsigned requests from elsewhere must not get Slack's real
    deliveries refused for every workspace the app is installed in.
    """
    from langflow.services.deps import get_settings_service

    # An unusual ceiling: the limiter keys a counter by its limit, so nothing
    # else in this process shares these counters.
    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_slack_app_rate_limit_per_minute", 7)
    _key_client_ip_by_header(monkeypatch)
    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    body = fx.raw("message_channel")
    unsigned = {**fx.sign(b"not this body"), _CLIENT_IP_HEADER: "203.0.113.9"}

    flood = [await client.post(URL, content=body, headers=unsigned) for _ in range(10)]
    delivered = await _deliver(client, "message_channel")

    assert {response.status_code for response in flood} == {404}
    assert delivered.status_code == 202, delivered.text
    assert len(await fx.events_for(trigger_id)) == 1


async def test_one_sender_is_cut_off_before_its_requests_are_verified(client: AsyncClient, monkeypatch) -> None:
    from langflow.services.deps import get_settings_service
    from langflow.services.triggers.ingress.verifiers import REASON_RATE_LIMITED
    from langflow.services.triggers.providers.slack import ingress as slack_ingress

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_slack_app_rate_limit_per_minute", 5)
    _key_client_ip_by_header(monkeypatch)
    reasons: list[str | None] = []

    async def record(**kwargs) -> None:
        reasons.append(kwargs.get("reason"))

    monkeypatch.setattr(slack_ingress, "audit_delivery", record)
    body = fx.raw("message_channel")
    unsigned = {**fx.sign(b"not this body"), _CLIENT_IP_HEADER: "203.0.113.10"}

    for _ in range(7):
        assert (await client.post(URL, content=body, headers=unsigned)).status_code == 404

    assert REASON_RATE_LIMITED not in reasons[:5]
    assert reasons[5:] == [REASON_RATE_LIMITED, REASON_RATE_LIMITED]


async def test_an_oversized_body_is_refused_without_being_stored(client: AsyncClient, active_user, flow) -> None:
    from langflow.services.deps import get_settings_service

    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    body = fx.load("message_channel")
    body["pad"] = "x" * (get_settings_service().settings.trigger_ingress_max_body_bytes + 1024)

    response = await _deliver(client, json.dumps(body).encode())

    assert response.status_code == 404
    assert await fx.events_for(trigger_id) == []


# --------------------------------------------------------------------------- #
# The acknowledgement budget and the audit trail
# --------------------------------------------------------------------------- #


async def test_concurrent_deliveries_are_acknowledged_without_calling_out(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    """Slack gives three seconds. The budget is verification and ledger writes, nothing else."""
    import httpx

    async def _no_outbound(*_args, **_kwargs):
        msg = "ingress must not make outbound HTTP calls inside the request"
        raise AssertionError(msg)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _no_outbound)
    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    bodies = []
    for index in range(25):
        body = fx.load("message_channel")
        body["event_id"] = f"Ev0CON{index:05d}"
        bodies.append(json.dumps(body).encode())

    responses = await asyncio.gather(*[_deliver(client, body) for body in bodies])

    assert {response.status_code for response in responses} == {202}
    assert len(await fx.events_for(trigger_id)) == 25


async def test_retry_headers_are_audited_and_never_reach_the_flow(
    client: AsyncClient, active_user, flow, monkeypatch
) -> None:
    from langflow.services.authorization.audit import drain_pending_audit_writes
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import get_settings_service, session_scope
    from sqlmodel import select

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    trigger_id = await fx.arm(flow.id, active_user.id, await fx.make_oauth_connection(active_user.id))
    try:
        response = await _deliver(
            client, "message_channel", headers={"X-Slack-Retry-Num": "2", "X-Slack-Retry-Reason": "http_timeout"}
        )
        await drain_pending_audit_writes()
    finally:
        await drain_pending_audit_writes()

    assert response.status_code == 202
    [row] = await fx.events_for(trigger_id)
    assert "retry" not in json.dumps(row.payload)
    async with session_scope() as session:
        audits = (
            await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.action == "trigger_ingress:accept"))
        ).all()
    ours = [audit for audit in audits if audit.details.get("slack_event_id") == "Ev0MSG00001"]
    assert len(ours) == 1
    assert ours[0].details["retry_num"] == "2"
    assert ours[0].details["retry_reason"] == "http_timeout"
    assert ours[0].details["matched"] == 1
    assert ours[0].details["trigger_ids"] == [str(trigger_id)]
