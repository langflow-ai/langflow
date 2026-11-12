"""Provider receiver reservations retain the shared subscription audit contract."""

import traceback
from uuid import uuid4

import pytest
from langflow.services.authorization import audit
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers.providers.discord import lifecycle as discord
from langflow.services.triggers.providers.github import runtime as github
from langflow.services.triggers.providers.telegram import lifecycle as telegram
from langflow.services.triggers.providers.whatsapp import lifecycle as whatsapp
from sqlalchemy import event
from sqlmodel import select
from structlog.testing import capture_logs

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(params=[telegram, discord, whatsapp, github], ids=["telegram", "discord", "whatsapp", "github"])
def lifecycle(request, monkeypatch):
    async def address(_session, _trigger):
        return "https://private-callback.example/receiver"

    if request.param is not discord:
        monkeypatch.setattr(request.param, "source_ingress_url", address)
    for key, value in {
        "APP_ID": "111",
        "WABA_ID": "222",
        "PHONE_ID": "333",
        "GRAPH_VERSION": "v25.0",
        "APP_SECRET": "a" * 32,
    }.items():
        monkeypatch.setenv("LANGFLOW_WHATSAPP_" + key, value)
    return request.param


@pytest.fixture
async def provider_trigger(make_trigger, trigger_owner, lifecycle):
    provider, kind, identity, config = {
        telegram: (
            "telegram",
            "telegram.message",
            {"identity": "bot", "account": {"id": "123456789", "display": "example_bot"}},
            {"allowed_chats": ["123"], "mechanism_id": "telegram.webhook"},
        ),
        discord: (
            "discord",
            "discord.message",
            {"identity": "bot", "account": {"id": "123456789"}},
            {"mechanism_id": "discord.gateway"},
        ),
        whatsapp: (
            "whatsapp",
            "whatsapp.event",
            {"identity": "service", "account": {"id": "333", "tenant_id": "111:222"}},
            {"mechanism_id": "whatsapp.webhook"},
        ),
        github: ("github", "github.issue", {"identity": "bot"}, {"repository": "private-owner/private-repo"}),
    }[lifecycle]
    async with session_scope() as session:
        connection = Connection(
            owner_id=trigger_owner,
            provider_key=provider,
            name=f"audit-{uuid4().hex[:8]}",
            display_name="Subscription audit",
            executing_identity=identity,
        )
        session.add(connection)
        await session.flush()
        connection_id = connection.id
    return await make_trigger(provider=provider, kind=kind, config=config, connection_id=connection_id)


async def _new_reservation(session, lifecycle, trigger_id):
    trigger = await session.get(Trigger, trigger_id)
    trigger.state = "pending"
    session.add(trigger)
    await session.flush()
    await lifecycle.prepare(session, trigger)
    return (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger_id, TriggerSubscription.state != "expired"
            )
        )
    ).one()


async def _creation_audits(session, trigger_id):
    return (
        await session.exec(
            select(AuthzAuditLog).where(
                AuthzAuditLog.resource_id == trigger_id, AuthzAuditLog.action == "trigger_subscription:create"
            )
        )
    ).all()


@pytest.mark.parametrize("durable", [False, True], ids=["best-effort", "durable"])
async def test_provider_creation_is_audited_once_per_new_local_row(provider_trigger, lifecycle, monkeypatch, durable):
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", durable)
    async with session_scope() as session:
        first = await _new_reservation(session, lifecycle, provider_trigger)
        first_id = first.id
        await lifecycle.prepare(session, await session.get(Trigger, provider_trigger))
    async with session_scope() as session:
        rows = await _creation_audits(session, provider_trigger)
        assert len(rows) == 1
        assert rows[0].resource_type == "trigger"
        assert rows[0].result == "allow"
        assert rows[0].details == {"subscriptions": 1}
        first = await session.get(TriggerSubscription, first_id)
        first.state = "expired"
        session.add(first)
        await session.flush()
        replacement = await _new_reservation(session, lifecycle, provider_trigger)
        assert replacement.id != first_id
        await lifecycle.prepare(session, await session.get(Trigger, provider_trigger))
    async with session_scope() as session:
        rows = await _creation_audits(session, provider_trigger)
        assert len(rows) == 2
        assert all(row.details == {"subscriptions": 1} for row in rows)


@pytest.mark.parametrize("durable", [False, True], ids=["best-effort", "durable"])
async def test_provider_creation_audit_rolls_back_with_reservation(provider_trigger, lifecycle, monkeypatch, durable):
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", durable)
    async with session_scope() as session:
        await _new_reservation(session, lifecycle, provider_trigger)
        await session.rollback()
    async with session_scope() as session:
        assert (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == provider_trigger))
        ).all() == []
        assert await _creation_audits(session, provider_trigger) == []


@pytest.mark.parametrize("durable", [False, True], ids=["best-effort", "durable"])
@pytest.mark.parametrize("failure_point", ["stage", "insert"])
async def test_provider_creation_respects_audit_failure_mode(
    provider_trigger, lifecycle, monkeypatch, durable, caplog, failure_point
):
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", durable)

    def fail_stage(*_args, **_kwargs):
        message = "private-provider-audit-detail"
        raise RuntimeError(message)

    if failure_point == "stage":
        monkeypatch.setattr(audit, "_stage_audit_entries", fail_stage)
    else:
        event.listen(AuthzAuditLog, "before_insert", fail_stage)
    try:
        with capture_logs() as records:
            if durable:
                with pytest.raises(audit.AuditPersistenceError) as raised:
                    async with session_scope() as session:
                        await _new_reservation(session, lifecycle, provider_trigger)
                assert "private-provider-audit-detail" not in "".join(traceback.format_exception(raised.value))
            else:
                async with session_scope() as session:
                    await _new_reservation(session, lifecycle, provider_trigger)
    finally:
        if failure_point == "insert":
            event.remove(AuthzAuditLog, "before_insert", fail_stage)
    async with session_scope() as session:
        rows = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == provider_trigger))
        ).all()
        assert len(rows) == (0 if durable else 1)
        assert await _creation_audits(session, provider_trigger) == []
    assert "private-provider-audit-detail" not in caplog.text
    assert "private-provider-audit-detail" not in str(records)


async def test_provider_creation_keeps_auditing_disabled(provider_trigger, lifecycle, monkeypatch):
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", False)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", True)
    async with session_scope() as session:
        await _new_reservation(session, lifecycle, provider_trigger)
    async with session_scope() as session:
        assert await _creation_audits(session, provider_trigger) == []
