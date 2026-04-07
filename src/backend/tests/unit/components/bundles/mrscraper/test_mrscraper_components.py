"""Unit tests for MrScraper LFX components with mocked SDK calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.mrscraper.mrscraper_ai_scraper import MrscraperAiScraper
from lfx.components.mrscraper.mrscraper_batch_scrape import MrscraperBatchScrape
from lfx.components.mrscraper.mrscraper_crawl_website import MrscraperCrawlWebsite
from lfx.components.mrscraper.mrscraper_fetch_html import MrscraperFetchHtml
from lfx.components.mrscraper.mrscraper_get_result import MrscraperGetResult
from lfx.components.mrscraper.mrscraper_get_results import MrscraperGetResults
from lfx.components.mrscraper.mrscraper_run_ai_scraper import MrscraperRunAiScraper
from lfx.components.mrscraper.mrscraper_run_manual_scraper import MrscraperRunManualScraper

# Placeholder token for SDK mocks (not a real credential).
MOCK_MR_API_TOKEN = "test-mrscraper-sdk-token-placeholder"  # noqa: S105


@pytest.mark.unit
class TestMrscraperAiScraper:
    """Tests for `MrscraperAiScraper`."""

    def test_metadata(self) -> None:
        """Component exposes display name, icon, and documentation."""
        c = MrscraperAiScraper()
        assert c.display_name == "MrScraper AI Agent Scraper"
        assert c.icon == "MrScraper"
        assert "docs.mrscraper.com" in c.documentation

    @pytest.mark.asyncio
    async def test_run_scraper_calls_sdk(self) -> None:
        """`create_scraper` runs with expected arguments and returns Data."""
        mock_client = MagicMock()
        mock_client.create_scraper = AsyncMock(return_value={"ok": True, "id": "run-1"})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperAiScraper()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                url="https://example.com/page",
                message="Extract titles",
                agent="general",
                proxy_country="us",
            )
            out = await c.run_scraper()

        assert out.data == {"ok": True, "id": "run-1"}
        mock_client.create_scraper.assert_awaited_once()
        kwargs = mock_client.create_scraper.call_args.kwargs
        assert kwargs["url"] == "https://example.com/page"
        assert kwargs["message"] == "Extract titles"
        assert kwargs["agent"] == "general"
        assert kwargs["proxy_country"] == "us"


@pytest.mark.unit
class TestMrscraperBatchScrape:
    """Tests for `MrscraperBatchScrape`."""

    @pytest.mark.asyncio
    async def test_empty_urls_raises(self) -> None:
        """Empty URL string raises ValueError before calling the SDK."""
        with patch("mrscraper.MrScraper"):
            c = MrscraperBatchScrape()
            c.set(api_token=MOCK_MR_API_TOKEN, scraper_id="s1", urls="", mode="AI")
            with pytest.raises(ValueError, match="URLs are required"):
                await c.batch_scrape()

    @pytest.mark.asyncio
    async def test_whitespace_only_urls_raises(self) -> None:
        """Whitespace-only URL list raises ValueError."""
        with patch("mrscraper.MrScraper"):
            c = MrscraperBatchScrape()
            c.set(api_token=MOCK_MR_API_TOKEN, scraper_id="s1", urls="  ,  \n", mode="AI")
            with pytest.raises(ValueError, match="No valid URLs"):
                await c.batch_scrape()

    @pytest.mark.asyncio
    async def test_ai_mode_calls_bulk_ai(self) -> None:
        """Mode AI uses `bulk_rerun_ai_scraper`."""
        mock_client = MagicMock()
        mock_client.bulk_rerun_ai_scraper = AsyncMock(return_value={"batch": 1})
        mock_client.bulk_rerun_manual_scraper = AsyncMock()

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperBatchScrape()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                scraper_id="sid",
                urls="https://a.com,https://b.com",
                mode="AI",
            )
            out = await c.batch_scrape()

        assert out.data == {"batch": 1}
        mock_client.bulk_rerun_ai_scraper.assert_awaited_once()
        mock_client.bulk_rerun_manual_scraper.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_mode_calls_bulk_manual(self) -> None:
        """Mode Manual uses `bulk_rerun_manual_scraper`."""
        mock_client = MagicMock()
        mock_client.bulk_rerun_manual_scraper = AsyncMock(return_value={"batch": 2})
        mock_client.bulk_rerun_ai_scraper = AsyncMock()

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperBatchScrape()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                scraper_id="sid",
                urls="https://a.com",
                mode="Manual",
            )
            out = await c.batch_scrape()

        assert out.data == {"batch": 2}
        mock_client.bulk_rerun_manual_scraper.assert_awaited_once()


@pytest.mark.unit
class TestMrscraperCrawlWebsite:
    """Tests for `MrscraperCrawlWebsite`."""

    @pytest.mark.asyncio
    async def test_max_depth_zero_preserved(self) -> None:
        """`max_depth=0` must be passed through (not coerced to default 2)."""
        mock_client = MagicMock()
        mock_client.create_scraper = AsyncMock(return_value={"crawl": True})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperCrawlWebsite()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                url="https://example.com/",
                max_depth=0,
                max_pages=10,
                limit=100,
                include_patterns="",
                exclude_patterns="",
            )
            await c.crawl()

        kwargs = mock_client.create_scraper.call_args.kwargs
        assert kwargs["max_depth"] == 0
        assert kwargs["agent"] == "map"
        assert kwargs["message"] == ""


@pytest.mark.unit
class TestMrscraperFetchHtml:
    """Tests for `MrscraperFetchHtml`."""

    @pytest.mark.asyncio
    async def test_fetch_html_calls_sdk(self) -> None:
        """`fetch_html` receives timeout and geo settings."""
        mock_client = MagicMock()
        mock_client.fetch_html = AsyncMock(return_value={"html": "<html></html>"})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperFetchHtml()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                url="https://example.com/",
                timeout=60,
                geo_code="GB",
                block_resources=True,
            )
            out = await c.fetch()

        assert out.data["html"] == "<html></html>"
        kwargs = mock_client.fetch_html.call_args.kwargs
        assert kwargs["timeout"] == 60
        assert kwargs["geo_code"] == "GB"
        assert kwargs["block_resources"] is True


@pytest.mark.unit
class TestMrscraperGetResult:
    """Tests for `MrscraperGetResult`."""

    @pytest.mark.asyncio
    async def test_get_result_by_id(self) -> None:
        """Maps `result_id` to SDK `get_result_by_id`."""
        mock_client = MagicMock()
        mock_client.get_result_by_id = AsyncMock(return_value={"id": "r1"})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperGetResult()
            c.set(api_token=MOCK_MR_API_TOKEN, result_id="r1")
            out = await c.get_result()

        assert out.data["id"] == "r1"
        mock_client.get_result_by_id.assert_awaited_once_with(result_id="r1")


@pytest.mark.unit
class TestMrscraperGetResults:
    """Tests for `MrscraperGetResults`."""

    @pytest.mark.asyncio
    async def test_get_all_results_passes_filters(self) -> None:
        """Pagination and sort params are forwarded to `get_all_results`."""
        mock_client = MagicMock()
        mock_client.get_all_results = AsyncMock(return_value={"rows": []})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperGetResults()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                sort_field="createdAt",
                sort_order="ASC",
                page_size=25,
                page=2,
                search="error",
                date_range_column="updatedAt",
                start_at="2024-01-01",
                end_at="2024-12-31",
            )
            await c.fetch_all_results()

        kwargs = mock_client.get_all_results.call_args.kwargs
        assert kwargs["sort_field"] == "createdAt"
        assert kwargs["page"] == 2
        assert kwargs["search"] == "error"


@pytest.mark.unit
class TestMrscraperRunAiScraper:
    """Tests for `MrscraperRunAiScraper`."""

    @pytest.mark.asyncio
    async def test_rerun_preserves_zero_depth(self) -> None:
        """`max_depth=0` is forwarded to `rerun_scraper`."""
        mock_client = MagicMock()
        mock_client.rerun_scraper = AsyncMock(return_value={"ok": True})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperRunAiScraper()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                scraper_id="sid",
                url="https://example.com/page",
                max_depth=0,
                max_pages=5,
                limit=50,
                include_patterns="",
                exclude_patterns="",
            )
            await c.rerun()

        kwargs = mock_client.rerun_scraper.call_args.kwargs
        assert kwargs["max_depth"] == 0


@pytest.mark.unit
class TestMrscraperRunManualScraper:
    """Tests for `MrscraperRunManualScraper`."""

    @pytest.mark.asyncio
    async def test_rerun_manual_calls_sdk(self) -> None:
        """Delegates to `rerun_manual_scraper`."""
        mock_client = MagicMock()
        mock_client.rerun_manual_scraper = AsyncMock(return_value={"status": "done"})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperRunManualScraper()
            c.set(api_token=MOCK_MR_API_TOKEN, scraper_id="mid", url="https://example.com/x")
            out = await c.rerun_manual()

        assert out.data["status"] == "done"
        mock_client.rerun_manual_scraper.assert_awaited_once_with(
            scraper_id="mid",
            url="https://example.com/x",
        )
