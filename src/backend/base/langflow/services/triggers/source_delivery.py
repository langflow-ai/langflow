"""Atomic delivery of provider source changes.

Push notifications are hints. A source adapter expands a hint (or a poll page)
into canonical items, and commits their ledger rows with its cursor in one
transaction. A failed expansion therefore leaves the cursor behind for replay.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlmodel import col, select

from langflow.services.database.models.trigger.model import Trigger, TriggerSourceVersion
from langflow.services.triggers import ledger
from langflow.services.triggers.constants import PUSH_MECHANISMS

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


SOURCE_HINT_FIELD = "_source_hint"
SOURCE_DEDUPE_PREFIX = "source"
_VERSION_LOOKUP_BATCH = 500


def canonical_key(*, provider: str, resource: str, item_id: str, version: str) -> str:
    """One identity shared by a provider's push and poll mechanisms.

    The subscription/channel id and delivery timestamp are deliberately absent.
    Hashing the tuple bounds long Graph resource paths and avoids delimiter
    ambiguity between provider-owned identifiers.
    """
    identity = json.dumps([provider, resource, item_id, version], ensure_ascii=False, separators=(",", ":"))
    return f"{SOURCE_DEDUPE_PREFIX}:{provider}:{hashlib.sha256(identity.encode()).hexdigest()}"


def item_key(*, provider: str, resource: str, item_id: str) -> str:
    identity = json.dumps([provider, resource, item_id], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(identity.encode()).hexdigest()


async def append_and_advance(
    session: AsyncSession,
    *,
    trigger_id: UUID,
    items: list[dict[str, Any]],
    cursor: dict[str, Any] | None,
    previous_cursor: dict[str, Any] | None = None,
    baseline: bool = False,
    expected_connection_id: UUID | None = None,
    expected_mechanism_id: str | None = None,
    snapshot_resource: str | None = None,
) -> int:
    """Append normalized items and advance a cursor in the caller's transaction.

    A caller must commit only after this returns. The cursor precondition stops
    an older poll pass from overwriting a newer one after a lease handover. The
    database uniqueness constraint collapses replays, including a push and a
    poll of the same provider item.
    """
    row = await session.get(Trigger, trigger_id, populate_existing=True, with_for_update=True)
    if row is None:
        return 0
    if expected_connection_id is not None and row.connection_id != expected_connection_id:
        msg = "The source connection changed while this page was fetched."
        raise RuntimeError(msg)
    if expected_mechanism_id is not None and (row.config or {}).get("mechanism_id") != expected_mechanism_id:
        msg = "The source mechanism changed while this page was fetched."
        raise RuntimeError(msg)
    state = dict(row.provider_state or {})
    if previous_cursor is not None and state != previous_cursor:
        msg = "The source cursor changed while this page was fetched."
        raise RuntimeError(msg)
    keys = {
        item_key(provider=str(item["provider"]), resource=str(item["resource"]), item_id=str(item["id"]))
        for item in items
    }
    prior_items: list[TriggerSourceVersion] = []
    if snapshot_resource is not None and not baseline:
        # A full snapshot needs every prior item in this resource to detect
        # removals. Ordinary polls need only the items returned by the provider.
        prior_items = list(
            (
                await session.exec(
                    select(TriggerSourceVersion).where(
                        TriggerSourceVersion.trigger_id == trigger_id,
                        TriggerSourceVersion.resource == snapshot_resource,
                    )
                )
            ).all()
        )
    keys.difference_update(prior.item_key for prior in prior_items)
    lookup_keys = list(keys)
    for start in range(0, len(lookup_keys), _VERSION_LOOKUP_BATCH):
        prior_items.extend(
            (
                await session.exec(
                    select(TriggerSourceVersion).where(
                        TriggerSourceVersion.trigger_id == trigger_id,
                        col(TriggerSourceVersion.item_key).in_(lookup_keys[start : start + _VERSION_LOOKUP_BATCH]),
                    )
                )
            ).all()
        )
    prior_by_key = {prior.item_key: prior for prior in prior_items}
    if snapshot_resource is not None and not baseline:
        present = {
            item_key(provider=str(item["provider"]), resource=str(item["resource"]), item_id=str(item["id"]))
            for item in items
        }
        items = [*items]
        items.extend(
            {
                "provider": prior.provider,
                "resource": prior.resource,
                "id": prior.provider_item_id,
                "version": "deleted",
                "deleted": True,
                "data": {},
            }
            for prior in prior_items
            if prior.resource == snapshot_resource and prior.item_key not in present and prior.version != "deleted"
        )
    created = 0
    for item in items:
        identity = item_key(provider=str(item["provider"]), resource=str(item["resource"]), item_id=str(item["id"]))
        prior = prior_by_key.get(identity)
        version = str(item["version"])
        if prior is not None and prior.version == version:
            continue
        removed_version = prior.version if version == "deleted" and prior is not None else None
        if prior is None:
            prior = TriggerSourceVersion(
                trigger_id=trigger_id,
                item_key=identity,
                provider=str(item["provider"]),
                resource=str(item["resource"]),
                provider_item_id=str(item["id"]),
                version=version,
            )
        else:
            prior.version = version
        prior_by_key[identity] = prior
        session.add(prior)
        if baseline:
            continue
        key = canonical_key(
            provider=str(item["provider"]),
            resource=str(item["resource"]),
            item_id=str(item["id"]),
            version=f"deleted:{removed_version}" if removed_version is not None else version,
        )
        _event, inserted = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=key, payload=item)
        created += int(inserted)
    if cursor is not None:
        row.provider_state = {**state, **cursor}
        row.updated_at = datetime.now(timezone.utc)
        if expected_mechanism_id in PUSH_MECHANISMS:
            # Provider notifications may be dropped. The dispatcher scans the
            # source independently even when no notification arrives.
            row.next_fire_at = row.updated_at + timedelta(minutes=5)
        session.add(row)
        await session.flush()
    return created
