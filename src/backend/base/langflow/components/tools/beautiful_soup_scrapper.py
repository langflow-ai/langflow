import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DictInput, IntInput, MessageTextInput
from langflow.schema import Data

logging.basicConfig(level=logging.ERROR)

HTTP_SUCCESS_CODE = 200


class BeautifulSoupScrapeApiComponent(LCToolComponent):
    display_name = "Beautiful Soup Scraper"
    description = "Scrape web content using BeautifulSoup."
    name = "beautiful_soup_scraper"
    documentation = "https://www.crummy.com/software/BeautifulSoup/bs4/doc/"
    icon = "BeautifulSoup"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The URL to scrape.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds for the request.",
            value=300,
        ),
        DictInput(
            name="page_options",
            display_name="Page Options",
            info="The page options to send with the request.",
            advanced=True,
        ),
        DictInput(
            name="extractor_options",
            display_name="Extractor Options",
            info="The extractor options to send with the request.",
            advanced=True,
        ),
    ]

    class BeautifulSoupScrapeApiSchema(BaseModel):
        url: str = Field(..., description="The URL to scrape")
        timeout: int = Field(default=10, description="Timeout in seconds for the request")
        page_options: dict | None = Field(default=None, description="The page options to send with the request")
        extractor_options: dict | None = Field(
            default=None, description="The extractor options to send with the request"
        )

    def run_model(self) -> Data:
        results = self.scrape_url(
            url=self.url,
            timeout=self.timeout,
            page_options=self.page_options,
            extractor_options=self.extractor_options,
        )
        data = Data(data=results)
        self.status = data
        return data

    def scrape_url(
        self, url: str, timeout: int = 10, page_options: dict | None = None, extractor_options: dict | None = None
    ) -> dict[str, list[dict[str, str]]]:
        """Scrapes content from URL and linked pages, returning structured data."""
        urls = self.extract_urls(url, timeout, page_options)
        scraped_data = []
        for target_url in urls:
            data = self.scrape_page(target_url, timeout, extractor_options)
            scraped_data.append(data)
        return {"scraped_data": scraped_data}

    def extract_urls(self, base_url: str, timeout: int, page_options: dict | None) -> list[str]:
        """Extracts URLs from base URL that share the same domain."""
        try:
            response = requests.get(base_url, timeout=timeout, params=page_options)
            if response.status_code != HTTP_SUCCESS_CODE:
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            a_tags = soup.find_all("a")
            urls = []
            base_parsed = urlparse(base_url)
            base_netloc = base_parsed.netloc

            for tag in a_tags:
                href = tag.get("href")
                if href:
                    full_url = urljoin(base_url, href)
                    parsed_url = urlparse(full_url)
                    if parsed_url.scheme in ["http", "https"] and parsed_url.netloc == base_netloc:
                        urls.append(full_url)
            return list(set(urls))
        except requests.RequestException:
            logging.exception("Error extracting URLs from page")
            return []

    def scrape_page(self, url: str, timeout: int, extractor_options: dict | None) -> dict[str, str]:
        """Extracts content from a single webpage."""
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code != HTTP_SUCCESS_CODE:
                return {"url": url, "title": "Error accessing the page", "content": ""}

            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else "No Title"
            content = soup.get_text(separator="\n", strip=True)

            # Example usage of extractor_options (if any)
            if extractor_options:
                # Implement extractor options logic here
                pass
        except requests.RequestException:
            logging.exception("Error scraping page: %s", url)
            return {"url": url, "title": "Error accessing the page", "content": ""}
        else:
            return {"url": url, "title": title, "content": content}

    def build_tool(self) -> Tool:
        tool_description = (
            "Scrape web content using BeautifulSoup. Input should be a dictionary "
            "with 'url' and optional 'timeout', 'page_options', and "
            "'extractor_options'."
        )
        return StructuredTool.from_function(
            name="beautifulsoup_scrape_api",
            description=tool_description,
            func=self.scrape_url,
            args_schema=self.BeautifulSoupScrapeApiSchema,
        )
