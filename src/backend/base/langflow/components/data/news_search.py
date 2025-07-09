from urllib.parse import quote_plus

import pandas as pd
import requests
from bs4 import BeautifulSoup

from langflow.custom import Component
from langflow.io import IntInput, MessageTextInput, Output
from langflow.schema import DataFrame


class NewsSearchComponent(Component):
    display_name = "News Search"
    description = "Searches Google News via RSS. Returns clean article data."
    documentation: str = "https://docs.langflow.org/components-data#news-search"
    icon = "newspaper"
    name = "NewsSearch"

    inputs = [
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

    outputs = [Output(name="articles", display_name="News Articles", method="search_news")]

    def search_news(self) -> DataFrame:
        # Defaults
        hl = getattr(self, "hl", None) or "en-US"
        gl = getattr(self, "gl", None) or "US"
        ceid = getattr(self, "ceid", None) or f"{gl}:{hl.split('-')[0]}"
        topic = getattr(self, "topic", None)
        location = getattr(self, "location", None)
        query = getattr(self, "query", None)

        # Build base URL
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
            query_parts = [query]
            query_encoded = quote_plus(" ".join(query_parts))
            params = f"&hl={hl}&gl={gl}&ceid={ceid}"
            rss_url = f"{base_url}{query_encoded}{params}"
        else:
            self.status = "No search query, topic, or location provided."
            self.log(self.status)
            return DataFrame(
                pd.DataFrame(
                    [
                        {
                            "title": "Error",
                            "link": "",
                            "published": "",
                            "summary": "No search query, topic, or location provided.",
                        }
                    ]
                )
            )

        try:
            response = requests.get(rss_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
        except requests.RequestException as e:
            self.status = f"Failed to fetch news: {e}"
            self.log(self.status)
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": str(e)}]))
        except (AttributeError, ValueError, TypeError) as e:
            self.status = f"Unexpected error: {e!s}"
            self.log(self.status)
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "published": "", "summary": str(e)}]))

        if not items:
            self.status = "No news articles found."
            self.log(self.status)
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

        df_articles = pd.DataFrame(articles)
        self.log(f"Found {len(df_articles)} articles.")
        return DataFrame(df_articles)

    def clean_html(self, html_string: str) -> str:
        return BeautifulSoup(html_string, "html.parser").get_text(separator=" ", strip=True)
