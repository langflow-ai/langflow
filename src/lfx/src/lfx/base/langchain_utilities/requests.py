"""LangChain request wrappers that honor the administrator's outbound request policy."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_community.utilities.requests import TextRequestsWrapper

from lfx.utils.ssrf_requests import ssrf_safe_request

DEFAULT_REQUEST_TIMEOUT = 30.0


class SSRFSafeTextRequestsWrapper(TextRequestsWrapper):
    """Use the same protected transport for synchronous and asynchronous tool calls."""

    def _request(self, method: str, url: str, **kwargs: Any) -> str | dict[str, Any]:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = DEFAULT_REQUEST_TIMEOUT
        response = ssrf_safe_request(method, url, headers=self.headers, auth=self.auth, verify=self.verify, **kwargs)
        return self._get_resp_content(response)

    def get(self, url: str, **kwargs: Any) -> str | dict[str, Any]:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return self._request("POST", url, json=data, **kwargs)

    def patch(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return self._request("PATCH", url, json=data, **kwargs)

    def put(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return self._request("PUT", url, json=data, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> str | dict[str, Any]:
        return self._request("DELETE", url, **kwargs)

    async def aget(self, url: str, **kwargs: Any) -> str | dict[str, Any]:
        return await asyncio.to_thread(self.get, url, **kwargs)

    async def apost(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return await asyncio.to_thread(self.post, url, data, **kwargs)

    async def apatch(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return await asyncio.to_thread(self.patch, url, data, **kwargs)

    async def aput(self, url: str, data: dict[str, Any], **kwargs: Any) -> str | dict[str, Any]:
        return await asyncio.to_thread(self.put, url, data, **kwargs)

    async def adelete(self, url: str, **kwargs: Any) -> str | dict[str, Any]:
        return await asyncio.to_thread(self.delete, url, **kwargs)
