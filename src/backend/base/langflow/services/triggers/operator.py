"""Operator bulk pause and resume, for incident response (TRG-7, surface B3).

A superuser selects triggers by provider, by id, or both, across every user, and
pauses or resumes them in one request. Two rules keep this from overriding the
owners it acts for:

* **Pause takes out only what is armed** - ``active``, ``error`` and
  ``needs_reconnect``, the states an owner turned on. A ``pending`` trigger was
  created by a canvas save and never consented to, and a paused one is already
  off; both are left alone so that a later resume cannot arm them.
* **Resume re-arms only what an operator paused.** Each pause is marked
  (``trigger.admin_paused_at``); resume enables exactly the marked rows that are
  still paused. A trigger its owner paused - before the incident or during it -
  stays paused, because the incident ending is not the owner's consent.

Each trigger is changed through the same service methods the owner's own pause
and resume routes use, and committed on its own together with its audit row, so
a failure part-way through leaves every earlier change durable and audited and
is reported rather than aborting the batch. Each row is re-read under a row lock
just before it is changed, so an owner acting on it while the batch runs is
seen, not overwritten.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.authorization.audit import AUDIT_EVENT_MUTATION
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import (
    ARMED_TRIGGER_STATES,
    TriggerAction,
    TriggerBulkFailure,
    TriggerBulkRequest,
    TriggerBulkResult,
    TriggerState,
)
from langflow.services.triggers.constants import AUDIT_ADMIN_PAUSE, AUDIT_ADMIN_RESUME
from langflow.services.triggers.locking import lock_trigger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.triggers.service import TriggerService

_UNEXPECTED_FAILURE = "The trigger could not be changed. Check the server log for this trigger id."


async def _selected_ids(session: AsyncSession, *, request: TriggerBulkRequest) -> list[UUID]:
    """Every trigger the request's filters select, oldest first, across all owners."""
    statement = select(Trigger.id).order_by(col(Trigger.created_at), col(Trigger.id))
    if request.provider is not None:
        statement = statement.where(Trigger.provider == request.provider)
    if request.trigger_ids:
        statement = statement.where(col(Trigger.id).in_(request.trigger_ids))
    return list((await session.exec(statement)).all())


async def _current(session: AsyncSession, trigger_id: UUID, *, lock: bool) -> Trigger | None:
    """The row as it is now, not as the selection saw it."""
    if lock:
        return await lock_trigger(session, trigger_id)
    return await session.get(Trigger, trigger_id, populate_existing=True)


def _pausable(row: Trigger) -> bool:
    return row.state in ARMED_TRIGGER_STATES


def _resumable(row: Trigger) -> bool:
    return row.state == TriggerState.PAUSED.value and row.admin_paused_at is not None


class _Audit:
    """One required operator audit row, written in the change's own transaction."""

    def __init__(self, action: str, *, actor_id: UUID, row: Trigger) -> None:
        self.entry: dict[str, Any] = {
            "user_id": actor_id,
            "action": action,
            "obj": f"trigger:{row.id}",
            "result": "allow",
            "details": {"event": AUDIT_EVENT_MUTATION, "provider": row.provider},
        }

    def stage(self, session: AsyncSession) -> None:
        from langflow.services.authorization.audit import AuditPersistenceError, stage_audit_decision

        try:
            stage_audit_decision(session=session, required=True, **self.entry)
        except Exception as exc:
            # Provider/storage errors, including ValueError, are not an
            # owner-facing enable refusal and must not release the hold.
            raise AuditPersistenceError from exc


async def _run(
    session: AsyncSession,
    *,
    action: TriggerAction,
    request: TriggerBulkRequest,
    eligible: Callable[[Trigger], bool],
    apply: Callable[[Trigger, _Audit], Awaitable[None]],
    audit_action: str,
    actor_id: UUID,
    on_refusal: Callable[[UUID, str], Awaitable[None]] | None = None,
) -> TriggerBulkResult:
    changed: list[UUID] = []
    unchanged: list[UUID] = []
    failed: list[TriggerBulkFailure] = []
    owners: set[UUID] = set()
    trigger_ids = await _selected_ids(session, request=request)
    for trigger_id in trigger_ids:
        try:
            row = await _current(session, trigger_id, lock=not request.dry_run)
            if row is None or not eligible(row):
                if not request.dry_run:
                    await session.rollback()  # Release even an unchanged row's lock.
                unchanged.append(trigger_id)
                continue
            owner_id = row.user_id
            if not request.dry_run:
                audit = _Audit(audit_action, actor_id=actor_id, row=row)
                try:
                    await apply(row, audit)
                except ValueError as exc:
                    # Enable/disable refusals are owner-facing. Releasing a
                    # refused resume must also succeed with its required audit.
                    await session.rollback()
                    if on_refusal is not None:
                        await on_refusal(trigger_id, str(exc))
                    failed.append(TriggerBulkFailure(trigger_id=trigger_id, detail=str(exc)))
                    continue
        except Exception:  # noqa: BLE001 - one trigger must not stop an incident response
            await session.rollback()
            await logger.aexception("Operator %s failed for trigger %s", action.value, trigger_id)
            failed.append(TriggerBulkFailure(trigger_id=trigger_id, detail=_UNEXPECTED_FAILURE))
            continue
        changed.append(trigger_id)
        owners.add(owner_id)
    return TriggerBulkResult(
        action=action,
        dry_run=request.dry_run,
        matched=len(trigger_ids),
        changed=changed,
        unchanged=unchanged,
        failed=failed,
        owners=len(owners),
    )


async def bulk_pause(
    session: AsyncSession, service: TriggerService, *, request: TriggerBulkRequest, actor_id: UUID
) -> TriggerBulkResult:
    async def apply(row: Trigger, audit: _Audit) -> None:
        await service.admin_pause(session, row=row)
        audit.stage(session)
        await session.commit()

    return await _run(
        session,
        action=TriggerAction.PAUSE,
        request=request,
        eligible=_pausable,
        apply=apply,
        audit_action=AUDIT_ADMIN_PAUSE,
        actor_id=actor_id,
    )


async def bulk_resume(
    session: AsyncSession, service: TriggerService, *, request: TriggerBulkRequest, actor_id: UUID
) -> TriggerBulkResult:
    async def apply(row: Trigger, audit: _Audit) -> None:
        enabled = await service.enable(session, row=row)
        audit.stage(session)
        await session.commit()
        # Committed above, so the operator's hold is released and audited even
        # when the provider subscription below fails; the initializer then
        # records that failure on the trigger, as it does for the owner's resume.
        await service.activate_push_source(session, row=enabled)

    async def release(trigger_id: UUID, detail: str) -> None:
        """The operator released it, so it must stop reading as paused by an administrator."""
        row = await _current(session, trigger_id, lock=True)
        if row is None or not _resumable(row):
            await session.rollback()
            return
        row.admin_paused_at = None
        row.last_error = f"An administrator resumed this trigger, but it could not start: {detail}"
        session.add(row)
        audit = _Audit(AUDIT_ADMIN_RESUME, actor_id=actor_id, row=row)
        audit.entry["details"].update(outcome="enable_refused", reason=detail)
        audit.stage(session)
        await session.commit()

    return await _run(
        session,
        action=TriggerAction.RESUME,
        request=request,
        eligible=_resumable,
        apply=apply,
        audit_action=AUDIT_ADMIN_RESUME,
        actor_id=actor_id,
        on_refusal=release,
    )
