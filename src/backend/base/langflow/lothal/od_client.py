"""Open Design (OD) daemon HTTP client — Lothal's transport to the prototyping engine (Story U.4).

The prototype stage drives Open Design as a headless prototyping engine: Lothal
creates an OD project, starts a design run, reads back the generated artifacts,
and (on approval) copies them into its own store. This module is the thin
transport for that — one method per OD `/api/*` call the prototype engine needs,
nothing about *when* to call them (that is `langflow.lothal.prototype`).

It is the OD-facing sibling of `lothal_gateway` (which is OD → Lothal): here
Lothal is the client and OD is the server. OD's contract is pinned in
`open-design-ui-ux-stage.md` (`packages/contracts/src/api/*`); only non-browser,
server-to-server calls are made, so the origin check always passes and only the
optional bearer matters.

Configuration (env, read when the client is built):

- ``LOTHAL_OD_BASE_URL`` — the OD daemon base URL reachable from the backend.
  Defaults to ``http://open-design:7456`` (the compose service name, Story U.2).
- ``LOTHAL_OD_API_TOKEN`` (or ``OD_API_TOKEN``) — bearer for OD's API. Optional:
  OD ships internal-only with auth disabled (the private compose network is the
  boundary), so this is unset by default and only set for defense-in-depth.

Errors mirror the LLM bridge's split so the API layer can map them to distinct
HTTP statuses: ``ODConfigError`` (misconfiguration — a 503) vs
``ODConnectionError`` (the call itself failed — a 502).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx
from lfx.log.logger import logger

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self

# OD's daemon service name on the compose network (Story U.2). Overridable for a
# differently-named/hosted daemon.
_DEFAULT_OD_BASE_URL = "http://open-design:7456"

# OD calls are discrete request/response (a run is enqueued and executes in OD's
# background — `POST /api/runs` returns a runId promptly), so unlike the streaming
# LLM gateway a normal bounded timeout is correct. Generous enough for project
# creation / run enqueue, short enough that an unreachable daemon fails fast.
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class ODError(Exception):
    """Base class for every error raised by the Open Design client."""


class ODConfigError(ODError):
    """Open Design is not configured for use (e.g. an empty base URL)."""


class ODConnectionError(ODError):
    """A call to the Open Design daemon failed or returned an unusable response.

    Covers transport failures (daemon unreachable), non-2xx replies, and
    malformed/non-JSON bodies — anything that means the call did not succeed.
    """


def _resolve_base_url() -> str:
    """The OD daemon base URL from env, trailing slash stripped.

    Raises ``ODConfigError`` only if the var is explicitly set to blank — an
    unset var falls back to the compose default, so OD is "configured" by default.
    """
    raw = os.getenv("LOTHAL_OD_BASE_URL")
    if raw is None:
        return _DEFAULT_OD_BASE_URL
    base = raw.strip().rstrip("/")
    if not base:
        msg = "LOTHAL_OD_BASE_URL is set but empty; unset it to use the default, or give a URL."
        raise ODConfigError(msg)
    return base


def _resolve_token() -> str | None:
    """The optional OD API bearer from env (``LOTHAL_OD_API_TOKEN`` then ``OD_API_TOKEN``)."""
    for var in ("LOTHAL_OD_API_TOKEN", "OD_API_TOKEN"):
        token = (os.getenv(var) or "").strip()
        if token:
            return token
    return None


class ODClient:
    """An async client for the Open Design daemon `/api/*` surface.

    Use as an async context manager so the underlying connection is always
    closed:

        async with ODClient.from_env() as od:
            project = await od.create_project("My App", pending_prompt=brief)

    Each method maps to exactly one OD endpoint and returns OD's parsed JSON (or
    raw text, for file content). Any failure — transport, non-2xx, or a body that
    will not parse — is raised as ``ODConnectionError``.
    """

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"accept": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        # OD's origin-guard protects sensitive routes (e.g. /api/app-config). For a
        # server-to-server call the Host header is the daemon's service address
        # (e.g. `open-design:7456`) — a DNS name, neither loopback nor a private-IP
        # literal — so the guard rejects it unless the request's Origin exactly
        # matches an `OD_ALLOWED_ORIGINS` entry (the documented reverse-proxy escape
        # hatch). Send our own base origin as Origin; the deployment lists it in
        # OD_ALLOWED_ORIGINS so config writes (agent gateway + onboarding) succeed.
        parsed = urlsplit(self._base_url)
        if parsed.scheme and parsed.netloc:
            headers["origin"] = f"{parsed.scheme}://{parsed.netloc}"
        self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=_TIMEOUT)

    @classmethod
    def from_env(cls) -> Self:
        """Build a client from the environment (``LOTHAL_OD_BASE_URL`` / token)."""
        return cls(_resolve_base_url(), _resolve_token())

    @property
    def base_url(self) -> str:
        return self._base_url

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    # --- transport -----------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Issue one request, raising ``ODConnectionError`` on any failure.

        A transport error (daemon unreachable) and a non-2xx reply both mean the
        call did not succeed. OD's error bodies can echo project content, so the
        client-facing exception carries only the method/path/status — never the
        body — while the operator log gets the status.
        """
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            logger.warning(f"open-design request {method} {path} failed: {exc}")
            msg = f"Open Design request failed: {method} {path}."
            raise ODConnectionError(msg) from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            logger.warning(f"open-design {method} {path} → {response.status_code}")
            msg = f"Open Design returned {response.status_code} for {method} {path}."
            raise ODConnectionError(msg)
        return response

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._request(method, path, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            logger.warning(f"open-design {method} {path} returned a non-JSON body")
            msg = f"Open Design returned a non-JSON body for {method} {path}."
            raise ODConnectionError(msg) from exc

    # --- projects ------------------------------------------------------------

    async def create_project(
        self,
        name: str,
        *,
        project_id: str,
        pending_prompt: str | None = None,
        skill_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """`POST /api/projects` — create an OD project. Returns the project (carries `id`).

        OD requires the client to supply the project `id` (a safe slug:
        ``[A-Za-z0-9._-]``); without it the daemon rejects the call with
        ``invalid project id``. `pending_prompt` seeds the brief OD runs from;
        `metadata` records the Lothal linkage so an OD-side operator can trace a
        project back.
        """
        body: dict[str, Any] = {"id": project_id, "name": name}
        if pending_prompt is not None:
            body["pendingPrompt"] = pending_prompt
        if skill_id:
            body["skillId"] = skill_id
        if metadata is not None:
            body["metadata"] = metadata
        result = await self._request_json("POST", "/api/projects", json=body)
        # OD wraps the created project as ``{"project": {...}}``; tolerate a bare
        # ``{...}`` too (the contract docs show the unwrapped shape).
        project = result.get("project") if isinstance(result, dict) else None
        if not isinstance(project, dict):
            project = result if isinstance(result, dict) else {}
        if not project.get("id"):
            msg = "Open Design create-project response did not include a project id."
            raise ODConnectionError(msg)
        return project

    async def list_projects(self) -> list[dict[str, Any]]:
        """`GET /api/projects` — all OD projects (used to find one Lothal already created)."""
        result = await self._request_json("GET", "/api/projects")
        if isinstance(result, dict) and isinstance(result.get("projects"), list):
            return result["projects"]
        if isinstance(result, list):
            return result
        msg = "Open Design list-projects response was not a list of projects."
        raise ODConnectionError(msg)

    async def list_files(self, project_id: str) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/files` — the project's files with artifact manifests."""
        result = await self._request_json("GET", f"/api/projects/{project_id}/files")
        if isinstance(result, dict) and isinstance(result.get("files"), list):
            return result["files"]
        if isinstance(result, list):
            return result
        msg = "Open Design list-files response was not a list of files."
        raise ODConnectionError(msg)

    async def get_file_content(self, project_id: str, path: str) -> str:
        """`GET /api/projects/:id/raw/:path` — a single artifact file's raw text."""
        response = await self._request("GET", f"/api/projects/{project_id}/raw/{path.lstrip('/')}")
        return response.text

    # --- runs ----------------------------------------------------------------

    async def start_run(
        self,
        *,
        project_id: str,
        message: str,
        conversation_id: str | None = None,
        agent_id: str | None = None,
        skill_id: str | None = None,
    ) -> dict[str, Any]:
        """`POST /api/runs` — enqueue a design run. Returns `{runId, conversationId?}`.

        The flat body is OD's verified headless form: `projectId` is required,
        `message` carries the brief/instruction, and `conversationId` continues an
        existing conversation (a refine turn, Story U.6).
        """
        body: dict[str, Any] = {"projectId": project_id, "message": message}
        if conversation_id:
            body["conversationId"] = conversation_id
        if agent_id:
            body["agentId"] = agent_id
        if skill_id:
            body["skillId"] = skill_id
        result = await self._request_json("POST", "/api/runs", json=body)
        if not isinstance(result, dict) or not result.get("runId"):
            msg = "Open Design start-run response did not include a runId."
            raise ODConnectionError(msg)
        return result

    async def list_runs(self, project_id: str) -> list[dict[str, Any]]:
        """`GET /api/runs?projectId=:id` — the project's runs (newest-relevant status lives here)."""
        result = await self._request_json("GET", "/api/runs", params={"projectId": project_id})
        if isinstance(result, dict) and isinstance(result.get("runs"), list):
            return result["runs"]
        if isinstance(result, list):
            return result
        msg = "Open Design list-runs response was not a list of runs."
        raise ODConnectionError(msg)

    # --- config --------------------------------------------------------------

    async def update_app_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """`PUT /api/app-config` — merge into OD app config (e.g. point an agent at the gateway).

        OD's app-config write is `PUT` (it read-merges the body), not `PATCH`
        (verified live — `PATCH` 404s).
        """
        result = await self._request_json("PUT", "/api/app-config", json=body)
        return result if isinstance(result, dict) else {}
