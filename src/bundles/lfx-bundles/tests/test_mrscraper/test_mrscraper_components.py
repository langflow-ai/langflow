"""Unit tests for MrScraper LFX components with mocked SDK calls."""

from __future__ import annotations

import builtins
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx_bundles.mrscraper.mrscraper_ai_scraper import MrscraperAiScraper
from lfx_bundles.mrscraper.mrscraper_batch_scrape import MrscraperBatchScrape
from lfx_bundles.mrscraper.mrscraper_crawl_website import MrscraperCrawlWebsite
from lfx_bundles.mrscraper.mrscraper_fetch_html import MrscraperFetchHtml
from lfx_bundles.mrscraper.mrscraper_get_result import MrscraperGetResult
from lfx_bundles.mrscraper.mrscraper_get_results import MrscraperGetResults
from lfx_bundles.mrscraper.mrscraper_run_ai_scraper import MrscraperRunAiScraper
from lfx_bundles.mrscraper.mrscraper_run_manual_scraper import MrscraperRunManualScraper

# Placeholder token for SDK mocks (not a real credential).
MOCK_MR_API_TOKEN = "test-mrscraper-sdk-token-placeholder"  # noqa: S105


def envelope(data: Any) -> dict[str, Any]:
    """Wrap a payload the way ``MrScraper._parse`` wraps every real response."""
    return {"status_code": 200, "data": data, "headers": {"content-type": "application/json"}}


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component_class", "method_name"),
    [
        (MrscraperAiScraper, "run_scraper"),
        (MrscraperBatchScrape, "batch_scrape"),
        (MrscraperCrawlWebsite, "crawl"),
        (MrscraperFetchHtml, "fetch"),
        (MrscraperGetResult, "get_result"),
        (MrscraperGetResults, "fetch_all_results"),
        (MrscraperRunAiScraper, "rerun"),
        (MrscraperRunManualScraper, "rerun_manual"),
    ],
)
async def test_missing_sdk_error(component_class: type, method_name: str) -> None:
    """Every component explains how to install the optional SDK."""
    original_import = builtins.__import__

    def import_without_mrscraper(name: str, *args, **kwargs):
        if name == "mrscraper":
            msg = "No module named 'mrscraper'"
            raise ImportError(msg)
        return original_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=import_without_mrscraper),
        pytest.raises(ImportError, match="pip install mrscraper-sdk"),
    ):
        await getattr(component_class(), method_name)()


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
        mock_client.create_scraper = AsyncMock(return_value=envelope({"ok": True, "id": "run-1"}))

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

    @pytest.mark.asyncio
    async def test_run_scraper_omits_empty_proxy_country(self) -> None:
        """An empty proxy country is sent as ``None``, not the string ``"None"``."""
        mock_client = MagicMock()
        mock_client.create_scraper = AsyncMock(return_value=envelope({"ok": True}))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperAiScraper()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                url="https://example.com/page",
                message="Extract titles",
                agent="general",
                proxy_country="",
            )
            await c.run_scraper()

        assert mock_client.create_scraper.call_args.kwargs["proxy_country"] is None


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
        mock_client.bulk_rerun_ai_scraper = AsyncMock(return_value=envelope({"batch": 1}))
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
        mock_client.bulk_rerun_manual_scraper = AsyncMock(return_value=envelope({"batch": 2}))
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

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self) -> None:
        """Unsupported modes fail before either bulk API is called."""
        mock_client = MagicMock()
        mock_client.bulk_rerun_ai_scraper = AsyncMock()
        mock_client.bulk_rerun_manual_scraper = AsyncMock()

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperBatchScrape()
            c.set(
                api_token=MOCK_MR_API_TOKEN,
                scraper_id="sid",
                urls="https://example.com",
                mode="unsupported",
            )
            with pytest.raises(ValueError, match=r"unsupported.*sid"):
                await c.batch_scrape()

        mock_client.bulk_rerun_ai_scraper.assert_not_called()
        mock_client.bulk_rerun_manual_scraper.assert_not_called()


@pytest.mark.unit
class TestMrscraperCrawlWebsite:
    """Tests for `MrscraperCrawlWebsite`."""

    @pytest.mark.asyncio
    async def test_max_depth_zero_preserved(self) -> None:
        """`max_depth=0` must be passed through (not coerced to default 2)."""
        mock_client = MagicMock()
        mock_client.create_scraper = AsyncMock(return_value=envelope({"crawl": True}))

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
        mock_client.fetch_html = AsyncMock(return_value=envelope("<html></html>"))

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
        mock_client.get_result_by_id = AsyncMock(return_value={"status_code": 200, "data": {"id": "r1"}, "headers": {}})

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperGetResult()
            c.set(api_token=MOCK_MR_API_TOKEN, result_id="r1")
            out = await c.get_result()

        assert out.data == {"id": "r1"}
        mock_client.get_result_by_id.assert_awaited_once_with(result_id="r1")


@pytest.mark.unit
class TestMrscraperGetResults:
    """Tests for `MrscraperGetResults`."""

    @pytest.mark.asyncio
    async def test_get_all_results_passes_filters(self) -> None:
        """Pagination and sort params are forwarded to `get_all_results`."""
        mock_client = MagicMock()
        mock_client.get_all_results = AsyncMock(return_value=envelope({"rows": []}))

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
        mock_client.rerun_scraper = AsyncMock(return_value=envelope({"ok": True}))

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
        mock_client.rerun_manual_scraper = AsyncMock(return_value=envelope({"status": "done"}))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperRunManualScraper()
            c.set(api_token=MOCK_MR_API_TOKEN, scraper_id="mid", url="https://example.com/x")
            out = await c.rerun_manual()

        assert out.data["status"] == "done"
        mock_client.rerun_manual_scraper.assert_awaited_once_with(
            scraper_id="mid",
            url="https://example.com/x",
        )


@pytest.mark.unit
class TestResponseHandling:
    """The SDK envelope is stripped consistently across every component."""

    @pytest.mark.asyncio
    async def test_envelope_is_not_surfaced_to_flows(self) -> None:
        """Transport metadata stays out of the component output."""
        mock_client = MagicMock()
        mock_client.rerun_manual_scraper = AsyncMock(return_value=envelope({"status": "done"}))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperRunManualScraper()
            c.set(api_token=MOCK_MR_API_TOKEN, scraper_id="mid", url="https://example.com/x")
            out = await c.rerun_manual()

        assert out.data == {"status": "done"}
        assert "status_code" not in out.data
        assert "headers" not in out.data

    @pytest.mark.asyncio
    async def test_non_json_html_is_boxed(self) -> None:
        """`fetch_html` returns text for non-JSON pages; it is boxed under `html`."""
        mock_client = MagicMock()
        mock_client.fetch_html = AsyncMock(return_value=envelope("<html>plain</html>"))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperFetchHtml()
            c.set(api_token=MOCK_MR_API_TOKEN, url="https://example.com/")
            out = await c.fetch()

        assert out.data == {"html": "<html>plain</html>"}

    @pytest.mark.asyncio
    async def test_get_results_dataframe_rows(self) -> None:
        """The tabular output yields one row per result, not one row per page."""
        rows = [{"id": "r1", "status": "done"}, {"id": "r2", "status": "failed"}]
        mock_client = MagicMock()
        mock_client.get_all_results = AsyncMock(return_value=envelope({"results": rows, "page": 1, "total": 2}))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperGetResults()
            c.set(api_token=MOCK_MR_API_TOKEN)
            frame = await c.fetch_all_results_as_dataframe()

        assert len(frame) == 2
        assert list(frame["id"]) == ["r1", "r2"]

    @pytest.mark.asyncio
    async def test_get_results_dataframe_survives_key_rename(self) -> None:
        """A payload with no row list degrades to a single row instead of raising."""
        mock_client = MagicMock()
        mock_client.get_all_results = AsyncMock(return_value=envelope({"page": 1, "total": 0}))

        with patch("mrscraper.MrScraper", return_value=mock_client):
            c = MrscraperGetResults()
            c.set(api_token=MOCK_MR_API_TOKEN)
            frame = await c.fetch_all_results_as_dataframe()

        assert len(frame) == 1


@pytest.mark.unit
class TestSdkContract:
    """Component call sites are checked against the installed SDK, not a mock.

    Every other test in this file patches `mrscraper.MrScraper`, so a signature
    change in the SDK would leave them green while the components broke at
    runtime. These assert against the real package; they skip only in a minimal
    env where `conftest` had to register a stub.
    """

    @staticmethod
    def _real_sdk():
        import mrscraper

        if getattr(mrscraper, "__lfx_test_stub__", False):
            pytest.skip("mrscraper-sdk is not installed; conftest registered a stub")
        return mrscraper

    def test_client_accepts_token_kwarg(self) -> None:
        """Components construct the client as `MrScraper(token=...)`."""
        mrscraper = self._real_sdk()
        assert "token" in inspect.signature(mrscraper.MrScraper).parameters

    @pytest.mark.parametrize(
        ("method_name", "call_site_kwargs"),
        [
            (
                "create_scraper",
                {
                    "url",
                    "message",
                    "agent",
                    "proxy_country",
                    "max_depth",
                    "max_pages",
                    "limit",
                    "include_patterns",
                    "exclude_patterns",
                },
            ),
            (
                "rerun_scraper",
                {"scraper_id", "url", "max_depth", "max_pages", "limit", "include_patterns", "exclude_patterns"},
            ),
            ("rerun_manual_scraper", {"scraper_id", "url"}),
            ("bulk_rerun_ai_scraper", {"scraper_id", "urls"}),
            ("bulk_rerun_manual_scraper", {"scraper_id", "urls"}),
            ("fetch_html", {"url", "timeout", "geo_code", "block_resources"}),
            (
                "get_all_results",
                {"sort_field", "sort_order", "page_size", "page", "search", "date_range_column", "start_at", "end_at"},
            ),
            ("get_result_by_id", {"result_id"}),
        ],
    )
    def test_call_site_kwargs_still_accepted(self, method_name: str, call_site_kwargs: set[str]) -> None:
        """Each keyword a component passes is still a parameter of the SDK method."""
        mrscraper = self._real_sdk()
        method = getattr(mrscraper.MrScraper, method_name, None)
        assert method is not None, f"MrScraper.{method_name} no longer exists"
        accepted = set(inspect.signature(method).parameters) - {"self"}
        dropped = call_site_kwargs - accepted
        assert not dropped, f"MrScraper.{method_name} no longer accepts {sorted(dropped)}"
