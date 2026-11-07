"""Opt-in Parallel web search through the official MCP endpoint."""

import asyncio
import json
import sys
from typing import TYPE_CHECKING

import httpx
from anyio import fail_after
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

if TYPE_CHECKING:
    from mcp.types import CallToolResult

MCP_URL = "https://mcp.parallel.ai/mcp"
USER_AGENT = "langflow/parallel-search"
MAX_RESULTS = 20


class ParallelSearchComponent(Component):
    display_name = "Parallel Search"
    description = "Search the web with Parallel and return source URLs and relevant passages. No API key required."
    documentation = "https://docs.langflow.org/bundles-parallel"
    icon = "Parallel"
    name = "ParallelSearch"

    inputs = [
        MessageTextInput(name="query", display_name="Search Query", required=True, tool_mode=True),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=5,
            info="Maximum rows returned (1-20). This is a local output limit, not a server search setting.",
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Parallel API Key",
            required=False,
            advanced=True,
            info="Optional Bearer token for higher limits. An invalid key fails without retrying anonymously.",
        ),
        BoolInput(
            name="enabled",
            display_name="Enabled",
            value=True,
            advanced=True,
            info="Disable to return an empty table without making network requests.",
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fetch_content_dataframe")]

    @staticmethod
    def _result_data(result: "CallToolResult", limit: int) -> list[Data]:
        """Validate structured or JSON MCP results and limit source rows with joined excerpts."""
        if result.isError:
            msg = "Parallel search failed. Check your credentials, rate limits, and query."
            raise ValueError(msg)
        payload = result.structuredContent
        if payload is None:
            for block in result.content:
                if block.type == "text":
                    try:
                        payload = json.loads(block.text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict) and "results" in payload:
                        break
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            msg = "Parallel returned an invalid search response."
            raise ValueError(msg)  # noqa: TRY004 - malformed remote data is a value error
        rows = []
        for item in payload["results"][:limit]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("url"), str)
                or not item["url"].startswith(("https://", "http://"))
                or not isinstance(item.get("excerpts"), list)
                or not all(isinstance(passage, str) for passage in item["excerpts"])
            ):
                msg = "Parallel returned an invalid source or passages."
                raise ValueError(msg)
            content = "\n\n".join(item["excerpts"])
            rows.append(
                Data(
                    text=content,
                    data={
                        "title": item.get("title"),
                        "url": item["url"],
                        "content": content,
                        "excerpts": item["excerpts"],
                    },
                )
            )
        return rows

    async def fetch_content(self) -> list[Data]:
        """Search through the fixed MCP endpoint with a deadline and sanitized HTTP errors."""
        if not self.enabled:
            return []
        query = self.query.strip()
        if not query:
            msg = "Enter a non-empty Search Query."
            raise ValueError(msg)
        if not 1 <= self.max_results <= MAX_RESULTS:
            msg = "Max Results must be between 1 and 20."
            raise ValueError(msg)
        headers = {"User-Agent": USER_AGENT}
        if self.api_key:
            # Use exactly the supplied credential; never downgrade to anonymous on error.
            headers["Authorization"] = f"Bearer {self.api_key}"
        _, kwargs = await asyncio.to_thread(ssrf_protected_strict_httpx_client_kwargs_for_url, MCP_URL)
        # The fixed endpoint never redirects. Keep redirects disabled even when SSRF checks are off.
        kwargs["follow_redirects"] = False
        with fail_after(90):
            try:
                async with (
                    httpx.AsyncClient(headers=headers, timeout=90, max_redirects=0, **kwargs) as http,
                    streamable_http_client(MCP_URL, http_client=http) as (read, write, _),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    tools = await session.list_tools()
                    if not any(tool.name == "web_search" for tool in tools.tools):
                        msg = "Parallel MCP does not expose web_search."
                        raise ValueError(msg)
                    result = await session.call_tool(
                        "web_search",
                        {"objective": query, "search_queries": [query]},
                    )
            except Exception as exc:
                # AnyIO task groups wrap HTTP failures. Only unwrap a single cause so
                # cancellation, timeouts and unrelated/multiple failures stay intact.
                error = exc
                while isinstance(error, ExceptionGroup) and len(error.exceptions) == 1:
                    error = error.exceptions[0]
                if not isinstance(error, httpx.HTTPStatusError):
                    raise
                status = error.response.status_code
                if error.response.is_redirect:
                    msg = f"Parallel MCP refused a redirect (HTTP {status})."
                else:
                    msg = f"Parallel MCP request failed (HTTP {status})."
                # Never expose a response body, request URL, redirect target or credential.
                raise ValueError(msg) from None
        rows = self._result_data(result, self.max_results)
        self.status = rows
        return rows

    async def fetch_content_dataframe(self) -> DataFrame:
        return DataFrame(await self.fetch_content())
