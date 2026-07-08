"""An async client for the Lothal ReviewPane git-read service.

The git-read service (repo ``realbytecode/lothal_review``) runs as an internal
compose service reachable from the backend at ``http://review:8000``. It computes
read-only per-node diffs / file trees / blobs straight from the shared code-gen
repos volume (``git --git-dir``) — the backend of the ReviewPane (``prod_spec.md``
Part B). Like the PM service the browser never calls it directly; the backend
bridges to it and re-exposes the results at ``/api/v1/lothal/projects/{id}/review/*``
in ``api/v1/lothal.py``.

Unlike ``pm_client.py`` it is **unauthenticated**: the service is internal-only (no
host port) and carries no auth of its own — the langflow route resolves the caller's
ownership (R4) *before* every call, so authorization lives entirely on this side.

Configuration (env):
- ``LOTHAL_GITREAD_BASE_URL`` — reachable from the backend (default
  ``http://review:8000``, the compose service name).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
from lfx.log.logger import logger

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self

_DEFAULT_BASE_URL = "http://review:8000"
_TIMEOUT = httpx.Timeout(30.0)


class GitReadError(Exception):
    """Base class for every error raised by the git-read client."""


class GitReadConfigError(GitReadError):
    """The client is misconfigured (e.g. an empty base URL override)."""


class GitReadConnectionError(GitReadError):
    """A request to the git-read service failed (transport, non-2xx, or bad body).

    Carries the service's status code and ``detail`` so the bridge can pass a
    genuine 404 through (a missing node branch → the pane's empty state) rather
    than masking it as a 5xx.
    """

    def __init__(self, message: str, *, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _resolve_base_url() -> str:
    raw = os.getenv("LOTHAL_GITREAD_BASE_URL")
    if raw is None:
        return _DEFAULT_BASE_URL
    base = raw.strip()
    if not base:
        msg = "LOTHAL_GITREAD_BASE_URL is set but empty; unset it to use the default, or give a URL."
        raise GitReadConfigError(msg)
    return base


class GitReadClient:
    """Async client for the git-read service.

    Routes use the process-wide instance (``gitread_client()`` below); it is also an
    async context manager for one-off use.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url, headers={"accept": "application/json"}, timeout=_TIMEOUT
        )

    @classmethod
    def from_env(cls) -> Self:
        return cls(_resolve_base_url())

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            logger.warning(f"git-read request GET {path} failed: {exc}")
            msg = f"Lothal git-read request failed: GET {path}."
            raise GitReadConnectionError(msg) from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            detail = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    raw = body.get("detail")
                    detail = raw if isinstance(raw, str) else None
            except ValueError:
                pass
            logger.warning(f"git-read GET {path} → {response.status_code}")
            msg = f"Lothal git-read returned {response.status_code} for GET {path}."
            raise GitReadConnectionError(msg, status_code=response.status_code, detail=detail)
        try:
            return response.json()
        except ValueError as exc:
            msg = f"Lothal git-read returned a non-JSON body for GET {path}."
            raise GitReadConnectionError(msg) from exc

    # --- reads ---------------------------------------------------------------

    async def node_diff(self, repo: str, base: str, head: str, context: int = 3) -> dict[str, Any]:
        """`GET /diff` — the net node diff between the branch point and the node head."""
        return await self._get_json("/diff", {"repo": repo, "base": base, "head": head, "context": context})

    async def file_tree(self, repo: str, ref: str) -> dict[str, Any]:
        """`GET /filetree` — the nested tree of every path at `ref`."""
        return await self._get_json("/filetree", {"repo": repo, "ref": ref})

    async def blob(self, repo: str, ref: str, path: str) -> dict[str, Any]:
        """`GET /blob` — a file's content at `ref` (size-guarded, binary-flagged)."""
        return await self._get_json("/blob", {"repo": repo, "ref": ref, "path": path})


# --- process-wide singleton ---------------------------------------------------
# One client per process so the connection pool survives across requests. Created
# lazily so an absent/misconfigured git-read service surfaces as a per-request error
# rather than failing app boot; closed at lifespan shutdown (``aclose_gitread_client``).

_singleton: GitReadClient | None = None


def gitread_client() -> GitReadClient:
    """Return the process-wide git-read client, building it from the env on first use."""
    global _singleton  # noqa: PLW0603 — deliberate process-wide singleton
    if _singleton is None:
        _singleton = GitReadClient.from_env()
    return _singleton


async def aclose_gitread_client() -> None:
    """Close and clear the singleton (lifespan shutdown; tests use it to reset)."""
    global _singleton  # noqa: PLW0603 — deliberate process-wide singleton
    if _singleton is not None:
        await _singleton.aclose()
        _singleton = None
