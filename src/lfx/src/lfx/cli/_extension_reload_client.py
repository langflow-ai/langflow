"""HTTP client helper for ``lfx extension reload``.

Kept separate from the typer command so the request/response shape can be
unit-tested without spinning up a full CLI invocation.  The CLI command
in :mod:`lfx.cli._extension_commands` delegates to :func:`reload_via_http`
and is responsible only for argument parsing and rendering.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_TARGET = "http://localhost:7860"
"""Fallback Langflow server URL when neither ``--target`` nor ``LANGFLOW_HOST`` is set."""

_HTTP_OK = 200
"""Named constant for the only status code we treat as a success."""


@dataclass(frozen=True)
class ReloadHttpResponse:
    """Outcome of a single HTTP reload call.

    ``status`` is the HTTP status code (200 on success; 409 for
    reload-in-progress; other non-2xx for transport / auth failures).
    ``payload`` is the parsed JSON body, or a synthetic ``{"error": ...}``
    dict when the response was not JSON.  ``ok`` mirrors the body's ``ok``
    field on success-shaped responses, otherwise False.
    """

    status: int
    payload: dict[str, Any]
    ok: bool

    def exit_code(self) -> int:
        """Map outcome to a CLI exit code (0 success / 1 failure)."""
        return 0 if self.ok else 1


def resolve_target(explicit: str | None) -> str:
    """Pick the server URL to call.  Precedence: explicit > $LANGFLOW_HOST > default."""
    if explicit:
        return explicit.rstrip("/")
    env_target = os.environ.get("LANGFLOW_HOST")
    if env_target:
        return env_target.rstrip("/")
    return DEFAULT_TARGET


def resolve_api_key(explicit: str | None) -> str | None:
    """Pick the API key to send.  Precedence: explicit > env > None."""
    if explicit:
        return explicit
    return os.environ.get("LANGFLOW_API_KEY")


def reload_via_http(
    *,
    target: str | None,
    api_key: str | None,
    extension_id: str,
    bundle_name: str,
    timeout: float = 30.0,
) -> ReloadHttpResponse:
    """POST a reload request to the Langflow extension dev server.

    Returns a :class:`ReloadHttpResponse` that the caller renders.  Network
    failures raise no exceptions out of this helper -- they surface as a
    synthetic non-2xx response so the CLI can render them with the same
    typed-error formatting as server-side failures.
    """
    base = resolve_target(target)
    url = f"{base}/api/v1/extensions/{extension_id}/bundles/{bundle_name}/reload"
    headers: dict[str, str] = {"Accept": "application/json"}
    key = resolve_api_key(api_key)
    if key is not None:
        headers["x-api-key"] = key

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers)
    except httpx.RequestError as exc:
        # Transport-layer failure: connection refused, DNS, TLS, timeout.
        # Use ``reload-transport-error`` so the CLI / log scrapers can
        # distinguish "could not reach the server" from "the server
        # responded that the source path is missing" -- the latter is
        # ``reload-source-missing`` and is a server-side condition.
        return ReloadHttpResponse(
            status=0,
            payload={
                "ok": False,
                "errors": [
                    {
                        "code": "reload-transport-error",
                        "message": f"Could not reach Langflow server at {url}: {exc}",
                        "location": url,
                        "hint": (
                            "Start the dev server (e.g. `lfx run`) and pass --target / "
                            "set LANGFLOW_HOST if it is not on http://localhost:7860."
                        ),
                    }
                ],
            },
            ok=False,
        )

    try:
        payload = response.json()
        if not isinstance(payload, dict):
            payload = {"ok": False, "raw": payload}
    except ValueError:
        payload = {
            "ok": False,
            "errors": [
                {
                    "code": "reload-transport-error",
                    "message": f"Server returned non-JSON body (HTTP {response.status_code}): {response.text[:200]}",
                    "location": url,
                    "hint": "Confirm the URL points at a Langflow server with the v1 API enabled.",
                }
            ],
        }

    success_ok = response.status_code == _HTTP_OK and bool(payload.get("ok"))
    return ReloadHttpResponse(status=response.status_code, payload=payload, ok=success_ok)
