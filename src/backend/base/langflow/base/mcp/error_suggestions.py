from __future__ import annotations

"""Utility helpers for providing actionable suggestions based on error messages.

This module groups together a few small helpers that attempt to recognise
common error patterns so that the caller can attach concrete and helpful
troubleshooting guidance to API error responses.

These helpers purposefully avoid pulling in heavy dependencies.  A couple of
simple ``in`` string checks cover the vast majority of user-facing scenarios
we want to handle here.

The module currently exposes two public helper functions:

    * ``get_connection_error_suggestions`` - Suggestions for network/connection
      failures (timeouts, refused connection, command-not-found, …)
    * ``get_validation_error_suggestions`` - Suggestions for configuration /
      validation problems detected locally before any network I/O happens.

Both helpers return a *list[str]* so that callers can directly marshal the
result into JSON responses.
"""


__all__ = [
    "get_connection_error_suggestions",
    "get_validation_error_suggestions",
]


def _normalise(msg: str | Exception) -> str:
    """Return a lower-cased representation of *msg* suitable for substring checks."""
    if isinstance(msg, Exception):
        msg = str(msg)
    return msg.lower()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_connection_error_suggestions(error_msg: str | Exception) -> list[str]:
    """Generate actionable suggestions for *connection* type errors.

    The function tries to match a handful of well-known substrings and adds a
    couple of high-level fall-back hints at the end if no specific case has
    matched.
    """
    msg = _normalise(error_msg)
    suggestions: list[str] = []

    if "timeout" in msg or "timed out" in msg:
        suggestions.extend(
            [
                "Increase the connection timeout in server settings.",
                "Check if the server is running and reachable from this machine.",
                "Verify network connectivity and any firewall rules between the client and the server.",
            ]
        )

    if "command not found" in msg or "not found: '" in msg:
        suggestions.extend(
            [
                "Ensure the command is installed and available in your PATH.",
                "Double-check the command spelling and required arguments.",
                "Try running the command manually in a terminal to verify it works.",
            ]
        )

    if "connection refused" in msg or "cannot connect" in msg:
        suggestions.extend(
            [
                "Verify the server URL and port are correct.",
                "Confirm the server process is up and listening for connections.",
                "Check whether a reverse-proxy or firewall is blocking the request.",
            ]
        )

    if "transport" in msg or "streamable http" in msg:
        suggestions.extend(
            [
                "Make sure the server supports the requested transport protocol.",
                "Try a different transport type if the server offers multiple protocols.",
                "Confirm that the server URL points to the correct endpoint (e.g. /mcp).",
            ]
        )

    # Generic fall-back - only add if we have not matched anything specific
    if not suggestions:
        suggestions.append("Check the server configuration and network connectivity.")

    return suggestions


def get_validation_error_suggestions(error_msg: str | Exception) -> list[str]:
    """Generate actionable suggestions for *validation* type errors."""
    msg = _normalise(error_msg)
    suggestions: list[str] = []

    if "url" in msg and "invalid" in msg:
        suggestions.extend(
            [
                "Ensure the URL includes the protocol (http:// or https://).",
                "Verify the URL format and spelling are correct.",
                "Confirm the server is accessible at the specified address.",
            ]
        )

    if "env" in msg or "environment" in msg:
        suggestions.extend(
            [
                "Use the KEY=VALUE format for environment variables.",
                "Escape special characters if required by the shell or configuration format.",
                "Double-check the environment variable names for typos.",
            ]
        )

    if "command" in msg and ("invalid" in msg or "not found" in msg):
        suggestions.extend(
            [
                "Ensure the command path is correct and executable.",
                "Check whether additional arguments are needed.",
                "Verify that the command is installed and accessible.",
            ]
        )

    if not suggestions:
        suggestions.append("Review the server configuration parameters for mistakes.")

    return suggestions
