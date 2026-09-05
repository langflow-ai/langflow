"""Client-facing error policy for owner and delegated workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from lfx.integrations.errors import IntegrationError

SAFE_WORKFLOW_ERROR_MESSAGE = "Workflow execution failed."

# Generic replacement for an integration error's own sentence on paths where the
# caller is not the connection's owner. The typed fields still cross (a client
# needs the code to render the right call to action); only free text is dropped.
SAFE_INTEGRATION_ERROR_MESSAGE = "This flow could not use one of its connections."


@dataclass(frozen=True, slots=True)
class ExecutionErrorDetails:
    """The error fields that may cross an execution API boundary.

    ``code`` and the fields after it are populated only for
    ``lfx.integrations.errors.IntegrationError``; they stay ``None``/``False`` for
    every other failure, so existing consumers of ``message``/``stack_trace`` are
    unchanged.
    """

    message: str
    stack_trace: str
    code: str | None = None
    hint: str | None = None
    provider: str | None = None
    retryable: bool = False
    retry_after: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_client_body(self) -> dict[str, Any]:
        """The typed body an integration failure sends to a client.

        Only meaningful when ``code`` is set; callers gate on that.
        """
        body: dict[str, Any] = {"error_code": self.code, "message": self.message}
        if self.hint:
            body["hint"] = self.hint
        if self.provider:
            body["provider"] = self.provider
        body["retryable"] = self.retryable
        if self.retry_after is not None:
            body["retry_after"] = self.retry_after
        return body


def _integration_details(error: IntegrationError, *, expose_details: bool) -> ExecutionErrorDetails:
    """Build the typed body for an integration failure under either error policy.

    An ``IntegrationError`` is sanitized by construction (URLs and e-mail
    addresses are scrubbed when it is raised), so the code, hint, provider and
    retry metadata are safe on every path and are always emitted -- INT-8's UI
    turns the code into a "reconnect this integration" call to action, and a
    public visitor seeing a generic sentence with no code has nothing to act on.

    The error's own ``safe_message`` still names a non-secret handle
    (``Connection 'google/work' could not be resolved``), which tells a delegated
    or anonymous caller which account the owner uses. It is emitted only when the
    caller is entitled to owner diagnostics.
    """
    return ExecutionErrorDetails(
        message=error.safe_message if expose_details else SAFE_INTEGRATION_ERROR_MESSAGE,
        stack_trace="",
        code=error.code,
        hint=error.hint,
        provider=error.provider,
        retryable=error.retryable,
        retry_after=getattr(error, "retry_after", None),
        details=dict(error.details) if expose_details else {},
    )


def error_details_for_client(
    error: Exception,
    *,
    expose_details: bool,
    message: str | None = None,
    stack_trace: str | None = None,
) -> ExecutionErrorDetails:
    """Keep owner diagnostics while removing delegated/public runtime details."""
    if isinstance(error, IntegrationError):
        return _integration_details(error, expose_details=expose_details)
    if expose_details:
        return ExecutionErrorDetails(
            message=message if message is not None else str(error),
            stack_trace=stack_trace or "",
        )
    return ExecutionErrorDetails(message=SAFE_WORKFLOW_ERROR_MESSAGE, stack_trace="")


def error_for_client(error: Exception, *, expose_details: bool) -> Exception:
    """Return an exception suitable for serializers that accept an exception object."""
    if isinstance(error, IntegrationError):
        # Typed, machine-readable, and safe on every path: the status comes from
        # the error itself (403 for an unauthorized connection, 401 for expired
        # credentials, 429 for a rate limit) rather than collapsing into a 500.
        details = _integration_details(error, expose_details=expose_details)
        return HTTPException(status_code=error.http_status or 400, detail=details.as_client_body())
    if expose_details:
        return error
    if isinstance(error, HTTPException):
        return HTTPException(
            status_code=error.status_code,
            detail=SAFE_WORKFLOW_ERROR_MESSAGE,
            headers=error.headers,
        )
    return RuntimeError(SAFE_WORKFLOW_ERROR_MESSAGE)


def integration_http_error(error: Exception, *, expose_details: bool) -> HTTPException | None:
    """The typed HTTPException for an integration failure, or ``None`` for anything else.

    Terminal run handlers wrap whatever a flow raised into a generic 500. That is
    right for a component that blew up, but wrong for a connection the caller is
    not allowed to use: the code, the status and the call to action all disappear.
    Call this first and raise the result when it is not ``None``.
    """
    if not isinstance(error, IntegrationError):
        return None
    client_error = error_for_client(error, expose_details=expose_details)
    return client_error if isinstance(client_error, HTTPException) else None


def caller_owns_flow(flow: object, user: object) -> bool:
    """Return whether the request actor and stored flow owner are the same principal."""
    flow_user_id = getattr(flow, "user_id", None)
    user_id = getattr(user, "id", None)
    return flow_user_id is not None and user_id is not None and str(flow_user_id) == str(user_id)
