import re
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import DataFrame
from langflow.services.deps import get_settings_service

DEFAULT_TIMEOUT = 5


class WebSearchComponent(Component):
    display_name = "Web Search"
    description = (
        "Performs a basic DuckDuckGo search (HTML scraping) "
        "and returns a DataFrame of titles, links, snippets, and fetched content."
    )
    icon = "search"
    name = "WebSearchNoAPI"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Keywords to search for.",
            tool_mode=True,
            input_types=[],
            required=True,
        )
    ]

    outputs = [Output(name="results", display_name="Search Results", method="perform_search")]

    def validate_url(self, string: str) -> bool:
        url_regex = re.compile(
            r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
            re.IGNORECASE,
        )
        return bool(url_regex.match(string))

    def ensure_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        if not self.validate_url(url):
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)
        return url

    def perform_search(self) -> DataFrame:
        headers = {"User-Agent": get_settings_service().settings.user_agent}
        params = {"q": self.query, "kl": "us-en"}
        url = "https://html.duckduckgo.com/html/"

        try:
            response = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            self.status = f"Failed request: {e}"
            return DataFrame(pd.DataFrame([{"title": "Error", "link": "", "snippet": str(e), "content": ""}]))

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
                    page = requests.get(final_url, headers=headers, timeout=DEFAULT_TIMEOUT)
                    page.raise_for_status()
                    content = BeautifulSoup(page.text, "lxml").get_text(separator=" ", strip=True)
                except requests.RequestException as e:
                    final_url = decoded_link
                    content = f"(Failed to fetch: {e})"

                results.append(
                    {
                        "title": title_tag.get_text(strip=True),
                        "link": final_url,
                        "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                        "content": content,
                    }
                )

        df_results = pd.DataFrame(results)
        return DataFrame(df_results)
