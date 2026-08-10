"""Unified Web Search Component.

This component consolidates Web Search, News Search, and RSS Reader into a single
component with tabs for different search modes.
"""

import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pydantic import SecretStr

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, Output, TabInput
from lfx.schema import Data, DataFrame, Message
from lfx.utils.request_utils import get_user_agent
from lfx.utils.ssrf_protection import SSRFProtectionError, is_ssrf_protection_enabled, validate_and_resolve_url
from lfx.utils.ssrf_transport import create_ssrf_protected_sync_client

DEFAULT_MAX_RESULTS = 5
DEFAULT_MAX_CONTENT_LENGTH = 2000
TRUNCATION_SUFFIX = "... [truncated]"
SHORT_TRUNCATION_SUFFIX = "…"
LIMIT_DEFAULTS = {
    "max_results": DEFAULT_MAX_RESULTS,
    "max_content_length": DEFAULT_MAX_CONTENT_LENGTH,
}


class WebSearchComponent(Component):
    display_name = "Web Search"
    description = "Search the web, news, or RSS feeds."
    documentation: str = "https://docs.langflow.org/web-search"
    icon = "search"
    name = "UnifiedWebSearch"

    inputs = [
        TabInput(
            name="search_mode",
            display_name="Search Mode",
            options=["Web", "News", "RSS"],
            info="Choose search mode: Web (DuckDuckGo), News (Google News), or RSS (Feed Reader)",
            value="Web",
            real_time_refresh=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Search keywords for news articles.",
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language (hl)",
            info="Language code, e.g. en-US, fr, de. Default: en-US.",
            tool_mode=False,
            input_types=[],
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country (gl)",
            info="Country code, e.g. US, FR, DE. Default: US.",
            tool_mode=False,
            input_types=[],
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="ceid",
            display_name="Country:Language (ceid)",
            info="e.g. US:en, FR:fr. Default: US:en.",
            tool_mode=False,
            value="US:en",
            input_types=[],
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="topic",
            display_name="Topic",
            info="One of: WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SCIENCE, SPORTS, HEALTH.",
            tool_mode=False,
            input_types=[],
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location (Geo)",
            info="City, state, or country for location-based news. Leave blank for keyword search.",
            tool_mode=False,
            input_types=[],
            required=False,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the request in seconds.",
            value=5,
            required=False,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of results to return. Set to 0 to return every result.",
            value=DEFAULT_MAX_RESULTS,
            required=False,
            advanced=True,
        ),
        IntInput(
            name="max_content_length",
            display_name="Max Content Length",
            info=(
                "Maximum number of characters kept from each scraped page or feed field. "
                "Set to 0 to keep the full text."
            ),
            value=DEFAULT_MAX_CONTENT_LENGTH,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [Output(name="results", display_name="Results", method="perform_search")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update input visibility based on search mode."""
        if field_name == "search_mode":
            # Show/hide inputs based on search mode
            is_news = field_value == "News"
            is_rss = field_value == "RSS"

            # Update query field info based on mode
            if is_rss:
                build_config["query"]["info"] = "RSS feed URL to parse"
                build_config["query"]["display_name"] = "RSS Feed URL"
            elif is_news:
                build_config["query"]["info"] = "Search keywords for news articles."
                build_config["query"]["display_name"] = "Search Query"
            else:  # Web
                build_config["query"]["info"] = "Keywords to search for"
                build_config["query"]["display_name"] = "Search Query"

            # Keep news-specific fields as advanced (matching original News Search component)
            # They remain advanced=True in all modes, just like in the original component

        return build_config

    def validate_url(self, string: str) -> bool:
        """Validate URL format."""
        url_regex = re.compile(
            r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
            re.IGNORECASE,
        )
        return bool(url_regex.match(string))

    def ensure_url(self, url: str) -> str:
        """Ensure URL has proper protocol."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if not self.validate_url(url):
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)
        return url

    def _build_safe_client(self, url: str, validated_ips: list[str]) -> httpx.Client:
        """Create a sync HTTP client with DNS pinning when SSRF protection applies."""
        if is_ssrf_protection_enabled() and validated_ips:
            hostname = urlparse(url).hostname
            if hostname:
                return create_ssrf_protected_sync_client(hostname=hostname, validated_ips=validated_ips)
        return httpx.Client()

    def _safe_get_url(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        """Validate an arbitrary URL and fetch it without following unvalidated redirects."""
        url = self.ensure_url(url)
        try:
            safe_url, validated_ips = validate_and_resolve_url(url)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e

        with self._build_safe_client(safe_url, validated_ips) as client:
            return client.get(safe_url, headers=headers, timeout=self.timeout, follow_redirects=False)

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query."""
        return re.sub(r'[<>"\']', "", query.strip())

    def clean_html(self, html_string: str) -> str:
        """Remove HTML tags from text."""
        return BeautifulSoup(html_string, "html.parser").get_text(separator=" ", strip=True)

    @staticmethod
    def _normalize_limit(raw: Any, default: int) -> int:
        """Normalize a limit so only an explicit zero disables it."""
        if isinstance(raw, Message):
            raw = raw.text
        elif isinstance(raw, Data):
            raw = raw.data.get(raw.text_key, "")
        if raw is None or isinstance(raw, bool) or (isinstance(raw, str) and not raw.strip()):
            return default
        if isinstance(raw, str):
            try:
                limit = int(raw)
            except ValueError:
                try:
                    numeric = float(raw)
                except ValueError:
                    return default
                if not numeric.is_integer():
                    return default
                limit = int(numeric)
        else:
            try:
                limit = int(raw)
            except (TypeError, ValueError, OverflowError):
                return default
            if raw != limit:
                return default
        return default if limit < 0 else limit

    def set_attributes(self, params: dict) -> None:
        """Normalize limits before IntInput validation mutates or rejects them."""
        for name, default in LIMIT_DEFAULTS.items():
            if name in params and not isinstance(params[name], SecretStr):
                params[name] = self._normalize_limit(params[name], default)
        super().set_attributes(params)

    def _get_limit(self, name: str, default: int) -> int | None:
        """Resolve a size limit, returning None only when the user explicitly opted out with zero.

        Flows saved before these inputs existed carry no value at all, so the default has to apply.
        """
        limit = self._normalize_limit(getattr(self, name, None), default)
        return None if limit == 0 else limit

    def _truncate_content(self, content: str, limit: int | None) -> str:
        """Bound a scraped page so a single result cannot flood the caller's context window."""
        if limit is None or len(content) <= limit:
            return content
        if limit < len(TRUNCATION_SUFFIX):
            return content[: limit - len(SHORT_TRUNCATION_SUFFIX)] + SHORT_TRUNCATION_SUFFIX
        if limit == len(TRUNCATION_SUFFIX):
            return TRUNCATION_SUFFIX
        return content[: limit - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX

    def perform_web_search(self) -> DataFrame:
        """Perform DuckDuckGo web search."""
        query = self._sanitize_query(self.query)
        if not query:
            msg = "Empty search query"
            raise ValueError(msg)

        headers = {"User-Agent": get_user_agent()}
        params = {"q": query, "kl": "us-en"}
        url = "https://html.duckduckgo.com/html/"

        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self.status = f"Failed request: {e!s}"
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "snippet": str(e), "content": ""}]))

        if not response.text or "text/html" not in response.headers.get("content-type", "").lower():
            self.status = "No results found"
            return DataFrame(
                pd.DataFrame([{"title": "Error", "link": "", "snippet": "No results found", "content": ""}])
            )

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        max_results = self._get_limit("max_results", DEFAULT_MAX_RESULTS)
        max_content_length = self._get_limit("max_content_length", DEFAULT_MAX_CONTENT_LENGTH)

        for result in soup.select("div.result"):
            if max_results is not None and len(results) >= max_results:
                break
            title_tag = result.select_one("a.result__a")
            snippet_tag = result.select_one("a.result__snippet")
            if title_tag:
                raw_link = title_tag.get("href", "")
                parsed = urlparse(raw_link)
                uddg = parse_qs(parsed.query).get("uddg", [""])[0]
                decoded_link = unquote(uddg) if uddg else raw_link

                try:
                    final_url = self.ensure_url(decoded_link)
                    page = self._safe_get_url(final_url, headers=headers)
                    page.raise_for_status()
                    content = BeautifulSoup(page.text, "lxml").get_text(separator=" ", strip=True)
                except (httpx.HTTPError, ValueError) as e:
                    final_url = decoded_link
                    if "SSRF Protection" in str(e):
                        content = f"(Blocked by SSRF protection: {e!s})"
                    else:
                        content = f"(Failed to fetch: {e!s})"

                results.append(
                    {
                        "title": title_tag.get_text(strip=True),
                        "link": final_url,
                        "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                        "content": self._truncate_content(content, max_content_length),
                    }
                )

        return DataFrame(pd.DataFrame(results))

    def perform_news_search(self) -> DataFrame:
        """Perform Google News search."""
        query = getattr(self, "query", "")
        hl = getattr(self, "hl", "en-US") or "en-US"
        gl = getattr(self, "gl", "US") or "US"
        topic = getattr(self, "topic", None)
        location = getattr(self, "location", None)

        ceid = f"{gl}:{hl.split('-')[0]}"

        # Build RSS URL based on parameters
        if topic:
            # Topic-based feed
            base_url = f"https://news.google.com/rss/headlines/section/topic/{quote_plus(topic.upper())}"
            params = f"?hl={hl}&gl={gl}&ceid={ceid}"
            rss_url = base_url + params
        elif location:
            # Location-based feed
            base_url = f"https://news.google.com/rss/headlines/section/geo/{quote_plus(location)}"
            params = f"?hl={hl}&gl={gl}&ceid={ceid}"
            rss_url = base_url + params
        elif query:
            # Keyword search feed
            base_url = "https://news.google.com/rss/search?q="
            query_encoded = quote_plus(query)
            params = f"&hl={hl}&gl={gl}&ceid={ceid}"
            rss_url = f"{base_url}{query_encoded}{params}"
        else:
            self.status = "No search query, topic, or location provided."
            return DataFrame(
                pd.DataFrame(
                    [{"title": "Error", "link": "", "published": "", "summary": "No search parameters provided"}]
                )
            )

        try:
            response = requests.get(rss_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
        except requests.RequestException as e:
            self.status = f"Failed to fetch news: {e}"
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": str(e)}]))

        if not items:
            self.status = "No news articles found."
            return DataFrame(pd.DataFrame([{"title": "No articles found", "link": "", "published": "", "summary": ""}]))

        articles = []
        max_results = self._get_limit("max_results", DEFAULT_MAX_RESULTS)
        max_content_length = self._get_limit("max_content_length", DEFAULT_MAX_CONTENT_LENGTH)
        for item in items:
            if max_results is not None and len(articles) >= max_results:
                break
            try:
                title = self._truncate_content(
                    self.clean_html(item.title.text if item.title else ""), max_content_length
                )
                link = self._truncate_content(item.link.text if item.link else "", max_content_length)
                published = self._truncate_content(item.pubDate.text if item.pubDate else "", max_content_length)
                summary = self._truncate_content(
                    self.clean_html(item.description.text if item.description else ""), max_content_length
                )
                articles.append({"title": title, "link": link, "published": published, "summary": summary})
            except (AttributeError, ValueError, TypeError) as e:
                self.log(f"Error parsing article: {e!s}")
                continue

        return DataFrame(pd.DataFrame(articles))

    def perform_rss_read(self) -> DataFrame:
        """Read RSS feed."""
        rss_url = getattr(self, "query", "")
        if not rss_url:
            return DataFrame(
                pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": "No RSS URL provided"}])
            )

        try:
            response = self._safe_get_url(rss_url)
            response.raise_for_status()
            if not response.content.strip():
                msg = "Empty response received"
                raise ValueError(msg)

            # Validate XML
            try:
                BeautifulSoup(response.content, "xml")
            except Exception as e:
                msg = f"Invalid XML response: {e}"
                raise ValueError(msg) from e

            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
        except (httpx.HTTPError, ValueError) as e:
            self.status = f"Failed to fetch RSS: {e}"
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": str(e)}]))

        max_results = self._get_limit("max_results", DEFAULT_MAX_RESULTS)
        max_content_length = self._get_limit("max_content_length", DEFAULT_MAX_CONTENT_LENGTH)
        articles = [
            {
                "title": self._truncate_content(item.title.text if item.title else "", max_content_length),
                "link": self._truncate_content(item.link.text if item.link else "", max_content_length),
                "published": self._truncate_content(item.pubDate.text if item.pubDate else "", max_content_length),
                "summary": self._truncate_content(
                    item.description.text if item.description else "", max_content_length
                ),
            }
            for item in (items if max_results is None else items[:max_results])
        ]

        # Ensure DataFrame has correct columns even if empty
        df_articles = pd.DataFrame(articles, columns=["title", "link", "published", "summary"])
        self.log(f"Fetched {len(df_articles)} articles.")
        return DataFrame(df_articles)

    def perform_search(self) -> DataFrame:
        """Main search method that routes to appropriate search function based on mode."""
        search_mode = getattr(self, "search_mode", "Web")

        if search_mode == "Web":
            return self.perform_web_search()
        if search_mode == "News":
            return self.perform_news_search()
        if search_mode == "RSS":
            return self.perform_rss_read()
        # Fallback to web search
        return self.perform_web_search()
