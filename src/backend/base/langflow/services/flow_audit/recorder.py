"""Writing down an edit, without ever costing the edit itself.

Two rules shape everything here. A save must never fail because its audit row
failed — the record is worth less than the work it describes. And a burst of
autosaves is one thing a person did, not sixty: recording per write turns typing
a word into a page of noise, so consecutive edits by the same person fold into
the entry already open.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.log import logger
from sqlmodel import col, delete, desc, select

from langflow.services.database.models.flow_audit.model import FlowAuditEntry
from langflow.services.deps import get_settings_service
from langflow.services.flow_audit.diff import diff_graphs, field_value_in

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

SOURCE_EDITOR = "editor"
SOURCE_API = "api"
SOURCE_IMPORT = "import"
SOURCE_RESTORE = "restore"
SOURCE_OVERWRITE = "overwrite"
SOURCE_ASSISTANT = "assistant"


def is_enabled() -> bool:
    return bool(get_settings_service().settings.flow_audit_enabled)


def _session_window() -> timedelta:
    return timedelta(seconds=get_settings_service().settings.flow_audit_session_window_seconds)


def _was_undone(change: dict[str, Any]) -> bool:
    """A field driven back to where it started is not a change the session made."""
    return change.get("kind") == "field" and "before" in change and change.get("before") == change.get("after")


def _change_key(group: dict[str, Any], change: dict[str, Any]) -> tuple[str, str, str]:
    return group["target"], change.get("kind", ""), change.get("field", "")


def merge_changes(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold a new diff into the session's running summary.

    The session reports where a value started and where it ended, so a field
    edited three times keeps its original ``before``. A value driven back to what
    it started as leaves nothing behind: the person undid it, and an entry saying
    they changed it would be false.
    """
    merged: dict[str, dict[str, Any]] = {group["target"]: dict(group) for group in existing}
    for group in merged.values():
        group["changes"] = [dict(change) for change in group["changes"]]

    for group in incoming:
        target = group["target"]
        current = merged.get(target)
        if current is None:
            merged[target] = {**group, "changes": [dict(change) for change in group["changes"]]}
            continue

        if group["badge"] != "modified":
            current["badge"] = group["badge"]

        by_key = {_change_key(current, change): change for change in current["changes"]}
        for change in group["changes"]:
            key = _change_key(group, change)
            previous = by_key.get(key)
            if previous is None:
                by_key[key] = dict(change)
                continue
            if "after" in change:
                previous["after"] = change["after"]
                if change.get("truncated"):
                    previous["truncated"] = True
        current["changes"] = [change for change in by_key.values() if not _was_undone(change)]

    return [group for group in merged.values() if group["changes"]]


def reconcile_with_graph(groups: list[dict[str, Any]], graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Point the session's summary at the graph the flow actually ended up with.

    A session's entry claims "this is what changed since you started". Two writers
    landing at once break that on their own: each records the field it changed
    against the state it read, the later write silently reverts the earlier one,
    and the entry ends up listing changes the flow no longer has. Re-reading each
    recorded field from the graph just written keeps the claim true.
    """
    reconciled: list[dict[str, Any]] = []
    for group in groups:
        if not group["target"].startswith("node:"):
            reconciled.append(group)
            continue
        node_id = group["target"].removeprefix("node:")
        changes: list[dict[str, Any]] = []
        for change in group["changes"]:
            if change.get("kind") != "field" or change.get("secret") or "after" not in change:
                changes.append(change)
                continue
            current = field_value_in(graph, node_id, change["field"])
            if current is None:
                changes.append(change)
                continue
            updated = dict(change)
            updated["after"] = current[: len(change["after"])] if change.get("truncated") else current
            if not _was_undone(updated):
                changes.append(updated)
        if changes:
            reconciled.append({**group, "changes": changes})
    return reconciled


async def _open_entry(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID | None,
    source: str,
    now: datetime,
) -> FlowAuditEntry | None:
    """The entry this write continues, if there is one, held for update.

    Only editing folds. A restore, an import or an overwrite is a discrete act
    somebody chose, and merging one into a typing session both mislabels the
    session and can cancel the act out of existence — restoring a version that
    undoes the last edit would leave no trace that anyone restored anything.

    Merging is read-modify-write, so the row is locked: two writers on one flow —
    two tabs, or two replicas behind a load balancer — would otherwise both read
    the same summary and the later write would drop the earlier merge. SQLite
    ignores ``FOR UPDATE`` entirely; there the guarantee comes from
    ``reconcile_with_graph``, which re-reads every recorded field from the graph
    that was actually written, so a dropped merge still cannot leave the entry
    claiming a change the flow does not have. Do not remove either half.
    """
    if source != SOURCE_EDITOR:
        return None
    cutoff = now - _session_window()
    statement = (
        select(FlowAuditEntry)
        .where(
            FlowAuditEntry.flow_id == flow_id,
            FlowAuditEntry.user_id == user_id,
            FlowAuditEntry.source == SOURCE_EDITOR,
            col(FlowAuditEntry.updated_at) >= cutoff,
        )
        .order_by(desc(col(FlowAuditEntry.updated_at)))
        .limit(1)
        .with_for_update()
    )
    return (await session.exec(statement)).first()


async def _prune(session: AsyncSession, flow_id: UUID) -> None:
    """Drop the oldest entries once a flow has more than the configured ceiling.

    Only called when a session opens, so a burst of editing never pays for it.
    Concurrent opens can both insert before either prunes and briefly exceed the
    limit; the excess self-corrects on the next session, which is the same trade
    the version history makes.
    """
    max_entries = get_settings_service().settings.max_flow_audit_entries_per_flow
    if max_entries <= 0:
        return

    # One short of the ceiling: this runs just before the entry that opens the new
    # session is added, and keeping a full ceiling here would leave the flow one over.
    survivors = (
        select(FlowAuditEntry.id)
        .where(FlowAuditEntry.flow_id == flow_id)
        .order_by(desc(col(FlowAuditEntry.updated_at)))
        .limit(max(max_entries - 1, 0))
        .scalar_subquery()
    )
    await session.exec(
        delete(FlowAuditEntry).where(
            FlowAuditEntry.flow_id == flow_id,
            col(FlowAuditEntry.id).not_in(survivors),
        )
    )


async def record_flow_edit(
    session: AsyncSession,
    *,
    flow_id: UUID,
    user_id: UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    source: str,
    from_version_token: UUID | None = None,
    to_version_token: UUID | None = None,
) -> None:
    """Record what this write changed, or do nothing at all.

    Never raises: the caller is in the middle of a save that has already been
    accepted, and losing the description of an edit must not lose the edit.
    """
    if not is_enabled():
        return

    try:
        groups = diff_graphs(before, after)
        if not groups:
            return

        now = datetime.now(timezone.utc)
        entry = await _open_entry(session, flow_id, user_id, source, now)
        if entry is None:
            await _prune(session, flow_id)
            session.add(
                FlowAuditEntry(
                    flow_id=flow_id,
                    user_id=user_id,
                    source=source,
                    from_version_token=from_version_token,
                    to_version_token=to_version_token,
                    changes=groups,
                    started_at=now,
                    updated_at=now,
                )
            )
            return

        merged = reconcile_with_graph(merge_changes(entry.changes or [], groups), after)
        if not merged:
            # Everything in the session was undone. The row would claim a change
            # that no longer exists in the flow.
            await session.delete(entry)
            return
        entry.changes = merged
        entry.updated_at = now
        entry.to_version_token = to_version_token or entry.to_version_token
        session.add(entry)
    except Exception as exc:  # noqa: BLE001
        # Named, because a bare warning here hid a real defect: the first real graph
        # this met had template metadata the diff assumed was a field, and every
        # edit went unrecorded while the log said only that something went wrong.
        await logger.awarning(
            "op=record_flow_edit flow_id=%s outcome=dropped error=%s",
            flow_id,
            type(exc).__name__,
        )
