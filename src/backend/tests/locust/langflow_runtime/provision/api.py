"""Sync httpx helpers for performance-suite provisioning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx

if TYPE_CHECKING:
    from tests.locust.langflow_runtime.clients.base import ApiClient

DEFAULT_TIMEOUT_S = 60.0


class ProvisionApiError(RuntimeError):
    """HTTP or application failure during provisioning."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ProvisionHttp:
    """Thin sync client with bearer / API-key auth for provision CLI commands."""

    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str | None = None,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout_s)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ProvisionHttp:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def api_client(self, *, api_key: str | None = None, bearer_token: str | None = None) -> ApiClient:
        """Build a protocol-suite ``ApiClient`` over this provision httpx session.

        Prefer this over reaching into ``_client``. Credentials default to whatever
        is already set on the provisioner (API key / bearer from auth).
        """
        from tests.locust.langflow_runtime.clients.base import ApiClient

        return ApiClient.from_httpx(
            self._client,
            base_url=self.base_url,
            api_key=api_key if api_key is not None else self.api_key,
            bearer_token=bearer_token if bearer_token is not None else self.bearer_token,
            connect_timeout_s=float(self.timeout_s),
            read_timeout_s=float(self.timeout_s),
        )

    def url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        ok_statuses: set[int] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        response = self._client.request(method, self.url(path), headers=self._headers(headers), **kwargs)
        if ok_statuses is not None and response.status_code not in ok_statuses:
            body: Any
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise ProvisionApiError(
                f"{method.upper()} {path} failed with HTTP {response.status_code}",
                status_code=response.status_code,
                body=body,
            )
        return response

    def health(self) -> dict[str, Any]:
        response = self.request("GET", "/health", ok_statuses={200})
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "raw": response.text}

    def login(self, username: str, password: str) -> str:
        response = self.request(
            "POST",
            "/api/v1/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            ok_statuses={200},
        )
        token = response.json().get("access_token")
        if not token:
            raise ProvisionApiError("login response missing access_token", body=response.json())
        self.bearer_token = str(token)
        return self.bearer_token

    def auto_login(self) -> str:
        response = self.request("GET", "/api/v1/auto_login", ok_statuses={200})
        token = response.json().get("access_token")
        if not token:
            raise ProvisionApiError("auto_login response missing access_token", body=response.json())
        self.bearer_token = str(token)
        return self.bearer_token

    def create_api_key(self, name: str) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/api/v1/api_key/",
            json={"name": name},
            ok_statuses={200, 201},
        )
        return response.json()

    def delete_api_key(self, api_key_id: str) -> None:
        self.request("DELETE", f"/api/v1/api_key/{api_key_id}", ok_statuses={200, 204, 404})

    def create_project(self, name: str, *, description: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if description is not None:
            payload["description"] = description
        response = self.request("POST", "/api/v1/projects/", json=payload, ok_statuses={201})
        return response.json()

    def delete_project(self, project_id: str) -> None:
        self.request("DELETE", f"/api/v1/projects/{project_id}", ok_statuses={200, 204, 404})

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        response = self.request("GET", f"/api/v1/projects/{project_id}", ok_statuses={200, 404})
        if response.status_code == 404:
            return None
        return response.json()

    def create_flow(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.request("POST", "/api/v1/flows/", json=payload, ok_statuses={201})
        return response.json()

    def upload_flow_json(
        self, flow_json: dict[str, Any] | list[dict[str, Any]], *, folder_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Upload flow JSON via multipart (same shape as UI export)."""
        body = flow_json if isinstance(flow_json, dict) else {"flows": flow_json}
        raw = json.dumps(body).encode("utf-8")
        files = {"file": ("flow.json", raw, "application/json")}
        params = {"folder_id": folder_id} if folder_id else None
        response = self.request(
            "POST",
            "/api/v1/flows/upload/",
            files=files,
            params=params,
            ok_statuses={201},
        )
        data = response.json()
        if isinstance(data, list):
            return data
        return [data]

    def patch_flow(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.request("PATCH", f"/api/v1/flows/{flow_id}", json=payload, ok_statuses={200})
        return response.json()

    def get_flow(self, flow_id: str) -> dict[str, Any] | None:
        response = self.request("GET", f"/api/v1/flows/{flow_id}", ok_statuses={200, 404})
        if response.status_code == 404:
            return None
        return response.json()

    def delete_flow(self, flow_id: str) -> None:
        self.request("DELETE", f"/api/v1/flows/{flow_id}", ok_statuses={200, 204, 404})

    def patch_mcp_project(
        self,
        project_id: str,
        *,
        settings: list[dict[str, Any]],
        auth_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"settings": settings}
        if auth_settings is not None:
            payload["auth_settings"] = auth_settings
        response = self.request(
            "PATCH",
            f"/api/v1/mcp/project/{project_id}",
            json=payload,
            ok_statuses={200},
        )
        return response.json()

    def create_knowledge_base(
        self,
        name: str,
        *,
        embedding_provider: str = "HuggingFace",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selection = model_selection or {
            "name": embedding_model,
            "provider": embedding_provider,
            "metadata": {
                "embedding_class": "HuggingFaceEmbeddings",
                "param_mapping": {"model_name": "model"},
            },
        }
        response = self.request(
            "POST",
            "/api/v1/knowledge_bases/",
            json={
                "name": name,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "model_selection": selection,
                "backend_type": "chroma",
            },
            ok_statuses={201, 409},
        )
        if response.status_code == 409:
            # Idempotent: treat existing KB as success and return a stub.
            return {"name": name, "already_exists": True}
        return response.json()

    def get_knowledge_base(self, kb_name: str) -> dict[str, Any] | None:
        response = self.request("GET", f"/api/v1/knowledge_bases/{kb_name}", ok_statuses={200, 404})
        if response.status_code == 404:
            return None
        return response.json()

    def ingest_knowledge_base(self, kb_name: str, paths: list[str]) -> dict[str, Any]:
        files = [("files", (Path(path).name, Path(path).read_bytes(), "text/plain")) for path in paths]
        response = self.request(
            "POST",
            f"/api/v1/knowledge_bases/{kb_name}/ingest",
            data={"chunk_size": "1000", "chunk_overlap": "200", "source_name": "perf-suite"},
            files=files,
            ok_statuses={200},
        )
        return response.json()

    def delete_knowledge_base(self, kb_name: str) -> None:
        self.request("DELETE", f"/api/v1/knowledge_bases/{kb_name}", ok_statuses={200, 204, 404})

    def create_memory_base(
        self,
        *,
        name: str,
        flow_id: str,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/api/v1/memories/",
            json={
                "name": name,
                "flow_id": flow_id,
                "threshold": 1,
                "auto_capture": True,
                "embedding_model": embedding_model,
                "preprocessing": False,
            },
            ok_statuses={201},
        )
        return response.json()

    def delete_memory_base(self, memory_base_id: str) -> None:
        self.request("DELETE", f"/api/v1/memories/{memory_base_id}", ok_statuses={200, 204, 404})

    def upload_user_file(self, *, filename: str, content: bytes, content_type: str = "text/plain") -> dict[str, Any]:
        response = self.request(
            "POST",
            "/api/v2/files/",
            params={"ephemeral": "false"},
            files={"file": (filename, content, content_type)},
            ok_statuses={201},
        )
        return response.json()

    def delete_user_file(self, file_id: str) -> None:
        self.request("DELETE", f"/api/v2/files/{file_id}", ok_statuses={200, 204, 404})

    def create_user(self, username: str, password: str) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/api/v1/users/",
            json={"username": username, "password": password},
            ok_statuses={201, 400},
        )
        if response.status_code == 400:
            # Username may already exist from a prior apply — caller can look up.
            return {"username": username, "already_exists": True, "body": response.json()}
        return response.json()

    def list_users(self, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            "/api/v1/users/",
            params={"skip": skip, "limit": limit},
            ok_statuses={200},
        )
        data = response.json()
        if isinstance(data, dict) and "users" in data:
            return list(data["users"])
        if isinstance(data, list):
            return data
        return []

    def patch_user(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.request(
            "PATCH",
            f"/api/v1/users/{user_id}",
            json=payload,
            ok_statuses={200},
        )
        return response.json()

    def delete_user(self, user_id: str) -> None:
        self.request("DELETE", f"/api/v1/users/{user_id}", ok_statuses={200, 204, 404})
