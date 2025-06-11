import re

import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader
from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.helpers.data import safe_convert
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SliderInput, TableInput
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.deps import get_settings_service

# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_DEPTH = 1
DEFAULT_FORMAT = "Text"
URL_REGEX = re.compile(
    r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
    re.IGNORECASE,
)


class URLComponent(Component):
    """A component that loads and parses content from web pages recursively.

    This component allows fetching content from one or more URLs, with options to:
    - Control crawl depth
    - Prevent crawling outside the root domain
    - Use async loading for better performance
    - Extract either raw HTML or clean text
    - Configure request headers and timeouts
    """

    display_name = "URL"
    description = "Fetch content from one or more web pages, following links recursively."
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
            input_types=[],
        ),
        SliderInput(
            name="max_depth",
            display_name="Depth",
            info=(
                "Controls how many 'clicks' away from the initial page the crawler will go:\n"
                "- depth 1: only the initial page\n"
                "- depth 2: initial page + all pages linked directly from it\n"
                "- depth 3: initial page + direct links + links found on those direct link pages\n"
                "Note: This is about link traversal, not URL path depth."
            ),
            value=DEFAULT_MAX_DEPTH,
            range_spec=RangeSpec(min=1, max=5, step=1),
            required=False,
            min_label=" ",
            max_label=" ",
            min_label_icon="None",
            max_label_icon="None",
            # slider_input=True
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
            value=DEFAULT_FORMAT,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the request in seconds.",
            value=DEFAULT_TIMEOUT,
            required=False,
            advanced=True,
        ),
        TableInput(
            name="headers",
            display_name="Headers",
            info="The headers to send with the request",
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Header",
                    "type": "str",
                    "description": "Header name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "Header value",
                },
            ],
            value=[{"key": "User-Agent", "value": get_settings_service().settings.user_agent}],
            advanced=True,
            input_types=["DataFrame"],
        ),
        BoolInput(
            name="filter_text_html",
            display_name="Filter Text/HTML",
            info="If enabled, filters out text/css content type from the results.",
            value=True,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="continue_on_failure",
            display_name="Continue on Failure",
            info="If enabled, continues crawling even if some requests fail.",
            value=True,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="check_response_status",
            display_name="Check Response Status",
            info="If enabled, checks the response status of the request.",
            value=False,
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="autoset_encoding",
            display_name="Autoset Encoding",
            info="If enabled, automatically sets the encoding of the request.",
            value=True,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="page_results", method="fetch_content"),
        Output(display_name="Raw Result", name="raw_results", method="as_message"),
    ]

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validates if the given string matches URL pattern.

        Args:
            url: The URL string to validate

        Returns:
            bool: True if the URL is valid, False otherwise
        """
        return bool(URL_REGEX.match(url))

    def ensure_url(self, url: str) -> str:
        """Ensures the given string is a valid URL.

        Args:
            url: The URL string to validate and normalize

        Returns:
            str: The normalized URL

        Raises:
            ValueError: If the URL is invalid
        """
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not self.validate_url(url):
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        return url

    def _create_loader(self, url: str) -> RecursiveUrlLoader:
        """Creates a RecursiveUrlLoader instance with the configured settings.

        Args:
            url: The URL to load

        Returns:
            RecursiveUrlLoader: Configured loader instance
        """
        headers_dict = {header["key"]: header["value"] for header in self.headers}
        extractor = (lambda x: x) if self.format == "HTML" else (lambda x: BeautifulSoup(x, "lxml").get_text())

        return RecursiveUrlLoader(
            url=url,
            max_depth=self.max_depth,
            prevent_outside=self.prevent_outside,
            use_async=self.use_async,
            extractor=extractor,
            timeout=self.timeout,
            headers=headers_dict,
            check_response_status=self.check_response_status,
            continue_on_failure=self.continue_on_failure,
            base_url=url,  # Add base_url to ensure consistent domain crawling
            autoset_encoding=self.autoset_encoding,  # Enable automatic encoding detection
            exclude_dirs=[],  # Allow customization of excluded directories
            link_regex=None,  # Allow customization of link filtering
        )

    def fetch_url_contents(self) -> list[dict]:
        """Load documents from the configured URLs.

        Returns:
            List[Data]: List of Data objects containing the fetched content

        Raises:
            ValueError: If no valid URLs are provided or if there's an error loading documents
        """
        try:
            urls = list({self.ensure_url(url) for url in self.urls if url.strip()})
            logger.info(f"URLs: {urls}")
            if not urls:
                msg = "No valid URLs provided."
                raise ValueError(msg)

            all_docs = []
            for url in urls:
                logger.info(f"Loading documents from {url}")

                try:
                    loader = self._create_loader(url)
                    docs = loader.load()

                    if not docs:
                        logger.warning(f"No documents found for {url}")
                        continue

                    logger.info(f"Found {len(docs)} documents from {url}")
                    all_docs.extend(docs)

                except requests.exceptions.RequestException as e:
                    logger.exception(f"Error loading documents from {url}: {e}")
                    continue

            if not all_docs:
                msg = "No documents were successfully loaded from any URL"
                raise ValueError(msg)

            # data = [Data(text=doc.page_content, **doc.metadata) for doc in all_docs]
            data = [
                {
                    "text": safe_convert(doc.page_content, clean_data=True),
                    "url": doc.metadata.get("source", ""),
                    "title": doc.metadata.get("title", ""),
                    "description": doc.metadata.get("description", ""),
                    "content_type": doc.metadata.get("content_type", ""),
                    "language": doc.metadata.get("language", ""),
                }
                for doc in all_docs
            ]
        except Exception as e:
            error_msg = e.message if hasattr(e, "message") else e
            msg = f"Error loading documents: {error_msg!s}"
            logger.exception(msg)
            raise ValueError(msg) from e
        return data

    def fetch_content(self) -> DataFrame:
        """Convert the documents to a DataFrame."""
        return DataFrame(data=self.fetch_url_contents())

    def as_message(self) -> Message:
        """Convert the documents to a Message."""
        url_contents = self.fetch_url_contents()
        return Message(text="\n\n".join([x["text"] for x in url_contents]), data={"data": url_contents})
