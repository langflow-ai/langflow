"""Trigger cleanup and pin retention with SQLite foreign keys both on and off."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry, delete_flow_version_entry
from langflow.services.database.models.flow_version.exceptions import FlowVersionError
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.triggers.service import TriggerService
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(params=[False, True], ids=["foreign-keys-off", "foreign-keys-on"])
async def trigger_db(request):
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def set_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys={'ON' if request.param else 'OFF'}")
        cursor.close()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()


async def _seed_trigger(session):
    owner = User(username=f"lifecycle-{uuid4().hex}", password=str(uuid4()), is_active=True)
    session.add(owner)
    await session.flush()
    flow = Flow(name="Lifecycle flow", user_id=owner.id)
    session.add(flow)
    await session.flush()
    version = FlowVersion(flow_id=flow.id, user_id=owner.id, version_number=1, data={"nodes": []})
    session.add(version)
    await session.flush()
    trigger = Trigger(
        flow_id=flow.id,
        user_id=owner.id,
        name="Pinned trigger",
        kind="schedule",
        flow_version_id=version.id,
        state="active",
    )
    session.add(trigger)
    await session.flush()
    original = TriggerEvent(trigger_id=trigger.id, dedupe_key="original", payload={"private": "payload"})
    session.add(original)
    await session.flush()
    replay = TriggerEvent(trigger_id=trigger.id, dedupe_key="replay", replay_of_event_id=original.id)
    subscription = TriggerSubscription(
        trigger_id=trigger.id,
        provider="test",
        provider_subscription_id=uuid4().hex,
    )
    session.add_all([replay, subscription])
    await session.commit()
    return flow, version, trigger


@pytest.mark.parametrize("target", ["trigger", "flow"])
async def test_deletion_removes_trigger_children(trigger_db, target):
    session = trigger_db
    flow, _version, trigger = await _seed_trigger(session)
    _other_flow, _other_version, other = await _seed_trigger(session)
    if target == "trigger":
        await TriggerService().delete(session, row=trigger)
    else:
        await cascade_delete_flow(session, flow.id)
    await session.commit()
    session.expunge_all()
    assert await session.get(Trigger, trigger.id) is None
    assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
    assert not (
        await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == trigger.id))
    ).all()
    assert await session.get(Trigger, other.id) is not None
    assert len((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == other.id))).all()) == 2


async def test_pruning_keeps_pinned_version_until_unpinned(trigger_db, monkeypatch):
    session = trigger_db
    flow, version, trigger = await _seed_trigger(session)
    monkeypatch.setattr(
        "langflow.services.database.models.flow_version.crud.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(max_flow_version_entries_per_flow=1)),
    )
    for _ in range(2):
        await create_flow_version_entry(session, flow.id, flow.user_id, {"nodes": []})
        await session.commit()
    await session.refresh(trigger)
    assert trigger.flow_version_id == version.id
    assert await session.get(FlowVersion, version.id) is not None
    assert len((await session.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all()) == 2

    await TriggerService().pin(session, row=trigger, flow_version_id=None)
    await session.commit()
    await create_flow_version_entry(session, flow.id, flow.user_id, {"nodes": []})
    await session.commit()
    session.expunge_all()
    assert await session.get(FlowVersion, version.id) is None


async def test_explicit_version_deletion_requires_unpinning(trigger_db):
    session = trigger_db
    flow, version, trigger = await _seed_trigger(session)
    with pytest.raises(FlowVersionError, match="pinned"):
        await delete_flow_version_entry(session, version.id, flow.user_id)
    await session.refresh(trigger)
    assert trigger.flow_version_id == version.id
    await TriggerService().pin(session, row=trigger, flow_version_id=None)
    await delete_flow_version_entry(session, version.id, flow.user_id)
    await session.commit()
    session.expunge_all()
    assert await session.get(FlowVersion, version.id) is None
