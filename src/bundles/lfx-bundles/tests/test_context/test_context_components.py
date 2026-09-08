from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from lfx_bundles.context import (
    ContextCrawlWebsiteComponent,
    ContextExtractStructuredDataComponent,
    ContextRetrieveBrandComponent,
    ContextScrapeMarkdownComponent,
    ContextSearchNewsComponent,
    ContextSearchWebComponent,
)

TEST_API_KEY = "test-context-api-key"


@pytest.mark.unit
class TestContextSearchWebComponent:
    async def test_search_uses_public_web_search_api(self) -> None:
        response = {"results": [{"url": "https://example.com"}]}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_search.request_context", request):
            component = ContextSearchWebComponent().set(
                api_key=TEST_API_KEY,
                query="latest agent frameworks",
                num_results=10,
                include_domains="example.com, docs.example.com",
                exclude_domains="spam.example",
                freshness="last_week",
                include_markdown=True,
                use_main_content_only=True,
            )
            result = await component.search()

        assert result.data == response
        request.assert_awaited_once_with(
            "POST",
            "/web/search",
            TEST_API_KEY,
            json={
                "query": "latest agent frameworks",
                "numResults": 10,
                "includeDomains": ["example.com", "docs.example.com"],
                "excludeDomains": ["spam.example"],
                "freshness": "last_week",
                "markdownOptions": {"enabled": True, "useMainContentOnly": True},
            },
        )


@pytest.mark.unit
class TestContextSearchNewsComponent:
    async def test_news_search_uses_company_news_api(self) -> None:
        response = {"data": [{"title": "Context launches a new API"}]}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_news.request_context", request):
            component = ContextSearchNewsComponent().set(
                api_key=TEST_API_KEY,
                identifier_type="domain",
                identifier="context.dev",
                sort_by="newest",
                limit=10,
            )
            result = await component.search_news()

        assert result.data == response
        request.assert_awaited_once_with(
            "POST",
            "/news/search",
            TEST_API_KEY,
            json={
                "searchBy": {
                    "type": "entity",
                    "entity": {"type": "domain", "domain": "context.dev"},
                },
                "sortBy": {"type": "newest"},
                "limit": 10,
            },
        )


@pytest.mark.unit
class TestContextScrapeMarkdownComponent:
    async def test_scrape_supports_youtube_urls(self) -> None:
        response = {"markdown": "[0:00] Transcript", "url": "https://youtu.be/demo"}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_scrape.request_context", request):
            component = ContextScrapeMarkdownComponent().set(
                api_key=TEST_API_KEY,
                url="https://youtu.be/demo",
                use_main_content_only=True,
                include_links=True,
                include_images=False,
                max_age_ms=86_400_000,
            )
            result = await component.scrape()

        assert result.text == "[0:00] Transcript"
        request.assert_awaited_once_with(
            "GET",
            "/web/scrape/markdown",
            TEST_API_KEY,
            params={
                "url": "https://youtu.be/demo",
                "useMainContentOnly": True,
                "includeLinks": True,
                "includeImages": False,
                "maxAgeMs": 86_400_000,
            },
        )


@pytest.mark.unit
class TestContextCrawlWebsiteComponent:
    async def test_crawl_preserves_zero_depth(self) -> None:
        response = {"results": []}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_crawl.request_context", request):
            component = ContextCrawlWebsiteComponent().set(
                api_key=TEST_API_KEY,
                url="https://example.com",
                max_pages=5,
                max_depth=0,
                use_main_content_only=True,
                follow_subdomains=False,
            )
            result = await component.crawl()

        assert result.data == response
        request.assert_awaited_once_with(
            "POST",
            "/web/crawl",
            TEST_API_KEY,
            json={
                "url": "https://example.com",
                "maxPages": 5,
                "maxDepth": 0,
                "useMainContentOnly": True,
                "followSubdomains": False,
            },
        )


@pytest.mark.unit
class TestContextExtractStructuredDataComponent:
    async def test_extract_sends_json_schema(self) -> None:
        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        response = {"status": "ok", "data": {"title": "Example"}}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_extract.request_context", request):
            component = ContextExtractStructuredDataComponent().set(
                api_key=TEST_API_KEY,
                url="https://example.com",
                schema=schema,
                instructions="Extract the page title.",
                fact_check=True,
                max_pages=1,
            )
            result = await component.extract()

        assert result.data == response
        request.assert_awaited_once_with(
            "POST",
            "/web/extract",
            TEST_API_KEY,
            json={
                "url": "https://example.com",
                "schema": schema,
                "instructions": "Extract the page title.",
                "factCheck": True,
                "maxPages": 1,
            },
        )


@pytest.mark.unit
class TestContextRetrieveBrandComponent:
    async def test_retrieve_brand_uses_selected_identifier(self) -> None:
        response = {"brand": {"domain": "context.dev"}}
        request = AsyncMock(return_value=response)

        with patch("lfx_bundles.context.context_retrieve_brand.request_context", request):
            component = ContextRetrieveBrandComponent().set(
                api_key=TEST_API_KEY,
                identifier_type="domain",
                identifier="context.dev",
                max_speed=False,
            )
            result = await component.retrieve_brand()

        assert result.data == response
        request.assert_awaited_once_with(
            "GET",
            "/brand/retrieve",
            TEST_API_KEY,
            params={"domain": "context.dev", "maxSpeed": False},
        )
