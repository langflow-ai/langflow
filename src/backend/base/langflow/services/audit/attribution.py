"""Who an event is attributed to, derived from the credential and never the caller.

A caller cannot supply any of these values. ``user_id`` is the Langflow account the
request executes under, ``actor_type``/``actor_id`` the credential that
authenticated it. The on-behalf-of pair is accepted only from a trusted Control
Plane identity, which nothing in this module establishes, so it stays empty here.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langflow.services.audit.details import AuditContractError
from langflow.services.audit.vocabulary import AuditActorType
from langflow.services.auth.context import AUTH_METHOD_API_KEY, get_current_auth_context
from langflow.services.database.models.audit_event.model import (
    ACTING_ISSUER_MAX_LENGTH,
    ACTING_SUBJECT_MAX_LENGTH,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_request_id: ContextVar[UUID | None] = ContextVar("langflow_audit_request_id", default=None)


@dataclass(frozen=True)
class AuditActor:
    """Attribution resolved while the request's user is still loaded.

    Resolved up front on purpose: a failure event is written after the mutation
    rolled back, and the rollback expires the ORM user it would otherwise read.
    """

    user_id: UUID | None
    actor_type: AuditActorType
    actor_id: UUID | None
    acting_issuer: str | None = None
    acting_subject: str | None = None

    def __post_init__(self) -> None:
        if (self.acting_issuer is None) != (self.acting_subject is None):
            msg = "acting_issuer and acting_subject must be set together"
            raise AuditContractError(msg)
        if self.acting_issuer is not None and len(self.acting_issuer) > ACTING_ISSUER_MAX_LENGTH:
            msg = "acting_issuer is longer than the contract allows"
            raise AuditContractError(msg)
        if self.acting_subject is not None and len(self.acting_subject) > ACTING_SUBJECT_MAX_LENGTH:
            msg = "acting_subject is longer than the contract allows"
            raise AuditContractError(msg)


SYSTEM_ACTOR = AuditActor(user_id=None, actor_type=AuditActorType.SYSTEM, actor_id=None)


def resolve_audit_actor(user_id: UUID | None) -> AuditActor:
    """Attribute to the authenticated credential of the current request."""
    if user_id is None:
        return AuditActor(user_id=None, actor_type=AuditActorType.UNKNOWN, actor_id=None)
    context = get_current_auth_context()
    if context is not None and context.method == AUTH_METHOD_API_KEY:
        # An environment-sourced key authenticates without a key record, so the
        # credential is still an API key and simply has no id to name.
        return AuditActor(user_id=user_id, actor_type=AuditActorType.API_KEY, actor_id=context.api_key_id)
    return AuditActor(user_id=user_id, actor_type=AuditActorType.USER, actor_id=user_id)


def audit_request_id() -> UUID | None:
    """This request's correlation id, or None outside an HTTP request."""
    return _request_id.get()


def current_request_id() -> UUID:
    """The correlation id every event of this request shares.

    Outside an HTTP request each event gets its own: remembering one in the
    context would let a long-lived worker stamp the same id on everything it does.
    """
    return _request_id.get() or uuid4()


class AuditRequestContextMiddleware:
    """Give every HTTP request its own server-generated correlation id.

    Set before the application runs, so an authorization event and the action
    event of the same request always share it, whichever task records them.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _request_id.set(uuid4())
        try:
            await self.app(scope, receive, send)
        finally:
            _request_id.reset(token)
