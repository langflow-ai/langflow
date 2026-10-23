"""Installed Discord ownership, admission, and pause use the shared runtime."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import lfx_discord
import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers.listeners.adapters import ListenerTrigger, build_adapter
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.discord.gateway import DiscordGatewayAdapter
from langflow.services.triggers.providers.discord.lifecycle import revoke
from langflow.services.triggers.providers.discord.provider import PROVIDER
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import run_cleanup_pass
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx.extension import bundle_registry, load_extension
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry
from sqlmodel import select

from .providers.discord.support import APP, BOT, TOKEN, BotTransport

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def discord_provider(monkeypatch, client):  # noqa: ARG001 - initialize shared services
    loaded = load_extension(Path(lfx_discord.__file__).parent, distribution="lfx-discord")
    assert loaded.ok, loaded.errors
    actual = BundleRegistry()
    actual.install_bundle(
        BundleRecord(
            bundle="discord",
            extension_id="lfx-discord",
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
    entry = SimpleNamespace(
        name="discord", dist=SimpleNamespace(metadata={"Name": "lfx-discord"}), load=lambda: PROVIDER
    )
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [entry] if kwargs.get("group") == registry.ENTRY_POINT_GROUP else original(**kwargs),
    )
    assert registry.get_provider("discord") is PROVIDER
    return actual


async def connection(owner_id, *, allow=True, name="bot"):
    async with session_scope() as session:
        user = await session.get(User, owner_id)
        return await DatabaseConnectionResolverService().create(
            session,
            user=user,
            payload=ConnectionCreate(
                provider_key="discord",
                name=name,
                display_name="Discord bot",
                executing_identity={"identity": "bot"},
                allow_non_interactive=allow,
                credentials={"access_token": TOKEN},
            ),
        )


async def reconcile(flow_id, owner_id, *, name="bot"):
    component = lfx_discord.DiscordOnMessageTriggerComponent(
        connection=f"discord/{name}", guild_id="222", channel_ids=["333"]
    )
    values = component.trigger_config()
    data = {
        "nodes": [
            {
                "id": "discord-source",
                "data": {
                    "type": "ext:discord:DiscordOnMessageTriggerComponent@official",
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


@pytest.mark.usefixtures("discord_provider")
async def test_enable_pause_pending_cleanup_then_reenable_does_not_delete_replacement(
    trigger_owner, owned_flow, monkeypatch
):
    transport = BotTransport([BOT, APP]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.config["mechanism_id"] == "discord.gateway"
        old = (await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))).one()
        old_id = old.id
        await TriggerService().disable(session, row=row)
        assert old.state == "expired"
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).one()
        task_copy = SimpleNamespace(
            provider_state=dict(task.provider_state), provider_subscription_id=task.provider_subscription_id
        )
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        with pytest.raises(SourceConfigurationError, match="cleanup is pending"):
            await TriggerService().enable(session, row=row)
    # Socket cleanup is local and can never delete a later external receiver.
    await revoke(task_copy, None)
    result = await run_cleanup_pass()
    assert result == 1
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable(session, row=row)
        new = (await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))).one()
        assert new.id != old_id
        assert new.state == "active"
        await revoke(task_copy, None)
        assert new.state == "active"
    assert len(transport.calls) == 2


@pytest.mark.usefixtures("discord_provider")
async def test_second_connection_cannot_claim_same_verified_bot(trigger_owner, owned_flow, monkeypatch):
    from langflow.services.database.models.flow.model import Flow

    BotTransport([BOT, APP, BOT, APP]).install(monkeypatch)
    await connection(trigger_owner)
    await connection(trigger_owner, name="other")
    first = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, first.id)
        await TriggerService().enable(session, row=row)
        flow = Flow(name="second Discord", user_id=trigger_owner, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    second = await reconcile(flow_id, trigger_owner, name="other")
    async with session_scope() as session:
        row = await session.get(Trigger, second.id)
        with pytest.raises(SourceConfigurationError, match="already has a receiver"):
            await TriggerService().enable(session, row=row)


@pytest.mark.usefixtures("discord_provider")
async def test_missing_background_consent_is_rejected(trigger_owner, owned_flow, monkeypatch):
    BotTransport([BOT, APP]).install(monkeypatch)
    await connection(trigger_owner, allow=False)
    row = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        with pytest.raises(ValueError, match=r"consent|non.interactive|background"):
            await TriggerService().enable(session, row=row)


@pytest.mark.usefixtures("discord_provider")
async def test_cross_owner_connection_is_rejected(trigger_owner, owned_flow, monkeypatch):
    BotTransport([BOT, APP]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        row.user_id = uuid4()
        with pytest.raises(ValueError, match="connection its owner owns"):
            await TriggerService().enable(session, row=row)


@pytest.mark.usefixtures("discord_provider")
async def test_actual_descriptor_builds_gateway_adapter(trigger_owner, owned_flow, monkeypatch):
    BotTransport([BOT, APP]).install(monkeypatch)
    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable(session, row=row)
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
    adapter = build_adapter(snapshot)
    assert isinstance(adapter, DiscordGatewayAdapter)
    assert adapter.state["bot_id"] == BOT["id"]


@pytest.mark.usefixtures("discord_provider")
async def test_policy_denial_precedes_receiver_claim(trigger_owner, owned_flow, monkeypatch):
    from dataclasses import replace

    from lfx.integrations.errors import IntegrationPolicyBlockedError
    from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service

    BotTransport([BOT, APP]).install(monkeypatch)
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    policy = get_policy_bundle_service()
    original = policy.snapshot
    policy.publish(
        replace(
            original,
            revision=original.revision + 1,
            initialized=True,
            blocked_integration_action_keys=frozenset({"integrations.discord.trigger.message"}),
        )
    )
    get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises(IntegrationPolicyBlockedError):
                await TriggerService().enable(session, row=row)
            assert not (
                await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
            ).all()
    finally:
        policy.publish(replace(original, revision=policy.snapshot.revision + 1))
        get_integration_policy_service().invalidate()
