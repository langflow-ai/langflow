"""Source hints, canonical dedupe, and cursor commits use the real database."""

from __future__ import annotations

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerSourceVersion
from langflow.services.deps import session_scope
from langflow.services.triggers.source_delivery import append_and_advance, canonical_key
from sqlmodel import select


def _item(item_id: str, version: str) -> dict:
    return {
        "provider": "google",
        "resource": "calendar:primary",
        "id": item_id,
        "version": version,
        "deleted": False,
        "data": {"id": item_id, "etag": version},
    }


async def test_baseline_then_update_and_replay_share_one_canonical_event(make_trigger) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        assert (
            await append_and_advance(
                session, trigger_id=trigger_id, items=[_item("e1", "v1")], cursor={"sync_token": "t1"}, baseline=True
            )
            == 0
        )
    async with session_scope() as session:
        assert (
            await append_and_advance(
                session,
                trigger_id=trigger_id,
                items=[_item("e1", "v2")],
                cursor={"sync_token": "t2"},
                previous_cursor={"sync_token": "t1"},
            )
            == 1
        )
    async with session_scope() as session:
        assert (
            await append_and_advance(
                session, trigger_id=trigger_id, items=[_item("e1", "v2")], cursor={"sync_token": "t3"}
            )
            == 0
        )
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert [row.dedupe_key for row in rows] == [
            canonical_key(provider="google", resource="calendar:primary", item_id="e1", version="v2")
        ]
        assert (await session.get(Trigger, trigger_id)).provider_state == {"sync_token": "t3"}


async def test_failed_cursor_precondition_rolls_back_items(make_trigger) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google", provider_state={"sync_token": "new"})
    with pytest.raises(RuntimeError, match="cursor changed"):
        async with session_scope() as session:
            await append_and_advance(
                session,
                trigger_id=trigger_id,
                items=[_item("e1", "v1")],
                cursor={"sync_token": "older"},
                previous_cursor={"sync_token": "old"},
            )
    async with session_scope() as session:
        assert (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all() == []
        assert (await session.get(Trigger, trigger_id)).provider_state == {"sync_token": "new"}


async def test_full_resync_emits_only_changed_and_removed_items_after_ledger_purge(make_trigger) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        await append_and_advance(
            session,
            trigger_id=trigger_id,
            items=[_item("unchanged", "v1"), _item("removed", "v1")],
            cursor={"sync_token": "t1"},
            baseline=True,
        )
    async with session_scope() as session:
        created = await append_and_advance(
            session,
            trigger_id=trigger_id,
            items=[_item("unchanged", "v1"), _item("new", "v1")],
            cursor={"sync_token": "t2"},
            snapshot_resource="calendar:primary",
        )
        assert created == 2
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert {(row.payload["id"], row.payload["version"]) for row in rows} == {("new", "v1"), ("removed", "deleted")}
        versions = (
            await session.exec(select(TriggerSourceVersion).where(TriggerSourceVersion.trigger_id == trigger_id))
        ).all()
        assert len(versions) == 3


async def test_readded_item_can_emit_a_second_removal(make_trigger) -> None:
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    removed = {**_item("e1", "deleted"), "deleted": True, "data": {}}
    async with session_scope() as session:
        await append_and_advance(session, trigger_id=trigger_id, items=[_item("e1", "v1")], cursor=None, baseline=True)
    async with session_scope() as session:
        assert await append_and_advance(session, trigger_id=trigger_id, items=[removed], cursor=None) == 1
    async with session_scope() as session:
        assert await append_and_advance(session, trigger_id=trigger_id, items=[_item("e1", "v2")], cursor=None) == 1
    async with session_scope() as session:
        assert await append_and_advance(session, trigger_id=trigger_id, items=[removed], cursor=None) == 1
        assert await append_and_advance(session, trigger_id=trigger_id, items=[removed], cursor=None) == 0
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        removal_keys = [row.dedupe_key for row in rows if row.payload["deleted"]]
        assert len(removal_keys) == len(set(removal_keys)) == 2


async def test_large_batch_rolls_back_versions_events_and_cursor_together(make_trigger):
    trigger_id = await make_trigger(kind="google.calendar", provider="google")
    items = [_item(str(index), "v1") for index in range(251)]
    async with session_scope() as session:
        assert (
            await append_and_advance(session, trigger_id=trigger_id, items=items, cursor={"sync_token": "new"}) == 251
        )
        await session.rollback()
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).provider_state == {}
        assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert not (
            await session.exec(select(TriggerSourceVersion).where(TriggerSourceVersion.trigger_id == trigger_id))
        ).all()
        assert (
            await append_and_advance(session, trigger_id=trigger_id, items=items, cursor={"sync_token": "new"}) == 251
        )
    async with session_scope() as session:
        assert (
            await append_and_advance(session, trigger_id=trigger_id, items=items, cursor={"sync_token": "newer"}) == 0
        )


async def test_competing_source_collectors_cannot_overwrite_the_cursor(make_trigger):
    import asyncio

    trigger_id = await make_trigger(kind="google.calendar", provider="google", provider_state={"sync_token": "start"})

    async def commit(index):
        async with session_scope() as session:
            return await append_and_advance(
                session,
                trigger_id=trigger_id,
                items=[_item(str(index), "v1")],
                cursor={"sync_token": str(index)},
                previous_cursor={"sync_token": "start"},
            )

    outcomes = await asyncio.gather(*(commit(index) for index in range(4)), return_exceptions=True)
    assert sum(result == 1 for result in outcomes) == 1
    assert sum(isinstance(result, RuntimeError) and "cursor changed" in str(result) for result in outcomes) == 3
    async with session_scope() as session:
        assert len((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()) == 1
