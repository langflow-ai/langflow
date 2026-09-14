"""Recording how an attempt ended, without asking every route to remember.

A route has many ways to fail and one way to succeed. Instrumenting each
``except`` by hand means the next branch somebody adds is silently unaudited, so
the outcome is decided here, once, around the whole attempt.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from langflow.services.audit.events import REASON_PERMISSION_DENIED
from langflow.services.audit.recorder import (
    record_audit_event,
    record_audit_event_independently,
)
from langflow.services.database.models.audit_event.model import AuditFamily, AuditResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass
class AuditScope:
    """What the body learns while it runs, for the row written after it."""

    resource_id: UUID | None = None
    payload: dict[str, Any] | None = None

    def describe(self, resource_id: UUID | None = None, **payload: Any) -> None:
        """Name the resource, and anything worth recording about the attempt."""
        if resource_id is not None:
            self.resource_id = resource_id
        if payload:
            self.payload = {**(self.payload or {}), **payload}


@asynccontextmanager
async def audited_action(
    session: AsyncSession,
    *,
    event: str,
    user_id: UUID | None,
    resource_id: UUID | None = None,
) -> AsyncIterator[AuditScope]:
    """Record one attempt and how it ended, whichever way the body leaves.

    Three outcomes, because conflating them makes the trail lie:

    - the body returns — one ``action`` row, ``succeeded``;
    - it raises ``403`` — an ``authz`` row, ``deny``. A refusal is a decision
      about permission, never a mutation that failed;
    - it raises anything else — an ``action`` row, ``failed``, written in its own
      transaction because the caller's is about to roll back and would take the
      row with it.

    ``404`` is recorded as nothing at all. Denials are mapped to ``404`` to keep
    a UUID private, so the status cannot tell a refusal from a resource that was
    never there — and recording every miss would turn the trail into a scan log.
    """
    scope = AuditScope(resource_id=resource_id)
    attribution = {"user_id": user_id}
    try:
        yield scope
    except HTTPException as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            raise
        if exc.status_code == HTTPStatus.FORBIDDEN:
            await record_audit_event_independently(
                event=event,
                family=AuditFamily.AUTHZ,
                result=AuditResult.DENY,
                resource_id=scope.resource_id,
                payload={**(scope.payload or {}), "reason": REASON_PERMISSION_DENIED},
                **attribution,
            )
            raise
        await _record_failure(event, scope, exc, attribution)
        raise
    except Exception as exc:
        await _record_failure(event, scope, exc, attribution)
        raise

    await record_audit_event(
        session,
        event=event,
        family=AuditFamily.ACTION,
        result=AuditResult.SUCCEEDED,
        resource_id=scope.resource_id,
        payload=scope.payload,
        **attribution,
    )


async def _record_failure(
    event: str,
    scope: AuditScope,
    exc: BaseException,
    attribution: dict[str, Any],
) -> None:
    await record_audit_event_independently(
        event=event,
        family=AuditFamily.ACTION,
        result=AuditResult.FAILED,
        resource_id=scope.resource_id,
        payload={**(scope.payload or {}), "error_class": type(exc).__name__},
        **attribution,
    )
