"""Real database receiver claims and safe Telegram webhook cleanup."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.triggers.providers.telegram.lifecycle import _claim, prepare, provision, revoke
from langflow.services.triggers.source_errors import SourceConfigurationError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .telegram_test_support import BOT, BotTransport, lease
from .test_telegram_events import CONFIG


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: SQLModel.metadata.create_all(
                sync, tables=[Trigger.__table__, TriggerSubscription.__table__, TriggerCleanup.__table__]
            )
        )
    yield engine
    await engine.dispose()


async def saved_trigger(session, mechanism="telegram.get_updates"):
    trigger = Trigger(
        flow_id=uuid4(),
        user_id=uuid4(),
        name="Telegram",
        kind="telegram.message",
        provider="telegram",
        config={**CONFIG, "connection": "telegram/bot", "mechanism_id": mechanism},
        connection_id=uuid4(),
        public_id=uuid4().hex,
        signing_secret_encrypted="encrypted",  # noqa: S106  # pragma: allowlist secret - synthetic envelope
        state="active",
    )
    session.add(trigger)
    await session.flush()
    return trigger


async def test_unique_claim_rejects_a_second_trigger_even_with_a_different_connection(database):
    async with AsyncSession(database, expire_on_commit=False) as session:
        first = await saved_trigger(session)
        second = await saved_trigger(session)
        row = await _claim(session, first, bot={"id": "123456789", "username": "example_bot"}, address=None)
        await session.commit()
        with pytest.raises(SourceConfigurationError, match="already has an active trigger"):
            await _claim(session, second, bot={"id": "123456789", "username": "example_bot"}, address=None)
        assert (await session.exec(select(TriggerSubscription))).all() == [row]
        assert await _claim(session, first, bot={"id": "123456789", "username": "example_bot"}, address=None) is row


async def test_cleanup_blocks_replacement_even_after_trigger_cascade_removed_claim(database):
    async with AsyncSession(database) as session:
        trigger = await saved_trigger(session)
        task = TriggerCleanup(
            id=uuid4(),
            trigger_id=uuid4(),
            user_id=trigger.user_id,
            provider="telegram",
            kind="telegram.message",
            provider_subscription_id="bot:123456789",
        )
        session.add(task)
        await session.flush()
        with pytest.raises(SourceConfigurationError, match="cleanup is pending"):
            await _claim(session, trigger, bot={"id": "123456789", "username": "example_bot"}, address=None)
        await session.delete(task)
        await session.flush()
        row = await _claim(session, trigger, bot={"id": "123456789", "username": "example_bot"}, address=None)
        assert row.trigger_id == trigger.id


async def test_expired_claim_is_replaced_only_after_cleanup_finishes(database):
    async with AsyncSession(database) as session:
        first = await saved_trigger(session)
        second = await saved_trigger(session)
        old = await _claim(session, first, bot={"id": "123456789", "username": "example_bot"}, address=None)
        old.state = "expired"
        session.add(old)
        await session.flush()
        new = await _claim(session, second, bot={"id": "123456789", "username": "example_bot"}, address=None)
        assert new.id != old.id
        assert new.trigger_id == second.id
        assert len((await session.exec(select(TriggerSubscription))).all()) == 1


async def test_bot_or_transport_change_requires_cleanup(database):
    async with AsyncSession(database) as session:
        trigger = await saved_trigger(session)
        await _claim(session, trigger, bot={"id": "123456789", "username": "example_bot"}, address=None)
        trigger.config = {**trigger.config, "mechanism_id": "telegram.webhook"}
        with pytest.raises(SourceConfigurationError, match="changing its transport"):
            await _claim(
                session,
                trigger,
                bot={"id": "123456789", "username": "example_bot"},
                address="https://example.test/hook",
            )
        with pytest.raises(SourceConfigurationError, match="changing the connected bot"):
            await _claim(
                session, trigger, bot={"id": "987654321", "username": "other_bot"}, address="https://example.test/hook"
            )


@pytest.mark.parametrize(
    ("current", "deleted"), [("https://other.invalid/hook", False), ("", False), ("https://ours.invalid/hook", True)]
)
async def test_cleanup_does_not_remove_another_trigger_receiver(monkeypatch, current, deleted):
    responses = [BOT, {"url": current}]
    if deleted:
        responses.append(True)
    transport = BotTransport(responses).install(monkeypatch)
    task = SimpleNamespace(
        provider_subscription_id="bot:123456789",
        provider_state={
            "bot_id": "123456789",
            "transport": "telegram.webhook",
            "callback_url": "https://ours.invalid/hook",
        },
    )
    await revoke(task, lease())
    assert ("deleteWebhook" in [method for method, _ in transport.calls]) is deleted
    if deleted:
        assert transport.calls[-1] == ("deleteWebhook", {"drop_pending_updates": False})


async def test_polling_cleanup_has_no_remote_side_effect(monkeypatch):
    transport = BotTransport([]).install(monkeypatch)
    await revoke(SimpleNamespace(provider_state={"transport": "telegram.get_updates"}), lease())
    assert transport.calls == []


async def test_prepare_rejects_empty_allowlist_before_any_network(database, monkeypatch):
    transport = BotTransport([]).install(monkeypatch)
    async with AsyncSession(database) as session:
        trigger = await saved_trigger(session)
        trigger.config = {**trigger.config, "allowed_chats": []}
        with pytest.raises(SourceConfigurationError, match="allowed Telegram chat"):
            await prepare(session, trigger)
    assert transport.calls == []


async def test_webhook_provision_is_owned_and_retains_pending_updates(database, monkeypatch):
    from langflow.services.triggers.providers.telegram import lifecycle

    transport = BotTransport([BOT, {"url": ""}, True]).install(monkeypatch)

    async def address(_session, _trigger):
        return "https://ours.invalid/hook"

    async def source(*_args, **_kwargs):
        return lease()

    monkeypatch.setattr(lifecycle, "source_ingress_url", address)
    monkeypatch.setattr(lifecycle, "source_lease", source)
    monkeypatch.setattr(lifecycle, "decrypt_api_key", lambda _value: "our_header_secret")
    async with AsyncSession(database) as session:
        trigger = await saved_trigger(session, "telegram.webhook")
        trigger.provider_state = {"bot_id": "123456789"}
        row = await _claim(
            session, trigger, bot={"id": "123456789", "username": "example_bot"}, address="https://ours.invalid/hook"
        )
        assert await provision(session, trigger) is row
        assert row.state == "active"
        assert row.expires_at is None
    assert transport.calls[-1] == (
        "setWebhook",
        {
            "url": "https://ours.invalid/hook",
            "secret_token": "our_header_secret",  # pragma: allowlist secret - synthetic header
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
            "max_connections": 1,
        },
    )


async def test_two_replica_sessions_admit_only_one_bot_receiver(tmp_path):
    import asyncio

    from langflow.services.triggers.locking import lock_trigger

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'telegram-claims.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: SQLModel.metadata.create_all(
                    sync, tables=[Trigger.__table__, TriggerSubscription.__table__, TriggerCleanup.__table__]
                )
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            first = await saved_trigger(session)
            second = await saved_trigger(session)
            ids = [first.id, second.id]
            await session.commit()

        async def reserve(trigger_id):
            async with AsyncSession(engine) as session:
                trigger = await lock_trigger(session, trigger_id)
                try:
                    await _claim(session, trigger, bot={"id": "123456789", "username": "example_bot"}, address=None)
                    await session.commit()
                except SourceConfigurationError:
                    await session.rollback()
                    return False
                return True

        outcomes = await asyncio.gather(*(reserve(trigger_id) for trigger_id in ids))
        assert sorted(outcomes) == [False, True]
        async with AsyncSession(engine) as session:
            assert len((await session.exec(select(TriggerSubscription))).all()) == 1
    finally:
        await engine.dispose()
