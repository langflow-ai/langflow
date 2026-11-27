"""Shared helpers for the CleanedWeb components."""

from __future__ import annotations

from cleanedweb import CleanedWeb
from cleanedweb.exceptions import CleanedWebError
from lfx.schema.data import Data


def make_client(api_key: str | None = None) -> CleanedWeb:
    """A CleanedWeb client.  Without ``api_key`` the client falls back to ``CLEANEDWEB_API_KEY``.

    Catalog reads need no key; the key is only sent to the run API.
    """
    return CleanedWeb(api_key=api_key or None)


def error_message(error: Exception) -> str:
    """Describe a failure, keeping the API's own status, code and message."""
    if isinstance(error, CleanedWebError):
        return f"CleanedWeb error: {error}"
    return str(error)


def error_rows(message: str) -> list[Data]:
    return [Data(text=message, data={"error": message})]
