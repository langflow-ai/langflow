from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Self, cast

import httpx

if TYPE_CHECKING:
    from .types import McpJsonRpcResponse, McpTool, MergeRegisteredUser, MergeToolPack

BASE_URL = "https://ah-api.merge.dev/api/v1"


class MergeAgentHandlerClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            msg = "An API key is required"
            raise ValueError(msg)

        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_tool_packs(self) -> list[MergeToolPack]:
        pages = self._fetch_all_pages("/tool-packs/")
        return [cast("MergeToolPack", item) for item in pages if isinstance(item, dict)]

    def get_registered_users(self, *, is_test: bool | None = None) -> list[MergeRegisteredUser]:
        params: dict[str, str] = {}
        if is_test is not None:
            params["is_test"] = str(is_test).lower()

        pages = self._fetch_all_pages("/registered-users", params=params)
        return [cast("MergeRegisteredUser", item) for item in pages if isinstance(item, dict)]

    def list_mcp_tools(self, tool_pack_id: str, user_id: str) -> list[McpTool]:
        mcp_path = f"/tool-packs/{tool_pack_id}/registered-users/{user_id}/mcp"

        rpc_request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        response = cast(
            "McpJsonRpcResponse",
            self._request(
                "POST",
                mcp_path,
                json_body=rpc_request,
                headers=self._mcp_headers(),
            ),
        )

        error = response.get("error")
        if error:
            code = error.get("code", "unknown")
            message = error.get("message", "Unknown MCP error")
            error_message = f"MCP tools/list failed ({code}): {message}"
            raise RuntimeError(error_message)

        result = response.get("result") or {}
        tools = result.get("tools") or []
        return [cast("McpTool", tool) for tool in tools if isinstance(tool, dict)]

    def call_mcp_tool(
        self,
        tool_pack_id: str,
        user_id: str,
        name: str,
        args: dict[str, Any],
    ) -> str:
        mcp_path = f"/tool-packs/{tool_pack_id}/registered-users/{user_id}/mcp"

        rpc_request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": {"input": args},
            },
        }

        try:
            response = cast(
                "McpJsonRpcResponse",
                self._request(
                    "POST",
                    mcp_path,
                    json_body=rpc_request,
                    headers=self._mcp_headers(),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return f'Error calling tool "{name}": {exc}'

        error = response.get("error")
        if error:
            message = error.get("message", "Unknown MCP error")
            return f'Tool "{name}" returned error: {message}'

        result = response.get("result") or {}
        if result.get("isError"):
            content = result.get("content") or []
            text_content = [
                str(entry.get("text", ""))
                for entry in content
                if isinstance(entry, dict) and entry.get("type") == "text"
            ]
            error_text = "\n".join([text for text in text_content if text]).strip() or "Unknown error"
            return f'Tool "{name}" failed: {error_text}'

        content = result.get("content")
        if isinstance(content, list):
            text_content = [
                str(entry.get("text", ""))
                for entry in content
                if isinstance(entry, dict) and entry.get("type") == "text"
            ]
            text_result = "\n".join([text for text in text_content if text]).strip()
            if text_result:
                return text_result

        return json.dumps(result, ensure_ascii=True)

    def _fetch_all_pages(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> list[Any]:
        all_items: list[Any] = []
        page = 1

        while True:
            page_params = dict(params or {})
            page_params["page"] = str(page)
            response = self._request("GET", path, params=page_params)

            if isinstance(response, list):
                return response

            if not isinstance(response, dict):
                msg = f"Unexpected response shape from {path}: {type(response)!r}"
                raise TypeError(msg)

            results = response.get("results") or []
            if not isinstance(results, list):
                msg = f"Unexpected paginated payload from {path}: missing list results"
                raise TypeError(msg)

            all_items.extend(results)

            if not response.get("next"):
                break
            page += 1

        return all_items

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self._client.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
        )
        response.raise_for_status()

        try:
            return response.json()
        except ValueError as exc:
            msg = f"Invalid JSON response from {url}"
            raise RuntimeError(msg) from exc

    @staticmethod
    def _mcp_headers() -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Source": "langflow-bundle",
        }
