import importlib.util
import io
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from markitdown import MarkItDown

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.helpers.data import safe_convert
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SliderInput, TableInput
from lfx.log.logger import logger
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.request_utils import get_user_agent
from lfx.utils.ssrf_protection import SSRFProtectionError, is_ssrf_protection_enabled, validate_and_resolve_url
from lfx.utils.ssrf_transport import create_ssrf_protected_client

# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_DEPTH = 1
DEFAULT_FORMAT = "Text"


URL_REGEX = re.compile(
    r"^(https?:\/\/)?" r"(www\.)?" r"([a-zA-Z0-9.-]+)" r"(\.[a-zA-Z]{2,})?" r"(:\d+)?" r"(\/[^\s]*)?$",
    re.IGNORECASE,
)

USER_AGENT = None
# Check if langflow is installed using importlib.util.find_spec(name))
if importlib.util.find_spec("langflow"):
    langflow_installed = True
    USER_AGENT = get_user_agent()
else:
    langflow_installed = False
    USER_AGENT = "lfx"


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
    documentation: str = "https://docs.langflow.org/url"
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
            input_types=["Message"],
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
            info=(
                "Output Format. Use 'Text' to extract the text from the HTML, "
                "'Markdown' to parse the HTML into Markdown format, or 'HTML' "
                "for the raw HTML content."
            ),
            options=["Text", "HTML", "Markdown"],
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
            value=[{"key": "User-Agent", "value": USER_AGENT}],
            advanced=True,
            input_types=["DataFrame", "Table"],
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
        Output(display_name="Extracted Pages", name="page_results", method="fetch_content"),
        Output(display_name="Raw Content", name="raw_results", method="fetch_content_as_message", tool_mode=False),
    ]

    @staticmethod
    def _html_extractor(x: str) -> str:
        """Extract raw HTML content."""
        return x

    @staticmethod
    def _text_extractor(x: str) -> str:
        """Extract clean text from HTML."""
        return BeautifulSoup(x, "lxml").get_text()

    @staticmethod
    def _markdown_extractor(x: str) -> str:
        """Convert HTML to Markdown format."""
        stream = io.BytesIO(x.encode("utf-8"))
        result = MarkItDown(enable_plugins=False).convert_stream(stream)
        return result.markdown

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validates if the given string matches URL pattern.

        Args:
            url: The URL string to validate

        Returns:
            bool: True if the URL is valid, False otherwise
        """
        return bool(URL_REGEX.match(url))

    def ensure_url(self, url: str) -> tuple[str, list[str]]:
        """Ensures the given string is a valid URL and returns validated IPs for DNS pinning.

        Args:
            url: The URL string to validate and normalize

        Returns:
            tuple[str, list[str]]: The normalized URL and list of validated IPs for DNS pinning

        Raises:
            ValueError: If the URL is invalid or blocked by SSRF protection
        """
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not self.validate_url(url):
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        # ============================================================================
        # SSRF Protection with DNS Pinning
        # ============================================================================
        # This prevents DNS rebinding attacks by:
        # 1. Resolving DNS and validating IPs during security check
        # 2. Returning the validated IP addresses for DNS pinning
        # 3. Using a custom HTTP transport that forces use of the pinned IPs
        # 4. Ignoring any new DNS resolutions (prevents rebinding)
        #
        # Without DNS pinning, an attacker could:
        # - First DNS lookup: returns public IP (passes validation)
        # - Second DNS lookup: returns internal IP (bypasses protection)
        # - Attack succeeds: accesses internal services
        #
        # With DNS pinning:
        # - First DNS lookup: returns public IP (passes validation)
        # - IPs are pinned and returned
        # - HTTP request: uses pinned IPs directly (no new DNS lookup)
        # - Attack fails: even if DNS changes, we use the validated IPs
        # ============================================================================
        try:
            _validated_url, validated_ips = validate_and_resolve_url(url)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e
        else:
            # Log DNS pinning information for security auditing
            if validated_ips:
                logger.debug(f"SSRF Protection: Using DNS pinning with {len(validated_ips)} validated IP(s) for {url}")

            return url, validated_ips

    def _build_http_client(self, url: str, validated_ips: list[str]) -> httpx.AsyncClient:
        """Create an HTTP client with DNS pinning for SSRF protection.

        Args:
            url: The request URL whose hostname will be pinned
            validated_ips: IPs validated by validate_and_resolve_url for this URL

        Returns:
            httpx.AsyncClient: A client with DNS pinning when SSRF protection is enabled
        """
        if is_ssrf_protection_enabled() and validated_ips:
            hostname = urlparse(url).hostname
            if hostname:
                return create_ssrf_protected_client(hostname=hostname, validated_ips=validated_ips)
        return httpx.AsyncClient()

    async def _fetch_url_with_pinning(self, url: str, validated_ips: list[str], headers: dict) -> tuple[str, dict]:
        """Fetch a single URL with DNS pinning protection.

        Args:
            url: The URL to fetch
            validated_ips: Validated IPs for DNS pinning
            headers: HTTP headers to send

        Returns:
            tuple[str, dict]: The HTML content and metadata
        """
        async with self._build_http_client(url, validated_ips) as client:
            try:
                response = await client.get(url, headers=headers, timeout=self.timeout, follow_redirects=False)

                if self.check_response_status:
                    response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()

                # Filter out CSS files if requested
                if self.filter_text_html and "text/css" in content_type:
                    logger.debug(f"Skipping CSS file: {url}")
                    return "", {}

                # Get the HTML content
                html_content = response.text

                # Extract metadata
                metadata = {
                    "source": str(response.url),
                    "title": "",
                    "description": "",
                    "content_type": content_type,
                    "language": "",
                }

                # Try to extract title and description from HTML
                try:
                    soup = BeautifulSoup(html_content, "lxml")
                except Exception:  # noqa: BLE001
                    # Broad exception is acceptable here - metadata extraction is optional
                    # and we don't want to fail the entire request if it fails
                    logger.debug(f"Failed to extract metadata from {url}")
                else:
                    if soup.title:
                        metadata["title"] = soup.title.string or ""

                    # Try to get description from meta tags
                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        metadata["description"] = meta_desc["content"]

                    # Try to get language
                    html_tag = soup.find("html")
                    if html_tag and html_tag.get("lang"):
                        metadata["language"] = html_tag["lang"]

            except httpx.HTTPError as e:
                if self.continue_on_failure:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    return "", {}
                raise
            else:
                return html_content, metadata

    async def _crawl_recursive(
        self, start_url: str, validated_ips: list[str], headers: dict, visited: set, depth: int = 0
    ) -> list[dict]:
        """Recursively crawl URLs with DNS pinning protection.

        Args:
            start_url: The URL to start crawling from
            validated_ips: Validated IPs for DNS pinning
            headers: HTTP headers to send
            visited: Set of already visited URLs
            depth: Current crawl depth

        Returns:
            list[dict]: List of documents with content and metadata
        """
        if depth >= self.max_depth or start_url in visited:
            return []

        visited.add(start_url)
        documents = []

        # Fetch the current URL
        html_content, metadata = await self._fetch_url_with_pinning(start_url, validated_ips, headers)

        if not html_content:
            return documents

        # Extract content based on format
        extractors = {
            "HTML": self._html_extractor,
            "Markdown": self._markdown_extractor,
            "Text": self._text_extractor,
        }
        extractor = extractors.get(self.format, self._text_extractor)
        extracted_content = extractor(html_content)

        # Add the document
        documents.append(
            {
                "page_content": extracted_content,
                "metadata": metadata,
            }
        )

        # If we haven't reached max depth, extract and follow links
        if depth < self.max_depth - 1:
            try:
                soup = BeautifulSoup(html_content, "lxml")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    # Resolve relative URLs
                    absolute_url = urljoin(start_url, href)

                    # Skip if already visited
                    if absolute_url in visited:
                        continue

                    # Check if we should prevent going outside the domain
                    if self.prevent_outside:
                        start_domain = urlparse(start_url).netloc
                        link_domain = urlparse(absolute_url).netloc
                        if start_domain != link_domain:
                            continue

                    # Validate and crawl the linked URL
                    try:
                        _, link_validated_ips = self.ensure_url(absolute_url)
                        sub_docs = await self._crawl_recursive(
                            absolute_url, link_validated_ips, headers, visited, depth + 1
                        )
                        documents.extend(sub_docs)
                    except (ValueError, SSRFProtectionError) as e:
                        if self.continue_on_failure:
                            logger.warning(f"Skipping {absolute_url}: {e}")
                            continue
                        raise

            except Exception:  # noqa: BLE001
                # Broad exception is acceptable here - link extraction is optional
                # and we don't want to fail the entire crawl if one page has issues
                logger.debug(f"Failed to extract links from {start_url}")

        return documents

    async def fetch_url_contents(self) -> list[dict]:
        """Load documents from the configured URLs with SSRF protection and DNS pinning.

        This method implements comprehensive SSRF (Server-Side Request Forgery) protection
        using DNS pinning to prevent DNS rebinding attacks. Each URL is validated and its
        DNS resolution is pinned before any HTTP requests are made.

        Returns:
            list[dict]: List of documents with content and metadata

        Raises:
            ValueError: If no valid URLs are provided or if there's an error loading documents
        """
        try:
            # Validate all URLs and get their validated IPs for DNS pinning
            validated_urls = []
            first_validation_error: Exception | None = None
            for url in self.urls:
                if not url.strip():
                    continue
                try:
                    normalized_url, validated_ips = self.ensure_url(url)
                    validated_urls.append((normalized_url, validated_ips))
                except (ValueError, SSRFProtectionError) as e:
                    # Remember the first rejection so its real cause (for example an
                    # SSRF block) can be surfaced if no URL survives validation,
                    # instead of being hidden behind "No valid URLs provided".
                    if first_validation_error is None:
                        first_validation_error = e
                    if self.continue_on_failure:
                        logger.warning(f"Skipping invalid URL {url}: {e}")
                        continue
                    raise

            # Remove duplicates while preserving order
            seen = set()
            unique_validated_urls = []
            for url, ips in validated_urls:
                if url not in seen:
                    seen.add(url)
                    unique_validated_urls.append((url, ips))

            logger.debug(f"Validated {len(unique_validated_urls)} unique URL(s)")

            if not unique_validated_urls:
                # Surface the actual reason every candidate URL was rejected (e.g. an
                # SSRF block) rather than a generic message, so a security failure is
                # not silently swallowed when continue_on_failure is enabled.
                if first_validation_error is not None:
                    raise first_validation_error
                msg = "No valid URLs provided."
                raise ValueError(msg)

            # Prepare headers
            headers_dict = {header["key"]: header["value"] for header in self.headers if header["value"] is not None}

            # Crawl all URLs
            all_docs = []
            for url, validated_ips in unique_validated_urls:
                logger.debug(f"Crawling {url} with max_depth={self.max_depth}")

                try:
                    visited = set()
                    docs = await self._crawl_recursive(url, validated_ips, headers_dict, visited, depth=0)

                    if not docs:
                        logger.warning(f"No documents found for {url}")
                        continue

                    logger.debug(f"Found {len(docs)} document(s) from {url}")
                    all_docs.extend(docs)

                except httpx.HTTPError as e:
                    if self.continue_on_failure:
                        logger.warning(f"Error loading documents from {url}: {e}")
                        continue
                    msg = f"Error loading documents from {url}: {e}"
                    raise ValueError(msg) from e

            if not all_docs:
                msg = "No documents were successfully loaded from any URL"
                raise ValueError(msg)

            # Convert to output format
            return [
                {
                    "text": safe_convert(doc["page_content"], clean_data=True),
                    "url": doc["metadata"].get("source", ""),
                    "title": doc["metadata"].get("title", ""),
                    "description": doc["metadata"].get("description", ""),
                    "content_type": doc["metadata"].get("content_type", ""),
                    "language": doc["metadata"].get("language", ""),
                }
                for doc in all_docs
            ]

        except Exception as e:
            error_msg = e.message if hasattr(e, "message") else str(e)
            msg = f"Error loading documents: {error_msg}"
            logger.exception(msg)
            raise ValueError(msg) from e

    async def fetch_content(self) -> DataFrame:
        """Convert the documents to a DataFrame."""
        url_contents = await self.fetch_url_contents()
        return DataFrame(data=url_contents)

    async def fetch_content_as_message(self) -> Message:
        """Convert the documents to a Message."""
        url_contents = await self.fetch_url_contents()
        return Message(text="\n\n".join([x["text"] for x in url_contents]), data={"data": url_contents})
