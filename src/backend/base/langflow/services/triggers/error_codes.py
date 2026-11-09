"""Stable codes for the trigger errors a person is shown.

The server words its errors in English. A code lets the UI show them in the
reader's language: ``TriggerRead.last_error_code`` names a stored error, and a
refused ``enable`` answers ``{"code", "message"}``. A code is part of the API,
so it never changes; the message can. An error without a code stays readable
in English through its message.

This module owns the stored error strings it recognizes, so the text that is
written and the text that is classified cannot drift apart.
"""

from __future__ import annotations

from enum import Enum

from langflow.services.triggers.constants import CONNECTION_NOT_AUTHORIZED_ERROR


class TriggerErrorCode(str, Enum):
    MULTIPLE_TRIGGERS = "multiple_triggers"
    NODE_REMOVED = "node_removed"
    SOURCE_SETTINGS_CHANGED = "source_settings_changed"
    CONNECTION_NOT_AUTHORIZED = "connection_not_authorized"
    INVALID_CRON = "invalid_cron"
    CRON_NEVER_MATCHES = "cron_never_matches"
    TIMEZONE_REQUIRED = "timezone_required"
    UNKNOWN_TIMEZONE = "unknown_timezone"
    BACKGROUND_RUNS_NOT_ALLOWED = "background_runs_not_allowed"
    CONNECTION_UNUSABLE = "connection_unusable"


class CodedTriggerError(ValueError):
    """A trigger refusal whose reason the UI can show in the reader's language."""

    def __init__(self, code: TriggerErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code.value


#: Why a trigger whose node left the canvas was paused. Reconciliation owns this
#: reason: it blocks resuming while the node is gone, and the save that adds the
#: node back clears it. A config verdict must not erase it, since a schedule edit
#: through the API does not bring the node back.
NODE_REMOVED_ERROR = "trigger node removed from the flow"

MULTIPLE_TRIGGERS_ERROR = "A flow can have only one trigger. Remove the extra triggers and try again."

#: Why an armed Microsoft or Google source was paused by a save that changed its
#: settings: the provider subscription was retired with the old settings, so it
#: takes an explicit enable to subscribe again with the new ones.
SOURCE_SETTINGS_CHANGED_ERROR = "Source settings changed. Enable the trigger again to resubscribe."

INVALID_CRON_ERROR = "Invalid cron expression: a valid five-field cron expression is required."
CRON_NEVER_MATCHES_ERROR = "Invalid cron expression: it never matches a real date."
TIMEZONE_REQUIRED_ERROR = "A non-empty IANA timezone is required."
UNKNOWN_TIMEZONE_ERROR = "Unknown timezone; use an IANA timezone name."
SLACK_BACKGROUND_RUNS_NOT_ALLOWED_ERROR = (
    "Turn on 'Allow background runs' for the Slack connection this trigger uses: a trigger runs its flow "
    "with no one signed in, and the connection's owner has not allowed that yet."
)
SLACK_CONNECTION_UNUSABLE_ERROR = (
    "The Slack connection this trigger uses is revoked or expired. Reconnect it, then enable the trigger."
)

_STORED_ERRORS: dict[str, TriggerErrorCode] = {
    MULTIPLE_TRIGGERS_ERROR: TriggerErrorCode.MULTIPLE_TRIGGERS,
    NODE_REMOVED_ERROR: TriggerErrorCode.NODE_REMOVED,
    SOURCE_SETTINGS_CHANGED_ERROR: TriggerErrorCode.SOURCE_SETTINGS_CHANGED,
    CONNECTION_NOT_AUTHORIZED_ERROR: TriggerErrorCode.CONNECTION_NOT_AUTHORIZED,
    TriggerErrorCode.CONNECTION_UNUSABLE.value: TriggerErrorCode.CONNECTION_UNUSABLE,
    INVALID_CRON_ERROR: TriggerErrorCode.INVALID_CRON,
    CRON_NEVER_MATCHES_ERROR: TriggerErrorCode.CRON_NEVER_MATCHES,
    TIMEZONE_REQUIRED_ERROR: TriggerErrorCode.TIMEZONE_REQUIRED,
    UNKNOWN_TIMEZONE_ERROR: TriggerErrorCode.UNKNOWN_TIMEZONE,
    SLACK_BACKGROUND_RUNS_NOT_ALLOWED_ERROR: TriggerErrorCode.BACKGROUND_RUNS_NOT_ALLOWED,
    SLACK_CONNECTION_UNUSABLE_ERROR: TriggerErrorCode.CONNECTION_UNUSABLE,
}


def last_error_code(last_error: str | None) -> str | None:
    """The code of a stored ``last_error``, or ``None`` for text only a person can read."""
    if last_error is None:
        return None
    code = _STORED_ERRORS.get(last_error)
    return code.value if code is not None else None


def refusal_detail(exc: ValueError) -> dict[str, str | None]:
    """The ``detail`` of a refused trigger action: a code when one applies, and the English message."""
    message = str(exc)
    code = getattr(exc, "code", None) or last_error_code(message)
    return {"code": code, "message": message}
