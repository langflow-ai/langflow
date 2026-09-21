"""Auditing an API operation from start to outcome, with one decorator per route.

``audited_route`` opens an operation for the request: it resolves the actor while
the user is still loaded and remembers what was attempted. Where the mutation
happens, the route stages the succeeded event in the same transaction. A guard
that refuses leaves its decision in ``authz_audit_log``. Anything that escapes
the route after authorization becomes one failed event, written only after the
rollback.

An operation that is not yet authorized produces no action event: a request
refused before authorization is not an operation that reached Langflow.
"""

from __future__ import annotations

import functools
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

from langflow.services.audit.attribution import resolve_audit_actor
from langflow.services.audit.details import field_names, summarize_flow_membership
from langflow.services.audit.vocabulary import (
    AuditErrorCode,
    AuditEventType,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.audit.writer import (
    AuditEventDraft,
    is_audit_enabled,
    record_audit_event_after_rollback,
    stage_audit_event,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Mapping

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.audit.attribution import AuditActor

P = ParamSpec("P")
R = TypeVar("R")

UNKNOWN_RESOURCE_ID = UUID(int=0)
_NOT_WRITTEN = object()
_current: ContextVar[AuditedOperation | None] = ContextVar("langflow_audited_operation", default=None)


@dataclass
class AuditedOperation:
    """What one request attempted, kept for the event written about it."""

    resource_type: AuditResourceType
    action: str
    operation: AuditOperation
    actor: AuditActor
    resource_id: UUID | None = None
    resource_name: str | None = None
    attempted_fields: list[str] = field(default_factory=list)
    requested_flow_count: int | None = None
    authorized: bool = False
    committed: bool = False

    def identify(
        self,
        *,
        resource_id: UUID | None = None,
        resource_name: str | None = None,
        operation: AuditOperation | None = None,
        action: str | None = None,
    ) -> None:
        if resource_id is not None:
            self.resource_id = resource_id
        if resource_name is not None:
            self.resource_name = resource_name
        if operation is not None:
            self.operation = operation
        if action is not None:
            self.action = action

    def attempted_details(self) -> dict[str, Any]:
        details: dict[str, Any] = {"schema_version": 1}
        if self.attempted_fields:
            details["attempted_fields"] = self.attempted_fields
        if self.resource_type is AuditResourceType.PROJECT and self.requested_flow_count is not None:
            details["requested_flow_count"] = self.requested_flow_count
        return details

    def draft(self, result: AuditResult, error_code: AuditErrorCode) -> AuditEventDraft:
        return AuditEventDraft(
            resource_type=self.resource_type,
            resource_id=self.resource_id or UNKNOWN_RESOURCE_ID,
            resource_name=self.resource_name,
            action=self.action,
            operation=self.operation,
            event_type=AuditEventType.ACTION,
            result=result,
            actor=self.actor,
            details=self.attempted_details(),
            error_code=error_code,
        )


def current_operation() -> AuditedOperation | None:
    return _current.get()


def mark_committed() -> None:
    """The mutation is durable; nothing that fails afterwards may call it failed."""
    operation = _current.get()
    if operation is not None:
        operation.committed = True


async def audited_permission(check: Awaitable[None], **identity: Any) -> None:
    """Run a guard and mark the current operation authorized when it succeeds."""
    operation = _current.get()
    if operation is not None:
        operation.identify(**identity)
    await check
    if operation is not None:
        operation.authorized = True


def classify_failure(exc: BaseException, resource_type: AuditResourceType) -> AuditErrorCode:
    """A safe, bounded code for a failure; the exception text is never stored."""
    detail = str(getattr(exc, "detail", "")).lower()
    is_flow = resource_type is AuditResourceType.FLOW
    if "folder not found" in detail or "project not found" in detail:
        return AuditErrorCode.PROJECT_NOT_FOUND
    if is_flow and "already exist" in detail and "id" in detail:
        return AuditErrorCode.FLOW_ID_CONFLICT
    if "must be unique" in detail:
        return AuditErrorCode.FLOW_NAME_CONFLICT if is_flow else AuditErrorCode.PROJECT_NAME_CONFLICT
    if isinstance(exc, HTTPException) and exc.status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
        return _classify_status(exc.status_code, resource_type)
    cause = database_cause(exc)
    if cause is not None:
        return cause
    if isinstance(exc, HTTPException):
        return _classify_status(exc.status_code, resource_type)
    if type(exc).__name__ == "DeploymentGuardError":
        return AuditErrorCode.CONSTRAINT_VIOLATION
    return AuditErrorCode.INTERNAL_ERROR


def database_cause(exc: BaseException) -> AuditErrorCode | None:
    """Routes wrap database errors in a generic 500; the cause says what happened."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, IntegrityError):
            return AuditErrorCode.CONSTRAINT_VIOLATION
        if isinstance(current, OperationalError):
            return AuditErrorCode.SERVICE_UNAVAILABLE
        current = current.__cause__ or current.__context__
    return None


def _classify_status(status_code: int, resource_type: AuditResourceType) -> AuditErrorCode:
    is_flow = resource_type is AuditResourceType.FLOW
    by_status = {
        HTTPStatus.NOT_FOUND: AuditErrorCode.FLOW_NOT_FOUND if is_flow else AuditErrorCode.PROJECT_NOT_FOUND,
        HTTPStatus.CONFLICT: AuditErrorCode.FLOW_NAME_CONFLICT if is_flow else AuditErrorCode.PROJECT_NAME_CONFLICT,
        HTTPStatus.BAD_REQUEST: AuditErrorCode.INVALID_CONTENT,
        HTTPStatus.UNPROCESSABLE_ENTITY: AuditErrorCode.INVALID_CONTENT,
        HTTPStatus.FORBIDDEN: AuditErrorCode.CONSTRAINT_VIOLATION,
        HTTPStatus.LOCKED: AuditErrorCode.CONSTRAINT_VIOLATION,
        HTTPStatus.SERVICE_UNAVAILABLE: AuditErrorCode.SERVICE_UNAVAILABLE,
    }
    if status_code in by_status:
        return by_status[HTTPStatus(status_code)]
    return AuditErrorCode.INTERNAL_ERROR if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else AuditErrorCode.UNKNOWN


_PROJECT_MEMBERSHIP_FIELDS = frozenset({"flows_list", "components_list", "flows", "components"})
_NEVER_ATTEMPTED = frozenset({"id", "user_id"})


def _fields_set(body: Any) -> set[str]:
    return set(getattr(body, "model_fields_set", ())) - _NEVER_ATTEMPTED


def describe_project_body(param: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Attempted name, field names and requested Flow count of a Project body."""

    def describe(kwargs: dict[str, Any]) -> dict[str, Any]:
        body = kwargs.get(param)
        fields = _fields_set(body)
        requested = [*(getattr(body, "flows_list", None) or []), *(getattr(body, "components_list", None) or [])]
        return {
            "resource_name": getattr(body, "name", None),
            "attempted_fields": {("flows" if name in _PROJECT_MEMBERSHIP_FIELDS else name) for name in fields},
            "requested_flow_count": len(requested) if fields & _PROJECT_MEMBERSHIP_FIELDS else None,
        }

    return describe


def describe_flow_body(param: str, *, loaded_param: str | None = None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Field names of one Flow body, or of every Flow in a list, and the Flow's name.

    The name of a Flow a dependency already loaded is known; otherwise the body's
    name is the attempted one.
    """

    def describe(kwargs: dict[str, Any]) -> dict[str, Any]:
        body = kwargs.get(param)
        flows = getattr(body, "flows", None)
        if isinstance(flows, list):
            return {"attempted_fields": set().union(*(_fields_set(flow) for flow in flows))}
        loaded = kwargs.get(loaded_param) if loaded_param else None
        name = getattr(loaded, "name", None) or getattr(body, "name", None)
        return {"resource_name": name, "attempted_fields": _fields_set(body)}

    return describe


def describe_loaded_resource(param: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """The name of a resource a dependency already loaded and authorized."""

    def describe(kwargs: dict[str, Any]) -> dict[str, Any]:
        return {"resource_name": getattr(kwargs.get(param), "name", None)}

    return describe


async def _release(session: AsyncSession) -> None:
    """Roll the doomed transaction back so its locks do not block the failure row."""
    with suppress(Exception):
        await session.rollback()


def audited_route(
    resource_type: AuditResourceType,
    action: str,
    operation: AuditOperation,
    *,
    resource_id_param: str | None = None,
    session_param: str = "session",
    user_param: str = "current_user",
    describe: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    authorized: bool = False,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Audit every outcome of a route. A nested audited call joins the outer operation.

    ``describe`` receives the route's keyword arguments and returns what was
    attempted (``resource_name``, ``attempted_fields``, ``requested_flow_count``),
    read before the body can change or expire anything.
    """

    def decorate(route: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(route)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if _current.get() is not None or not is_audit_enabled():
                return await route(*args, **kwargs)
            user = kwargs[user_param]
            attempt = describe(kwargs) if describe is not None else {}
            audited = AuditedOperation(
                resource_type=resource_type,
                action=action,
                operation=operation,
                actor=resolve_audit_actor(user.id),
                resource_id=kwargs.get(resource_id_param) if resource_id_param else None,
                resource_name=attempt.get("resource_name"),
                attempted_fields=field_names(attempt.get("attempted_fields", ())),
                requested_flow_count=attempt.get("requested_flow_count"),
                authorized=authorized,
            )
            token = _current.set(audited)
            try:
                return await route(*args, **kwargs)
            except Exception as exc:
                if audited.authorized and not audited.committed:
                    await _release(kwargs[session_param])
                    await record_audit_event_after_rollback(
                        audited.draft(AuditResult.FAILED, classify_failure(exc, resource_type))
                    )
                raise
            finally:
                _current.reset(token)

        return wrapper

    return decorate


async def stage_flow_succeeded(
    session: AsyncSession,
    *,
    action: str,
    operation: AuditOperation,
    flow_id: UUID,
    flow_name: str | None,
    written_fields: Iterable[str] = (),
    project_before: UUID | None = None,
    project_after: UUID | None = None,
) -> None:
    """Stage a Flow event in the mutation's transaction, when a request is audited."""
    current = _current.get()
    if current is None:
        return
    details: dict[str, Any] = {"schema_version": 1}
    fields = field_names(name for name in written_fields if name not in {"id", "user_id"})
    if fields:
        details["written_fields"] = fields
    if project_before != project_after:
        details["project"] = {"before_id": project_before, "after_id": project_after}
    await stage_audit_event(
        session,
        AuditEventDraft(
            resource_type=AuditResourceType.FLOW,
            resource_id=flow_id,
            resource_name=flow_name,
            action=action,
            operation=operation,
            event_type=AuditEventType.ACTION,
            result=AuditResult.SUCCEEDED,
            actor=current.actor,
            details=details,
        ),
    )


async def stage_project_succeeded(
    session: AsyncSession,
    *,
    action: str,
    operation: AuditOperation,
    project_id: UUID,
    project_name: str | None,
    description: Any = _NOT_WRITTEN,
    flows_before: Mapping[UUID, str] | None = None,
    flows_after: Mapping[UUID, str] | None = None,
) -> None:
    """Stage a Project event in the mutation's transaction, when a request is audited.

    ``description`` is included only when the operation wrote it, as the value
    written. ``flows_before``/``flows_after`` are given only when membership was written.
    """
    current = _current.get()
    if current is None:
        return
    details: dict[str, Any] = {"schema_version": 1}
    if description is not _NOT_WRITTEN:
        details["description"] = description
    if flows_before is not None or flows_after is not None:
        details["flows"] = summarize_flow_membership(flows_before or {}, flows_after or {})
    await stage_audit_event(
        session,
        AuditEventDraft(
            resource_type=AuditResourceType.PROJECT,
            resource_id=project_id,
            resource_name=project_name,
            action=action,
            operation=operation,
            event_type=AuditEventType.ACTION,
            result=AuditResult.SUCCEEDED,
            actor=current.actor,
            details=details,
        ),
    )
