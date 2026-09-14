"""Creating audit events: the only write path into ``audit_events``.

Two entry points, because the contract gives the two outcomes opposite
durability rules. A committed mutation stages its event in the mutation's own
transaction, so the event cannot exist without the change and the change cannot
commit without the event. A failure or denial is written only after the
mutation's transaction is gone, in a transaction of its own.

There is no update and no delete here: rows are append-only, and the only
deletion is the retention sweep.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.services.session import NoopSession

from langflow.services.audit.attribution import AuditActor, current_request_id
from langflow.services.audit.details import AuditContractError, bounded_name, validate_details
from langflow.services.audit.vocabulary import (
    ACTIONS_BY_RESOURCE_TYPE,
    RESULTS_BY_EVENT_TYPE,
    RESULTS_REQUIRING_ERROR_CODE,
    AuditErrorCode,
    AuditEventType,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

MAX_CONCURRENT_INDEPENDENT_WRITES = 4
INDEPENDENT_WRITE_TIMEOUT_SECONDS = 5.0

_write_slots: asyncio.Semaphore | None = None
_write_slots_loop: asyncio.AbstractEventLoop | None = None


@dataclass(frozen=True)
class AuditEventDraft:
    """Everything a producer knows about one operation, before validation."""

    resource_type: AuditResourceType
    resource_id: UUID
    resource_name: str | None
    action: str
    operation: AuditOperation
    event_type: AuditEventType
    result: AuditResult
    actor: AuditActor
    details: Mapping[str, Any] = field(default_factory=lambda: {"schema_version": 1})
    error_code: AuditErrorCode | None = None


def is_audit_enabled() -> bool:
    return bool(get_settings_service().settings.audit_enabled)


def build_audit_event(draft: AuditEventDraft) -> AuditEvent:
    """Validate a draft against the contract and turn it into a row.

    Raises ``AuditContractError``: a producer that breaks the contract is a bug
    and must fail where its tests can see it, not become a missing row.
    """
    if draft.result not in RESULTS_BY_EVENT_TYPE[draft.event_type]:
        msg = f"{draft.result.value!r} is not a result of {draft.event_type.value!r} events"
        raise AuditContractError(msg)
    if draft.action not in ACTIONS_BY_RESOURCE_TYPE[draft.resource_type]:
        msg = f"{draft.action!r} is not an action on {draft.resource_type.value!r}"
        raise AuditContractError(msg)
    if (draft.error_code is not None) != (draft.result in RESULTS_REQUIRING_ERROR_CODE):
        msg = f"error_code is required for deny and failed, and forbidden for {draft.result.value!r}"
        raise AuditContractError(msg)
    return AuditEvent(
        resource_type=draft.resource_type.value,
        resource_id=draft.resource_id,
        resource_name=bounded_name(draft.resource_name),
        user_id=draft.actor.user_id,
        actor_type=draft.actor.actor_type.value,
        actor_id=draft.actor.actor_id,
        acting_issuer=draft.actor.acting_issuer,
        acting_subject=draft.actor.acting_subject,
        action=draft.action,
        operation=draft.operation.value,
        event_type=draft.event_type.value,
        result=draft.result.value,
        error_code=draft.error_code.value if draft.error_code is not None else None,
        request_id=current_request_id(),
        details=validate_details(draft.resource_type, draft.result, draft.details),
    )


def stage_audit_event(session: AsyncSession, draft: AuditEventDraft) -> AuditEvent | None:
    """Add a committed operation's event to the mutation's own transaction.

    Only staged: the insert rides the caller's commit, so if the event cannot be
    written the mutation rolls back with it. Returns ``None`` when auditing is off
    or there is no database, as under ``lfx serve``.
    """
    if not is_audit_enabled() or isinstance(session, NoopSession):
        return None
    event = build_audit_event(draft)
    session.add(event)
    return event


def _slots() -> asyncio.Semaphore:
    """The write slots of the running loop; a semaphore cannot cross loops."""
    global _write_slots, _write_slots_loop  # noqa: PLW0603
    loop = asyncio.get_running_loop()
    if _write_slots is None or _write_slots_loop is not loop:
        _write_slots = asyncio.Semaphore(MAX_CONCURRENT_INDEPENDENT_WRITES)
        _write_slots_loop = loop
    return _write_slots


async def record_audit_event_after_rollback(draft: AuditEventDraft) -> bool:
    """Write a failure or denial in its own transaction; the caller's is gone.

    Bounded to a few concurrent connections so a burst of refusals cannot drain
    the pool its own requests need. The caller is already failing or denied, so
    a storage outage is surfaced as an error log rather than a second exception.
    """
    if not is_audit_enabled():
        return False
    event = build_audit_event(draft)

    async def _write() -> bool:
        async with _slots(), session_scope() as session:
            if isinstance(session, NoopSession):
                return False
            session.add(event)
        return True

    try:
        # wait_for rather than asyncio.timeout, which does not exist on Python 3.10.
        return await asyncio.wait_for(_write(), timeout=INDEPENDENT_WRITE_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001
        await logger.aerror(
            "op=record_audit_event_after_rollback outcome=not_persisted request_id=%s "
            "resource_type=%s operation=%s result=%s error=%s",
            event.request_id,
            event.resource_type,
            event.operation,
            event.result,
            type(exc).__name__,
        )
        return False
