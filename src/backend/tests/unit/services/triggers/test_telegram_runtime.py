"""Telegram bundle ownership and the shared source lifecycle operate together."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import lfx_telegram
import pytest
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import source_runtime
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest, IngressSecrets
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.telegram.ingress import verify
from langflow.services.triggers.providers.telegram.provider import PROVIDER
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_delivery import append_and_advance
from lfx.extension import bundle_registry, load_extension
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry
from sqlmodel import select

from .providers.telegram.telegram_test_support import BOT, TOKEN, BotTransport
from .providers.telegram.test_telegram_events import CONFIG, UPDATE

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def telegram_provider(monkeypatch, client):  # noqa: ARG001 - initialize shared services first
    loaded = load_extension(Path(lfx_telegram.__file__).parent, distribution="lfx-telegram")
    assert loaded.ok, loaded.errors
    actual = BundleRegistry()
    actual.install_bundle(
        BundleRecord(
            bundle="telegram",
            extension_id="lfx-telegram",
            extension_version="0.1.0",
            slot="official",
            components=tuple(loaded.components),
            integrations=tuple(loaded.integrations),
        )
    )
    monkeypatch.setattr(bundle_registry, "get_default_registry", lambda: actual)
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_providers", {})
    original = registry.metadata.entry_points
    installed = [entry for entry in original(group=registry.ENTRY_POINT_GROUP) if entry.name == "telegram"]
    # CI can exercise the source contract before the new package is included
    # in the collective bundle profile. The wheel smoke uses the real entry.
    if not installed:
        entry = SimpleNamespace(
            name="telegram", dist=SimpleNamespace(metadata={"Name": "lfx-telegram"}), load=lambda: PROVIDER
        )
        monkeypatch.setattr(
            registry.metadata,
            "entry_points",
            lambda **kwargs: [entry] if kwargs.get("group") == registry.ENTRY_POINT_GROUP else original(**kwargs),
        )
    assert registry.get_provider("telegram") is PROVIDER
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "trigger_ingress_origin", "https://langflow.example")
    return PROVIDER


async def connection(owner_id, *, allow=True):
    async with session_scope() as session:
        user = await session.get(User, owner_id)
        return await DatabaseConnectionResolverService().create(
            session,
            user=user,
            payload=ConnectionCreate(
                provider_key="telegram",
                name="bot",
                display_name="Telegram bot",
                executing_identity={"identity": "bot"},
                allow_non_interactive=allow,
                credentials={"access_token": TOKEN},
            ),
        )


async def reconcile(flow_id, owner_id, *, delivery="push"):
    values = {
        "connection": "telegram/bot",
        "allowed_chats": CONFIG["allowed_chats"],
        "delivery_mode": delivery,
        "session_scope": "thread",
        "allowed_senders": [],
    }
    data = {
        "nodes": [
            {
                "id": "telegram-source",
                "data": {
                    "type": "ext:telegram:TelegramOnMessageTriggerComponent@official",
                    "node": {"template": {key: {"value": value} for key, value in values.items()}},
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


@pytest.mark.usefixtures("telegram_provider")
async def test_telegram_webhook_canonical_intake_and_pause_cleanup(trigger_owner, owned_flow, client, monkeypatch):
    transport = BotTransport([BOT, BOT, {"url": ""}, True]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
        snapshot = dict(row.config)
    url = f"/api/v1/triggers/ingress/telegram/{public_id}"
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret}
    for _ in range(2):
        response = await client.post(url, content=json.dumps(UPDATE), headers=headers)
        assert response.status_code == 202, response.text
    assert await source_runtime.sync_source(row.id) == 0
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == row.id))).all()
        assert len(events) == 1
        assert events[0].payload["data"]["chat_id"] == "-1001234"
        assert events[0].payload["session_key"] == "telegram:123456789:-1001234:thread:4"
        source_items = verify(
            IngressRequest(provider="telegram", body=json.dumps(UPDATE).encode(), headers=headers, query={}),
            IngressSecrets(
                signing_secret=secret,
                resource_id="123456789",
                channel_id="example_bot",
                target_kind="telegram.message",
                target_config=snapshot,
            ),
            tolerance_s=300,
        ).source_items
        assert (
            await append_and_advance(
                session, trigger_id=row.id, items=list(source_items), cursor=None, expected_config=snapshot
            )
            == 0
        )
        row = await session.get(Trigger, row.id)
        await TriggerService().disable(session, row=row)
        subscriptions = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).all()
        assert len(subscriptions) == 1
        assert subscriptions[0].state == "expired"
        assert (
            await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))
        ).one().provider_subscription_id == "bot:123456789"
    assert [method for method, _ in transport.calls] == [
        "getMe",
        "getMe",
        "getWebhookInfo",
        "setWebhook",
    ]
    response = await client.post(url, content=json.dumps(UPDATE), headers=headers)
    assert response.status_code == 404


@pytest.mark.usefixtures("telegram_provider")
async def test_telegram_polling_admission_and_pause_retains_cleanup(trigger_owner, owned_flow, monkeypatch):
    transport = BotTransport([BOT]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner, delivery="poll")
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.config["mechanism_id"] == "telegram.get_updates"
        await TriggerService().disable(session, row=row)
        assert (
            await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))
        ).one().provider_state["transport"] == "telegram.get_updates"
    assert [method for method, _ in transport.calls] == ["getMe"]


@pytest.mark.parametrize("header", [None, "wrong", "é", "x" * 257])
def test_webhook_requires_exact_secret_header(header):
    headers = {} if header is None else {"X-Telegram-Bot-Api-Secret-Token": header}
    with pytest.raises(IngressRejected, match="bad_signature"):
        verify(
            IngressRequest(provider="telegram", body=json.dumps(UPDATE).encode(), headers=headers, query={}),
            IngressSecrets(
                signing_secret="expected_header",  # noqa: S106  # pragma: allowlist secret - synthetic header
                resource_id="123456789",
                channel_id="example_bot",
                target_kind="telegram.message",
                target_config=CONFIG,
            ),
            tolerance_s=300,
        )


def test_signed_unrelated_chat_is_acknowledged_without_event():
    secret = "expected_header"  # noqa: S105  # pragma: allowlist secret - synthetic header
    result = verify(
        IngressRequest(
            provider="telegram",
            body=json.dumps(UPDATE).encode(),
            headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            query={},
        ),
        IngressSecrets(
            signing_secret=secret,
            resource_id="123456789",
            channel_id="example_bot",
            target_kind="telegram.message",
            target_config={**CONFIG, "allowed_chats": ["-99"]},
        ),
        tolerance_s=300,
    )
    assert result.source_items == ()
    assert result.handshake is None


@pytest.mark.usefixtures("telegram_provider")
@pytest.mark.parametrize("failure", ["foreign-owner", "consent", "identity", "policy"])
async def test_telegram_admission_enforces_owner_consent_identity_and_policy(
    trigger_owner, owned_flow, monkeypatch, failure
):
    from dataclasses import replace
    from uuid import uuid4

    from langflow.services.database.models.connection.model import Connection
    from lfx.integrations.errors import IntegrationPolicyBlockedError
    from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service

    transport = BotTransport([BOT]).install(monkeypatch)
    owner_id = trigger_owner
    if failure == "foreign-owner":
        async with session_scope() as session:
            other = User(username=f"telegram-other-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    created = await connection(owner_id, allow=failure != "consent")
    if failure == "identity":
        async with session_scope() as session:
            row = await session.get(Connection, created.id)
            row.executing_identity = {"identity": "service"}
            session.add(row)
    trigger = await reconcile(owned_flow, trigger_owner, delivery="poll")
    policy = get_policy_bundle_service()
    original = policy.snapshot
    if failure == "policy":
        policy.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.telegram.trigger.message"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable_and_activate(session, row=row)
            assert not (
                await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
            ).all()
        assert transport.calls == [("getMe", {})]
    finally:
        policy.publish(replace(original, revision=policy.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


@pytest.mark.usefixtures("telegram_provider")
async def test_registered_telegram_poll_adapter_commits_before_confirming_cursor(
    trigger_owner, owned_flow, monkeypatch
):
    import asyncio

    from langflow.services.triggers.listeners.adapters import (
        ListenerContext,
        ListenerTrigger,
        build_adapter,
        register_builtin_adapters,
    )

    transport = BotTransport([BOT, BOT, {"url": ""}, [UPDATE], BOT, {"url": ""}, []]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner, delivery="poll")
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        snapshot = ListenerTrigger(
            id=row.id,
            flow_id=row.flow_id,
            user_id=row.user_id,
            kind=row.kind,
            provider=row.provider,
            mechanism_id=row.config["mechanism_id"],
            config=dict(row.config),
            provider_state=dict(row.provider_state),
        )
        connection_id = row.connection_id

    async def unused(**_kwargs):
        pytest.fail("The source adapter must commit its canonical items through the shared source runtime.")

    register_builtin_adapters()
    adapter = build_adapter(snapshot)
    assert adapter is not None
    context = ListenerContext(
        connection_id=connection_id,
        triggers=[snapshot],
        emit=unused,
        save_cursor=unused,
        resolve_credential=unused,
        stopping=asyncio.Event(),
    )
    assert await adapter.poll(context) == 1
    async with session_scope() as session:
        current = await session.get(Trigger, snapshot.id)
        assert current.provider_state["offset"] == 10
        assert len((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == snapshot.id))).all()) == 1
    assert await adapter.poll(context) == 0
    async with session_scope() as session:
        current = await session.get(Trigger, snapshot.id)
        assert current.provider_state["offset"] is None
    calls = [payload for method, payload in transport.calls if method == "getUpdates"]
    assert len(calls) == 2
    assert "offset" not in calls[0]
    assert calls[1]["offset"] == 10
