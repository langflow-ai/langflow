"""Who an event is attributed to, derived from the credential and never the caller.

A caller cannot supply any of these values. ``user_id`` is the Langflow account the
request executes under, ``actor_type``/``actor_id`` the credential that
authenticated it. Represented identity comes from request context validated
after authentication against the exact credential allowlist.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langflow.services.audit.details import AuditContractError
from langflow.services.audit.represented import current_represented_identity
from langflow.services.audit.vocabulary import AuditActorType
from langflow.services.database.models.audit_event.model import (
    REPRESENTED_ISSUER_MAX_LENGTH,
    REPRESENTED_SUBJECT_MAX_LENGTH,
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
    represented_issuer: str | None = None
    represented_subject: str | None = None

    def __post_init__(self) -> None:
        represented = (self.represented_issuer, self.represented_subject)
        legacy = (self.acting_issuer, self.acting_subject)
        if represented != (None, None) and legacy not in ((None, None), represented):
            msg = "Represented identity conflicts with deprecated acting identity"
            raise AuditContractError(msg)
        issuer, subject = represented if represented != (None, None) else legacy
        object.__setattr__(self, "represented_issuer", issuer)
        object.__setattr__(self, "represented_subject", subject)
        object.__setattr__(self, "acting_issuer", issuer)
        object.__setattr__(self, "acting_subject", subject)
        if (issuer is None) != (subject is None):
            msg = "represented_issuer and represented_subject must be set together"
            raise AuditContractError(msg)
        if issuer is not None and len(issuer) > REPRESENTED_ISSUER_MAX_LENGTH:
            msg = "represented_issuer is longer than the contract allows"
            raise AuditContractError(msg)
        if subject is not None and len(subject) > REPRESENTED_SUBJECT_MAX_LENGTH:
            msg = "represented_subject is longer than the contract allows"
            raise AuditContractError(msg)


SYSTEM_ACTOR = AuditActor(user_id=None, actor_type=AuditActorType.SYSTEM, actor_id=None)


def resolve_audit_actor(user_id: UUID | None) -> AuditActor:
    """Attribute to the authenticated credential of the current request.

    Delegates to the rule ``authz_audit_log`` already applies, so an event and
    the authorization decision of the same request can never name different
    credentials, and a new auth method only has to be taught once.
    """
    # Imported here because ``authorization.audit`` reads this module's request id.
    from langflow.services.authorization.audit import _resolve_actor

    resolved_user_id, actor_type, actor_id = _resolve_actor(user_id)
    represented = current_represented_identity.get()
    return AuditActor(
        user_id=resolved_user_id,
        actor_type=AuditActorType(actor_type),
        actor_id=actor_id,
        represented_issuer=represented.issuer if represented else None,
        represented_subject=represented.subject if represented else None,
    )


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
        represented_token = current_represented_identity.set(None)
        try:
            await self.app(scope, receive, send)
        finally:
            current_represented_identity.reset(represented_token)
            _request_id.reset(token)
