"""Unified Web Search Component.

This component consolidates Web Search, News Search, and RSS Reader into a single
component with tabs for different search modes.
"""

import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, Output, TabInput
from lfx.schema import DataFrame
from lfx.utils.request_utils import get_user_agent


class WebSearchComponent(Component):
    display_name = "Web Search"
    description = "Search the web, news, or RSS feeds."
    documentation: str = "https://docs.langflow.org/components-data#web-search"
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

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query."""
        return re.sub(r'[<>"\']', "", query.strip())

    def clean_html(self, html_string: str) -> str:
        """Remove HTML tags from text."""
        return BeautifulSoup(html_string, "html.parser").get_text(separator=" ", strip=True)

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

        for result in soup.select("div.result"):
            title_tag = result.select_one("a.result__a")
            snippet_tag = result.select_one("a.result__snippet")
            if title_tag:
                raw_link = title_tag.get("href", "")
                parsed = urlparse(raw_link)
                uddg = parse_qs(parsed.query).get("uddg", [""])[0]
                decoded_link = unquote(uddg) if uddg else raw_link

                try:
                    final_url = self.ensure_url(decoded_link)
                    page = requests.get(final_url, headers=headers, timeout=self.timeout)
                    page.raise_for_status()
                    content = BeautifulSoup(page.text, "lxml").get_text(separator=" ", strip=True)
                except requests.RequestException as e:
                    final_url = decoded_link
                    content = f"(Failed to fetch: {e!s}"

                results.append(
                    {
                        "title": title_tag.get_text(strip=True),
                        "link": final_url,
                        "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                        "content": content,
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
        for item in items:
            try:
                title = self.clean_html(item.title.text if item.title else "")
                link = item.link.text if item.link else ""
                published = item.pubDate.text if item.pubDate else ""
                summary = self.clean_html(item.description.text if item.description else "")
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
            response = requests.get(rss_url, timeout=self.timeout)
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
        except (requests.RequestException, ValueError) as e:
            self.status = f"Failed to fetch RSS: {e}"
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": str(e)}]))

        articles = [
            {
                "title": item.title.text if item.title else "",
                "link": item.link.text if item.link else "",
                "published": item.pubDate.text if item.pubDate else "",
                "summary": item.description.text if item.description else "",
            }
            for item in items
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
