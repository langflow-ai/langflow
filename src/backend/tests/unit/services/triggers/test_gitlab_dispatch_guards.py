"""Classify signed GitLab actors before a background flow starts."""

import pytest
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher
from langflow.services.triggers.principal import trigger_execution_principal
from langflow.services.triggers.service import TriggerService
from sqlmodel import select

from tests.unit.services.triggers.test_gitlab_lifecycle import connection, gitlab, reconcile  # noqa: F401
from tests.unit.services.triggers.test_gitlab_provider import payload, signed

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("kind", ["issue", "merge_request"])
@pytest.mark.parametrize(("actor_bot", "include_bots"), [(True, False), (True, True), (False, False)])
async def test_real_webhook_actor_without_bot_flag_is_checked_before_dispatch(
    gitlab,  # noqa: F811
    trigger_owner,
    owned_flow,
    client,
    fake_background_service,
    kind,
    actor_bot,
    include_bots,
):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner, kind=kind)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        row.config = {**row.config, "include_bot_events": include_bots}
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    gitlab.actor_bot = actor_bot
    request = signed(payload(f"gitlab.{kind}"), secret=secret)
    count = len(gitlab.requests)
    response = await client.post(
        f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers
    )
    assert response.status_code == 202
    assert len(gitlab.requests) == count
    expected = int(not actor_bot or include_bots)
    assert await dispatcher.run_once(owner="gitlab-actor-guard") == expected
    assert len(fake_background_service.submits) == expected
    assert gitlab.requests[-1].url.path == "/api/v4/users/11"
    async with session_scope() as session:
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).one()
        if not expected:
            assert event.state == "completed"
            assert event.job_id is None


@pytest.mark.parametrize("status", [401, 429, 503])
async def test_actor_lookup_failure_never_runs_a_flow(
    gitlab,  # noqa: F811
    trigger_owner,
    owned_flow,
    client,
    fake_background_service,
    status,
):
    created = await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    gitlab.actor_status = status
    request = signed(secret=secret)
    response = await client.post(
        f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers
    )
    assert response.status_code == 202
    assert await dispatcher.run_once(owner="gitlab-actor-failure") == 0
    assert fake_background_service.submits == []
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        credential = await session.get(Connection, created.id)
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).one()
        if status == 401:
            assert credential.status == "expired"
            assert row.state == "needs_reconnect"
        else:
            assert row.state == "active"
            assert credential.status == "ready"
            assert event.state == "pending"
            assert event.attempt == 1


@pytest.mark.parametrize("detection", ["health", "action"])
async def test_previously_detected_revocation_requires_reconnect_and_explicit_resume(
    gitlab,  # noqa: F811
    trigger_owner,
    owned_flow,
    client,
    fake_background_service,
    detection,
):
    from langflow.api.v1.triggers_helpers import present_one
    from langflow.services.connection.service import DatabaseConnectionResolverService
    from langflow.services.database.models.connection.schemas import ConnectionTokenRenewal
    from langflow.services.database.models.user.model import User
    from langflow.services.triggers.providers.gitlab import runtime
    from langflow.services.triggers.source_clients import source_lease
    from lfx.integrations.errors import AuthExpiredError

    created = await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    gitlab.token_revoked = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        if detection == "health":
            stored = await session.get(Connection, created.id)
            result = await DatabaseConnectionResolverService().check_health(
                session, row=stored, principal=trigger_execution_principal(row)
            )
            assert result.status == "expired"
        else:
            lease = await source_lease(session, row, family="trigger_push")
            async with runtime.GitLabClient(lease) as provider:
                with pytest.raises(AuthExpiredError):
                    await provider.request("GET", "/projects/80")
    request = signed(secret=secret)
    assert (
        await client.post(f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers)
    ).status_code == 202
    assert await dispatcher.run_once(owner="gitlab-known-revocation") == 0
    assert fake_background_service.submits == []
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert row.state == "needs_reconnect"
        user = await session.get(User, trigger_owner)
        assert (await present_one(session, user, row)).reason == "needs_reconnect"
    gitlab.token_revoked = False
    async with session_scope() as session:
        stored = await session.get(Connection, created.id)
        user = await session.get(User, trigger_owner)
        await DatabaseConnectionResolverService().renew_token(
            session,
            row=stored,
            user=user,
            payload=ConnectionTokenRenewal(
                credentials={"access_token": "synthetic-gitlab-token"}, allow_non_interactive=True
            ),
        )
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        user = await session.get(User, trigger_owner)
        shown = await present_one(session, user, row)
        assert shown.reason == "ready_to_resume"
        assert "resume" in shown.allowed_actions
        assert row.state == "needs_reconnect"
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"


@pytest.mark.parametrize("reason", ["credential-undecryptable", "registration-unavailable"])
@pytest.mark.usefixtures("gitlab")
async def test_worker_configuration_failure_retries_without_reconnect(
    trigger_owner, owned_flow, client, fake_background_service, monkeypatch, reason
):
    from langflow.services.triggers.providers.gitlab import runtime
    from lfx.integrations.errors import ConnectionUnresolvedError

    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    request = signed(secret=secret)
    assert (
        await client.post(f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers)
    ).status_code == 202

    def broken_client(_lease):
        handle = "gitlab/work"
        raise ConnectionUnresolvedError(handle, provider="gitlab", reason=reason)

    monkeypatch.setattr(runtime, "GitLabClient", broken_client)
    assert await dispatcher.run_once(owner="gitlab-local-config") == 0
    assert fake_background_service.submits == []
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).one()
        assert row.state == "active"
        assert event.state == "pending"
        assert event.attempt == 1


@pytest.mark.parametrize("failure", ["auth", "policy"])
@pytest.mark.usefixtures("gitlab")
async def test_expired_holder_cannot_disarm_a_trigger_after_provider_io(
    trigger_owner, owned_flow, client, fake_background_service, monkeypatch, failure
):
    from datetime import datetime, timedelta, timezone

    from langflow.services.triggers.lease_guard import LeaseLostError
    from langflow.services.triggers.providers.gitlab import runtime
    from lfx.integrations.errors import AuthExpiredError, IntegrationPolicyBlockedError

    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    request = signed(secret=secret)
    assert (
        await client.post(f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers)
    ).status_code == 202

    def slow_rejected_client(_lease):
        expired = datetime.now(timezone.utc) + timedelta(days=1)
        monkeypatch.setattr(dispatcher, "_now", lambda: expired)
        error = AuthExpiredError if failure == "auth" else IntegrationPolicyBlockedError
        raise error(provider="gitlab")

    monkeypatch.setattr(runtime, "GitLabClient", slow_rejected_client)
    with pytest.raises(LeaseLostError):
        await dispatcher.run_once(owner="gitlab-expired-holder")
    assert fake_background_service.submits == []
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).one()
        assert row.state == "active"
        assert event.state == "claimed"
        assert event.error is None
