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
    return await session.get(Trigger, trigger_id, populate_existing=True, with_for_update=lock)


def _pausable(row: Trigger) -> bool:
    return row.state in ARMED_TRIGGER_STATES


def _resumable(row: Trigger) -> bool:
    return row.state == TriggerState.PAUSED.value and row.admin_paused_at is not None


class _Audit:
    """One operator audit row, written in the change's own transaction when audit is durable."""

    def __init__(self, action: str, *, actor_id: UUID, row: Trigger) -> None:
        self.entry: dict[str, Any] = {
            "user_id": actor_id,
            "action": action,
            "obj": f"trigger:{row.id}",
            "result": "allow",
            "details": {"provider": row.provider},
        }
        self.staged = False

    def stage(self, session: AsyncSession) -> None:
        from langflow.services.authorization.audit import stage_audit_decision

        self.staged = stage_audit_decision(session=session, **self.entry)

    async def submit_if_not_staged(self) -> None:
        """Best-effort mode: submit only after the change it describes has committed."""
        if not self.staged:
            from langflow.services.authorization.audit import audit_decision

            await audit_decision(**self.entry)


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
        row = await _current(session, trigger_id, lock=not request.dry_run)
        if row is None or not eligible(row):
            unchanged.append(trigger_id)
            continue
        owner_id = row.user_id
        if not request.dry_run:
            audit = _Audit(audit_action, actor_id=actor_id, row=row)
            try:
                await apply(row, audit)
            except ValueError as exc:
                # Owner-facing by contract: every refusal the enable and disable
                # paths raise is a message written for the trigger's owner.
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
        await audit.submit_if_not_staged()

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
        await audit.submit_if_not_staged()
        # Committed above, so the operator's hold is released and audited even
        # when the provider subscription below fails; the initializer then
        # records that failure on the trigger, as it does for the owner's resume.
        await service.activate_push_source(session, row=enabled)

    async def release(trigger_id: UUID, detail: str) -> None:
        """The operator released it, so it must stop reading as paused by an administrator."""
        row = await _current(session, trigger_id, lock=True)
        if row is None or not _resumable(row):
            return
        row.admin_paused_at = None
        row.last_error = f"An administrator resumed this trigger, but it could not start: {detail}"
        session.add(row)
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
