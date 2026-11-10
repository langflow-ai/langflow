"""Marking an authorization refusal so later layers can tell it from a failure.

A guard refuses with an ``HTTPException``, and the 404 mask in ``fetch`` may
rewrite it. Both look like any other error by the time a route's audit wrapper
sees them, but the audit contract records what an operation *did*: a refusal is
an authorization decision, already written to ``authz_audit_log``, and must not
also appear as a failed operation. The mark travels with the exception so the
distinction survives the rewrite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import HTTPException

_MARK = "__langflow_authorization_refusal__"


def mark_authorization_refusal(exc: HTTPException) -> HTTPException:
    """Tag an exception as an authorization refusal and return it."""
    setattr(exc, _MARK, True)
    return exc


def is_authorization_refusal(exc: BaseException) -> bool:
    """True when this exception is a guard's refusal, however it was relabelled."""
    return getattr(exc, _MARK, False) is True
