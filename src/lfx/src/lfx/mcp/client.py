"""Async HTTP client for Langflow REST API.

Adapted from the CLI's sync Backend class, using httpx.AsyncClient
for non-blocking operations inside the MCP server.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from starlette.status import HTTP_204_NO_CONTENT


class LangflowClient:
    """Async HTTP client for Langflow's REST API.

    Auth sends both headers on every request:
    - Authorization: Bearer <access_token or api_key>
    - x-api-key: <api_key> (when available)

    Uses a persistent httpx.AsyncClient for connection pooling.
    """

    def __init__(
        self,
        server_url: str | None = None,
        api_key: str | None = None,
        access_token: str | None = None,
    ):
        self.server_url = (server_url or os.environ.get("LANGFLOW_SERVER_URL", "http://localhost:7860")).rstrip("/")
        self.api_key = api_key or os.environ.get("LANGFLOW_API_KEY")
        self.access_token = access_token
        self._http: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _client(self) -> httpx.AsyncClient:
        async with self._lock:
            if self._http is None or self._http.is_closed:
                self._http = httpx.AsyncClient(follow_redirects=True)
            return self._http

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = self.access_token or self.api_key
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _url(self, path: str) -> str:
        return f"{self.server_url}/api/v1{path}"

    async def get(self, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            client = await self._client()
            resp = await client.get(url, headers=self._headers(), timeout=30.0, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"GET {path} failed ({exc.response.status_code})"
            raise RuntimeError(msg) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"GET {path} failed: {exc}"
            raise RuntimeError(msg) from exc

    async def post(self, path: str, json_data: Any = None, timeout: float = 30.0, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            client = await self._client()
            resp = await client.post(url, headers=self._headers(), json=json_data, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"POST {path} failed ({exc.response.status_code})"
            raise RuntimeError(msg) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"POST {path} failed: {exc}"
            raise RuntimeError(msg) from exc

    async def patch(self, path: str, json_data: Any = None, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            client = await self._client()
            resp = await client.patch(url, headers=self._headers(), json=json_data, timeout=30.0, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"PATCH {path} failed ({exc.response.status_code})"
            raise RuntimeError(msg) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"PATCH {path} failed: {exc}"
            raise RuntimeError(msg) from exc

    async def delete(self, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            client = await self._client()
            resp = await client.delete(url, headers=self._headers(), timeout=30.0, **kwargs)
            resp.raise_for_status()
            if resp.status_code == HTTP_204_NO_CONTENT or not resp.content:
                return {}
            return resp.json()
        except httpx.HTTPStatusError as exc:
            msg = f"DELETE {path} failed ({exc.response.status_code})"
            raise RuntimeError(msg) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"DELETE {path} failed: {exc}"
            raise RuntimeError(msg) from exc

    async def login(self, username: str, password: str) -> str:
        """Authenticate and create an API key.

        Each call creates a new API key on the server.
        Returns the API key string.
        """
        try:
            client = await self._client()
            # Login to get JWT
            resp = await client.post(
                self._url("/login"),
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            resp.raise_for_status()
            token_data = resp.json()
            if "access_token" not in token_data:
                msg = f"Login response missing 'access_token': {list(token_data.keys())}"
                raise RuntimeError(msg)
            self.access_token = token_data["access_token"]

            # Create API key
            resp = await client.post(
                self._url("/api_key/"),
                headers=self._headers(),
                json={"name": "mcp-client"},
                timeout=30.0,
            )
            resp.raise_for_status()
            key_data = resp.json()
            if "api_key" not in key_data:
                msg = f"API key response missing 'api_key': {list(key_data.keys())}"
                raise RuntimeError(msg)
            self.api_key = key_data["api_key"]
        except httpx.HTTPStatusError as exc:
            msg = f"Login failed ({exc.response.status_code})"
            raise RuntimeError(msg) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"Login failed: {exc}"
            raise RuntimeError(msg) from exc
        return self.api_key
