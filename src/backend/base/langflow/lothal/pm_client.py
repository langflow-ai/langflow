"""An async client for the Lothal PM service `/api/*` surface (Story U-PLAN).

The PM service (the verification-driven project-management tree — repo
``realbytecode/lothal_project``) runs as an internal compose service reachable
from the backend at ``http://pm:8000``. Unlike Open Design (a foreign daemon we
keep hidden), the PM service *is our product*: the backend bridges to it here and
re-exposes its routes as the canonical Lothal API
(``/api/v1/lothal/projects/{id}/plan/*`` in ``api/v1/lothal.py``), which a native
shell page renders. The browser never calls the PM service directly.

Mirrors ``od_client.py``: an httpx async client, built ``from_env()``, with one
method per PM endpoint. It differs in one way — the PM API is authenticated
(JWT), so the client logs in once with a service account and sends the bearer on
every call, re-authenticating once on a 401.

Configuration (env, with dev-friendly defaults matching the PM image):
- ``LOTHAL_PM_BASE_URL``  — PM base URL reachable from the backend (default
  ``http://pm:8000``, the compose service name).
- ``LOTHAL_PM_USER`` / ``LOTHAL_PM_PASSWORD`` — service-account credentials
  (default ``admin`` / ``admin``, the PM image's seeded dev superuser).
"""

from __future__ import annotations

import os
from types import TracebackType
from typing import TYPE_CHECKING, Any

import httpx
from lfx.log.logger import logger

if TYPE_CHECKING:
    from typing_extensions import Self

_DEFAULT_PM_BASE_URL = "http://pm:8000"
_DEFAULT_PM_USER = "admin"
_DEFAULT_PM_PASSWORD = "admin"
_TIMEOUT = httpx.Timeout(30.0)


class PMError(Exception):
    """Base class for every error raised by the PM client."""


class PMConfigError(PMError):
    """The client is misconfigured (e.g. an empty base URL override)."""


class PMConnectionError(PMError):
    """A request to the PM service failed (transport, non-2xx, or unparseable body).

    Carries the PM status code and its ``detail`` message when the failure was an
    HTTP error. Because the PM service is *our* product (not a foreign daemon), its
    ``detail`` is a controlled, user-facing message — e.g. the ratify-gate reason —
    so the bridge passes it through (``_pm_error_to_http``) rather than hiding it.
    """

    def __init__(self, message: str, *, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _resolve_base_url() -> str:
    raw = os.getenv("LOTHAL_PM_BASE_URL")
    if raw is None:
        return _DEFAULT_PM_BASE_URL
    base = raw.strip()
    if not base:
        msg = "LOTHAL_PM_BASE_URL is set but empty; unset it to use the default, or give a URL."
        raise PMConfigError(msg)
    return base


class PMClient:
    """Async client for the Lothal PM service.

    Use as an async context manager so the connection is always closed::

        async with PMClient.from_env() as pm:
            tree = await pm.list_nodes(plan_id)

    Each method maps to one PM endpoint and returns the parsed JSON. Any failure —
    transport, non-2xx, or a body that will not parse — is raised as
    ``PMConnectionError``; its message carries only the method/path/status, never
    a response body (which could echo project content).
    """

    def __init__(self, base_url: str, *, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._client = httpx.AsyncClient(
            base_url=self._base_url, headers={"accept": "application/json"}, timeout=_TIMEOUT
        )

    @classmethod
    def from_env(cls) -> Self:
        """Build a client from the environment (base URL + service credentials)."""
        return cls(
            _resolve_base_url(),
            username=os.getenv("LOTHAL_PM_USER", _DEFAULT_PM_USER),
            password=os.getenv("LOTHAL_PM_PASSWORD", _DEFAULT_PM_PASSWORD),
        )

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

    # --- auth ----------------------------------------------------------------

    async def _login(self) -> str:
        """`POST /api/auth/login` (form) — exchange service creds for a bearer token."""
        try:
            response = await self._client.post(
                "/api/auth/login",
                data={"username": self._username, "password": self._password},
            )
        except httpx.HTTPError as exc:
            logger.warning(f"pm login request failed: {exc}")
            msg = "Lothal PM login request failed."
            raise PMConnectionError(msg) from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            logger.warning(f"pm login → {response.status_code}")
            msg = f"Lothal PM login returned {response.status_code}."
            raise PMConnectionError(msg)
        try:
            token = response.json()["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            msg = "Lothal PM login response did not include an access_token."
            raise PMConnectionError(msg) from exc
        self._token = token
        return token

    # --- transport -----------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Issue one authenticated request, re-authenticating once on a 401.

        Raises ``PMConnectionError`` on any failure. Error bodies can echo project
        content, so the exception carries only method/path/status — never the body.
        """
        if self._token is None:
            await self._login()
        for attempt in (1, 2):
            headers = {**kwargs.pop("headers", {}), "authorization": f"Bearer {self._token}"}
            try:
                response = await self._client.request(method, path, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning(f"pm request {method} {path} failed: {exc}")
                msg = f"Lothal PM request failed: {method} {path}."
                raise PMConnectionError(msg) from exc
            # A stale/expired token → one silent re-login + retry, then give up.
            if response.status_code == httpx.codes.UNAUTHORIZED and attempt == 1:
                await self._login()
                continue
            if response.status_code >= httpx.codes.BAD_REQUEST:
                logger.warning(f"pm {method} {path} → {response.status_code}")
                detail = None
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        raw = body.get("detail")
                        detail = raw if isinstance(raw, str) else None
                except ValueError:
                    pass
                msg = f"Lothal PM returned {response.status_code} for {method} {path}."
                raise PMConnectionError(msg, status_code=response.status_code, detail=detail)
            return response
        # Unreachable: the loop returns or raises on both attempts.
        msg = f"Lothal PM request {method} {path} exhausted retries."
        raise PMConnectionError(msg)

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._request(method, path, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            logger.warning(f"pm {method} {path} returned a non-JSON body")
            msg = f"Lothal PM returned a non-JSON body for {method} {path}."
            raise PMConnectionError(msg) from exc

    # --- projects (PM "plan" trees) ------------------------------------------

    async def list_projects(self) -> list[dict[str, Any]]:
        """`GET /api/projects` — the service account's PM trees."""
        result = await self._request_json("GET", "/api/projects")
        if isinstance(result, list):
            return result
        msg = "Lothal PM list-projects response was not a list."
        raise PMConnectionError(msg)

    async def create_project(self, name: str) -> dict[str, Any]:
        """`POST /api/projects` — create a PM tree (server-assigned id). Returns the project."""
        result = await self._request_json("POST", "/api/projects", json={"name": name})
        if not isinstance(result, dict) or not result.get("id"):
            msg = "Lothal PM create-project response did not include an id."
            raise PMConnectionError(msg)
        return result

    async def ensure_plan(self, langflow_project_id: str) -> str:
        """Map a Langflow project to its PM tree, creating it on first use.

        The PM service assigns its own ids, so we can't reuse the Langflow id
        directly; instead the PM tree is *named* after the Langflow project id and
        looked up by that name (idempotent — mirrors ``od_client`` list-then-create).
        The name MUST be the marker (not a human title) or the lookup can't find it
        and every call would create a new tree. Returns the PM project id.
        """
        marker = str(langflow_project_id)
        for project in await self.list_projects():
            if project.get("name") == marker:
                return str(project["id"])
        created = await self.create_project(marker)
        return str(created["id"])

    # --- nodes (the verification tree) ---------------------------------------

    async def list_nodes(self, plan_id: str) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/nodes` — the flattened node tree (parent + depth)."""
        result = await self._request_json("GET", f"/api/projects/{plan_id}/nodes")
        if isinstance(result, list):
            return result
        msg = "Lothal PM list-nodes response was not a list."
        raise PMConnectionError(msg)

    async def get_node(self, plan_id: str, node_id: str) -> dict[str, Any]:
        """`GET /api/projects/:id/nodes/:nid` — a node with its contract."""
        return await self._request_json("GET", f"/api/projects/{plan_id}/nodes/{node_id}")

    async def create_node(self, plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes` — add a node (see PM ``NodeCreate``)."""
        return await self._request_json("POST", f"/api/projects/{plan_id}/nodes", json=body)

    async def move_node(self, plan_id: str, node_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes/:nid/move` — reparent a node (``new_parent_id``, null = root)."""
        return await self._request_json(
            "POST", f"/api/projects/{plan_id}/nodes/{node_id}/move", json=body
        )

    async def update_contract(self, plan_id: str, node_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`PATCH /api/projects/:id/nodes/:nid/contract` — edit assume/guarantee (draft only)."""
        return await self._request_json(
            "PATCH", f"/api/projects/{plan_id}/nodes/{node_id}/contract", json=body
        )

    async def ratify(self, plan_id: str, node_id: str) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes/:nid/ratify` — run the roll-up gate for a node."""
        return await self._request_json("POST", f"/api/projects/{plan_id}/nodes/{node_id}/ratify")

    # --- links + ledger ------------------------------------------------------

    async def list_links(self, plan_id: str) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/links` — every dependency link in the tree."""
        result = await self._request_json("GET", f"/api/projects/{plan_id}/links")
        if isinstance(result, list):
            return result
        msg = "Lothal PM list-links response was not a list."
        raise PMConnectionError(msg)

    async def create_link(self, plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST /api/projects/:id/links` — add a dependency link (see PM ``LinkCreate``)."""
        return await self._request_json("POST", f"/api/projects/{plan_id}/links", json=body)

    async def activity(self, plan_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/activity` — the decision/provenance ledger (newest first)."""
        result = await self._request_json(
            "GET", f"/api/projects/{plan_id}/activity", params={"limit": limit}
        )
        if isinstance(result, list):
            return result
        msg = "Lothal PM activity response was not a list."
        raise PMConnectionError(msg)

    # --- contract / criteria / state (the validation loop) -------------------

    async def update_criteria(self, plan_id: str, node_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`PATCH /api/projects/:id/nodes/:nid/criteria` — edit the verification criteria (draft only)."""
        return await self._request_json(
            "PATCH", f"/api/projects/{plan_id}/nodes/{node_id}/criteria", json=body
        )

    async def transition(self, plan_id: str, node_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes/:nid/transition` — drive the state machine (e.g. reopen → draft)."""
        return await self._request_json(
            "POST", f"/api/projects/{plan_id}/nodes/{node_id}/transition", json=body
        )

    async def node_events(self, plan_id: str, node_id: str) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/nodes/:nid/events` — the node's ledger events (its history)."""
        result = await self._request_json("GET", f"/api/projects/{plan_id}/nodes/{node_id}/events")
        if isinstance(result, list):
            return result
        msg = "Lothal PM node-events response was not a list."
        raise PMConnectionError(msg)

    async def node_dependencies(self, plan_id: str, node_id: str) -> dict[str, Any]:
        """`GET /api/projects/:id/nodes/:nid/dependencies` — upstream/downstream derives-from sets."""
        return await self._request_json("GET", f"/api/projects/{plan_id}/nodes/{node_id}/dependencies")

    # --- tests ----------------------------------------------------------------

    async def list_tests(self, plan_id: str, node_id: str) -> list[dict[str, Any]]:
        """`GET /api/projects/:id/nodes/:nid/tests` — the node's tests."""
        result = await self._request_json("GET", f"/api/projects/{plan_id}/nodes/{node_id}/tests")
        if isinstance(result, list):
            return result
        msg = "Lothal PM list-tests response was not a list."
        raise PMConnectionError(msg)

    async def create_test(self, plan_id: str, node_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes/:nid/tests` — author a test (see PM ``TestCreate``)."""
        return await self._request_json(
            "POST", f"/api/projects/{plan_id}/nodes/{node_id}/tests", json=body
        )

    async def record_test_run(
        self, plan_id: str, node_id: str, test_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """`POST /api/projects/:id/nodes/:nid/tests/:tid/runs` — record a test run result.

        The PM service only accepts runs once the node is ``in_progress`` (it 4xxs
        otherwise — frozen-before-build: you run the frozen tests, you don't re-run a draft).
        """
        return await self._request_json(
            "POST",
            f"/api/projects/{plan_id}/nodes/{node_id}/tests/{test_id}/runs",
            json=body,
        )

    # --- DAG render -----------------------------------------------------------

    async def dag_svg(self, plan_id: str) -> str:
        """`GET /api/projects/:id/dag.svg` — the server-rendered dependency graph as SVG text."""
        response = await self._request("GET", f"/api/projects/{plan_id}/dag.svg")
        return response.text
