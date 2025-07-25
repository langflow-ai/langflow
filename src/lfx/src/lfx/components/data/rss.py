import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema import DataFrame


class RSSReaderComponent(Component):
    display_name = "RSS Reader"
    description = "Fetches and parses an RSS feed."
    documentation: str = "https://docs.langflow.org/components-data#rss-reader"
    icon = "rss"
    name = "RSSReaderSimple"

    inputs = [
        MessageTextInput(
            name="rss_url",
            display_name="RSS Feed URL",
            info="URL of the RSS feed to parse.",
            tool_mode=True,
            required=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the RSS feed request.",
            value=5,
            advanced=True,
        ),
    ]

    outputs = [Output(name="articles", display_name="Articles", method="read_rss")]

    def read_rss(self) -> DataFrame:
        try:
            response = requests.get(self.rss_url, timeout=self.timeout)
            response.raise_for_status()
            if not response.content.strip():
                msg = "Empty response received"
                raise ValueError(msg)
            # Check if the response is valid XML
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

        # Ensure the DataFrame has the correct columns even if empty
        df_articles = pd.DataFrame(articles, columns=["title", "link", "published", "summary"])
        logger.info(f"Fetched {len(df_articles)} articles.")
        return DataFrame(df_articles)
