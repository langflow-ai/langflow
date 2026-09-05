"""Scope constants and the shared connection field for wave-1 Google actions.

Scopes are declared as the full ``https://www.googleapis.com/auth/...`` URLs the
capability matrix records, not the short suffixes, because that is the form
Google returns in the token response and therefore the form the database
resolver stores in ``granted_scopes`` and compares against as raw strings. A
short scope here would fail every resolution with ``scope-missing``.
"""

from __future__ import annotations

from lfx.io import ConnectionRefInput

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
CALENDAR_EVENTS_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"

_CONNECTION_INFO = (
    "Managed Google connection to run this action as, written as 'google/<name>'. "
    "Create it under Settings and authorize the scopes this action requires."
)


def google_connection_input(
    *,
    required_scopes: list[str],
    capabilities: list[str] | None = None,
    required: bool = True,
    info: str = _CONNECTION_INFO,
) -> ConnectionRefInput:
    """Build the ``connection`` field every connection-backed Google action shares."""
    return ConnectionRefInput(
        name="connection",
        display_name="Google Connection",
        info=info,
        provider="google",
        auth_profile_id="user",
        identity_kind="user",
        required_scopes=required_scopes,
        capabilities=capabilities or [],
        required=required,
    )
