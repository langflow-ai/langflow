"""GroundRoute Search: Langflow custom component (Phase 1, paste-able).

Self-contained: paste into Langflow as a custom component (no GroundRoute SDK, just httpx + the
Langflow component framework). Structured to drop into
`src/lfx/src/lfx/components/groundroute/groundroute_search.py` for the later bundle PR (Phase 2).

Mirrors the framework conventions of `lfx/components/tavily/tavily_search.py` (verified against
langflow `main`, 2026-06-20): Component base, lfx.inputs.inputs types, Data / DataFrame outputs,
lfx.template.field.base.Output, lfx.log.logger.

The /v1/search request + response mapping below replicates the GroundRoute MCP server's `_to_result`
(it cannot be imported across repos) and matches the live contract confirmed against the gateway
SearchResponse / SearchResult schema:
  results[] = {url, title, snippet, content, source_engine, published_at}
  top-level  = answer (optional), citations (optional)
  meta       = {request_id, cache_tier, degraded, cost_usd}
"""

from __future__ import annotations

from typing import Any

import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    DropdownInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

_BASE_URL = "https://api.groundroute.ai"
_MODES = ["auto", "web", "news", "academic", "answer", "page"]
_FRESHNESS = ["", "fresh", "semi", "static"]
_TIMEOUT_S = 30.0
_HTTP_OK = 200


class GroundRouteSearchComponent(Component):
    display_name = "GroundRoute Search"
    description = (
        "One API across 6 search engines (Serper, Brave, Exa, Tavily, Firecrawl, Perplexity). "
        "Routes each query to the cheapest engine that clears a quality bar and caches repeats, "
        "so you pay no more than going direct."
    )
    documentation = "https://groundroute.ai/docs"
    # Core bundle: the real GroundRoute glyph is registered in the frontend (icons/GroundRoute/ +
    # lazyIconImports + SIDEBAR_BUNDLES), so the bundle references it by name. Do NOT rename.
    icon = "GroundRoute"
    name = "GroundRouteSearch"  # stable contract: never rename (Langflow docs); renaming breaks flows

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="GroundRoute API Key",
            required=True,
            info="Get a free key, $10 credit, no card, at https://groundroute.ai/keys",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="What to search for.",
            tool_mode=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=_MODES,
            value="auto",
            advanced=True,
            info="auto lets GroundRoute classify the query and pick the engine class.",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=10,
            advanced=True,
            info="Number of results to return (clamped to 1-50).",
        ),
        DropdownInput(
            name="freshness",
            display_name="Freshness",
            options=_FRESHNESS,
            value="",
            advanced=True,
            info="Override freshness intent. Blank lets GroundRoute auto-detect.",
        ),
        MessageTextInput(
            name="domains",
            display_name="Include Domains",
            advanced=True,
            info="Comma-separated domains to restrict the search to.",
        ),
        MessageTextInput(
            name="lang",
            display_name="Language",
            advanced=True,
            info="ISO 639-1 language code, e.g. en.",
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            advanced=True,
            info="ISO 3166-1 alpha-2 country code, e.g. us.",
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="search_data"),
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    # ── request / response mapping ─────────────────────────────────────────────
    def _build_payload(self) -> dict[str, Any]:
        try:
            max_results = int(self.max_results or 10)
        except (TypeError, ValueError):
            max_results = 10
        max_results = max(1, min(max_results, 50))  # clamp 1-50

        body: dict[str, Any] = {"query": (self.query or "").strip(), "max_results": max_results}
        if self.mode and self.mode != "auto":
            body["mode"] = self.mode
        if getattr(self, "freshness", ""):
            body["freshness"] = self.freshness
        domains = getattr(self, "domains", "") or ""
        parsed = [d.strip() for d in domains.split(",") if d.strip()]
        if parsed:
            body["domains"] = parsed
        if getattr(self, "lang", ""):
            body["lang"] = self.lang
        if getattr(self, "country", ""):
            body["country"] = self.country
        return body

    @staticmethod
    def _to_records(resp: dict[str, Any]) -> list[dict[str, Any]]:
        """Replicates GroundRoute MCP `_to_result`: SearchResult -> a flat record per result."""
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "content": r.get("content"),
                "source_engine": r.get("source_engine", ""),
                "published_at": r.get("published_at"),
            }
            for r in resp.get("results", []) or []
        ]

    @staticmethod
    def _meta(resp: dict[str, Any]) -> dict[str, Any]:
        cache_meta = resp.get("cache_meta") or {}
        usage_meta = resp.get("usage_meta") or {}
        # cost_usd is read from usage_meta (the metering surface that becomes the usage_event row).
        # This is the canonical field and matches the shipped MCP server.py _to_result. In the live
        # contract usage_meta.cost_usd == routing_meta.cost_usd (same value set by the orchestrator).
        return {
            "request_id": resp.get("request_id"),
            "cache_tier": cache_meta.get("cache_tier"),
            "degraded": resp.get("degraded", False),
            "cost_usd": usage_meta.get("cost_usd"),
        }

    def _error(self, message: str) -> list[Data]:
        logger.error(message)
        self.status = message
        return [Data(data={"error": message})]

    # ── outputs ─────────────────────────────────────────────────────────────
    def search_data(self) -> list[Data]:
        """Call GroundRoute /v1/search and return one Data per result (plus an answer record).

        Never raises: a missing key or non-200 returns a single Data carrying an `error` string so
        the flow degrades gracefully instead of crashing.
        """
        if not self.api_key:
            return self._error("GroundRoute API key is required. Get one at https://groundroute.ai/keys")
        if not (self.query or "").strip():
            return self._error("GroundRoute search query is required.")

        try:
            response = httpx.post(
                f"{_BASE_URL}/v1/search",
                json=self._build_payload(),
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            return self._error(f"GroundRoute request failed: {exc}")

        if response.status_code != _HTTP_OK:
            return self._error(f"GroundRoute returned HTTP {response.status_code}: {response.text[:300]}")

        try:
            resp: dict[str, Any] = response.json()
        except ValueError as exc:
            return self._error(f"GroundRoute returned a non-JSON body: {exc}")

        records = self._to_records(resp)
        meta = self._meta(resp)
        data_list = [Data(data=rec) for rec in records]

        # answer-engine results carry a synthesized answer + citations, surfaced as a lead record
        if resp.get("answer"):
            data_list.insert(
                0,
                Data(
                    data={
                        "answer": resp["answer"],
                        "citations": resp.get("citations", []),
                        **meta,
                    }
                ),
            )

        engines = sorted({rec["source_engine"] for rec in records if rec.get("source_engine")})
        suffix = " (degraded)" if meta["degraded"] else ""
        self.status = f"{len(records)} results via {', '.join(engines) or 'cache'}{suffix}"
        return data_list or [Data(data={"warning": "no results", **meta})]

    def search_dataframe(self) -> DataFrame:
        """Same call as `search_data`, returned as a DataFrame (one row per result)."""
        return DataFrame(self.search_data())
