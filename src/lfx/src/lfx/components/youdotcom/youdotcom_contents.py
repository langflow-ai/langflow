import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"
MAX_CRAWL_TIMEOUT = 60


class InputValidationError(ValueError):
    """Raised when input validation fails."""

    pass


class YouDotComContentsComponent(Component):
    display_name = "You.com Contents"
    description = (
        "**You.com Contents** extracts clean HTML, markdown, or metadata from any URL. "
        "Useful for RAG pipelines and content extraction."
    )
    icon = "YouDotCom"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="You.com API Key",
            required=True,
            info="Your You.com API key. Get one at https://you.com/platform/api-keys",
        ),
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Comma-separated list of URLs to extract content from.",
            tool_mode=True,
        ),
        DropdownInput(
            name="formats",
            display_name="Format",
            info="The output format for extracted content.",
            options=["markdown", "html", "metadata"],
            value="markdown",
            advanced=True,
        ),
        IntInput(
            name="crawl_timeout",
            display_name="Crawl Timeout",
            info="Timeout in seconds for page crawling (1-60).",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        """Extract content from URLs using You.com API.

        Returns:
            list[Data]: A list of Data objects containing extracted content,
                        each with URL, title, and content (markdown/html/metadata).
        """
        try:
            if self.crawl_timeout is not None and not (1 <= self.crawl_timeout <= MAX_CRAWL_TIMEOUT):
                msg = f"crawl_timeout must be between 1 and {MAX_CRAWL_TIMEOUT} seconds"
                raise InputValidationError(msg)

            url = "https://ydc-index.io/v1/contents"
            headers = {
                "X-API-Key": self.api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            }

            url_list = [u.strip() for u in self.urls.split(",") if u.strip()]
            if not url_list:
                msg = "urls cannot be empty. Please provide at least one valid URL."
                raise InputValidationError(msg)

            payload: dict = {
                "urls": url_list,
                "formats": [self.formats],
            }
            if self.crawl_timeout is not None:
                payload["crawl_timeout"] = self.crawl_timeout

            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            contents_results = response.json()

            data_results = []
            for item in contents_results:
                content = item.get("markdown") or item.get("html") or ""
                result_data = {
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "content": content,
                }
                if item.get("metadata"):
                    result_data["metadata"] = item["metadata"]

                data_results.append(Data(text=content, data=result_data))

        except httpx.TimeoutException:
            error_message = "Request timed out (60s). Try reducing the number of URLs or increasing the timeout."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except InputValidationError as exc:
            error_message = f"Input validation error: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = data_results
            return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        """Fetch extracted content as a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the extracted content.
        """
        data = self.fetch_content()
        return DataFrame(data)
