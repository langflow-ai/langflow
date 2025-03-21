import logging
import re

from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader

from langflow.custom.custom_component.component import Component
from langflow.helpers.data import data_to_text
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message

logger = logging.getLogger(__name__)


class URLComponent(Component):
    """A component that loads and parses child links from a root URL recursively."""

    display_name = "URL"
    description = "Load and parse child links from a root URL recursively"
    icon = "layout-template"
    name = "URLComponent"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Enter one or more URLs to crawl recursively, by clicking the '+' button.",
            is_list=True,
            tool_mode=True,
            placeholder="Enter a URL...",
            list_add_label="Add URL",
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            info=(
                "Controls how many 'clicks' away from the initial page the crawler will go:\n"
                "- depth 1: only the initial page\n"
                "- depth 2: initial page + all pages linked directly from it\n"
                "- depth 3: initial page + direct links + links found on those direct link pages\n"
                "Note: This is about link traversal, not URL path depth."
            ),
            value=1,
            required=False,
        ),
        BoolInput(
            name="prevent_outside",
            display_name="Prevent Outside",
            info=(
                "If enabled, only crawls URLs within the same domain as the root URL. "
                "This helps prevent the crawler from going to external websites."
            ),
            value=True,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="use_async",
            display_name="Use Async",
            info=(
                "If enabled, uses asynchronous loading which can be significantly faster "
                "but might use more system resources."
            ),
            value=True,
            required=False,
            advanced=True,
        ),
        DropdownInput(
            name="format",
            display_name="Output Format",
            info="Output Format. Use 'Text' to extract the text from the HTML or 'HTML' for the raw HTML content.",
            options=["Text", "HTML"],
            value="Text",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Message", name="text", method="fetch_content_text"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def validate_url(self, string: str) -> bool:
        """Validates if the given string matches URL pattern."""
        url_regex = re.compile(
            r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
            re.IGNORECASE,
        )
        return bool(url_regex.match(string))

    def ensure_url(self, url: str) -> str:
        """Ensures the given string is a valid URL."""
        if not url.startswith(("http://", "https://")):
            url = "http://" + url

        if not self.validate_url(url):
            error_msg = "Invalid URL - " + url
            raise ValueError(error_msg)

        return url

    def fetch_content(self) -> list[Data]:
        """Load documents from the URLs."""
        all_docs = []
        data = []
        try:
            urls = list({self.ensure_url(url.strip()) for url in self.urls if url.strip()})

            no_urls_msg = "No valid URLs provided."
            if not urls:
                raise ValueError(no_urls_msg)

            for processed_url in urls:
                msg = f"Loading documents from {processed_url}"
                logger.info(msg)

                extractor = (lambda x: x) if self.format == "HTML" else (lambda x: BeautifulSoup(x, "lxml").get_text())
                loader = RecursiveUrlLoader(
                    url=processed_url,
                    max_depth=self.max_depth,
                    prevent_outside=self.prevent_outside,
                    use_async=self.use_async,
                    extractor=extractor,
                )

                docs = loader.load()
                msg = f"Found {len(docs)} documents from {processed_url}"
                logger.info(msg)
                all_docs.extend(docs)

            data = [Data(text=doc.page_content, **doc.metadata) for doc in all_docs]
            self.status = data

        except Exception as e:
            msg = f"Error loading documents: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

        self.status = data
        return data

    def fetch_content_text(self) -> Message:
        """Load documents and return their text content."""
        data = self.fetch_content()
        result_string = data_to_text("{text}", data)
        self.status = result_string
        return Message(text=result_string)

    def as_dataframe(self) -> DataFrame:
        """Convert the documents to a DataFrame."""
        data_frame = DataFrame(self.fetch_content())
        self.status = data_frame
        return data_frame
