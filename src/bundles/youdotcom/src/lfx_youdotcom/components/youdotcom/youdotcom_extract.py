import json

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"
MIN_TIMEOUT = 2
MAX_TIMEOUT = 100


class InputValidationError(ValueError):
    """Raised when input validation fails."""


class YouDotComExtractComponent(Component):
    """You.com Extract component for extracting clean content from URLs."""

    display_name = "You.com Extract"
    description = "**You.com Extract** extracts clean Markdown or HTML from any webpage or PDF."
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
            info='Newline-separated URLs or JSON array (e.g., ["https://example.com"]).',
            tool_mode=True,
        ),
        DropdownInput(
            name="formats",
            display_name="Format",
            info="The output format for extracted content.",
            options=["markdown", "html"],
            value="markdown",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="End-to-end timeout in seconds (2-100).",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        """Extract content from URLs using the You.com Extract API."""
        try:
            if self.timeout is not None and not (MIN_TIMEOUT <= self.timeout <= MAX_TIMEOUT):
                msg = f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds"
                raise InputValidationError(msg)
            if not isinstance(self.urls, str):
                msg = "urls must be a string. Please provide valid URLs."
                raise InputValidationError(msg)

            urls_input = self.urls.strip()
            if urls_input.startswith("["):
                try:
                    url_list = json.loads(urls_input)
                except json.JSONDecodeError as e:
                    msg = f"Invalid JSON array format: {e}"
                    raise InputValidationError(msg) from e
                if not isinstance(url_list, list):
                    msg = "JSON input must be a list"
                    raise TypeError(msg)
            else:
                url_list = urls_input.split("\n")

            if any(not isinstance(url, str) for url in url_list):
                msg = "urls must contain only strings."
                raise InputValidationError(msg)
            url_list = [url.strip() for url in url_list if url.strip()]
            if not url_list:
                msg = "urls cannot be empty. Please provide at least one valid URL."
                raise InputValidationError(msg)

            headers = {
                "X-API-Key": self.api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            }
            data_results = []
            with httpx.Client(timeout=self.timeout or 30) as client:
                for url in url_list:
                    payload: dict = {
                        "url": url,
                        "full_page": {"extraction_formats": [self.formats]},
                    }
                    if self.timeout is not None:
                        payload["timeout"] = self.timeout

                    response = client.post("https://ydc-index.io/v1/extract", json=payload, headers=headers)
                    response.raise_for_status()
                    item = response.json()
                    if not isinstance(item, dict):
                        msg = "Invalid response format: expected an object"
                        raise TypeError(msg)

                    contents = item.get("contents") or {}
                    full_page = contents.get("full_page") or {}
                    content = full_page.get("markdown") or full_page.get("html") or ""
                    result_data = {
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "content": content,
                    }
                    if item.get("metadata"):
                        result_data["metadata"] = item["metadata"]
                    data_results.append(Data(text=content, data=result_data))

        except httpx.TimeoutException:
            error_message = "Request timed out. Try reducing the number of URLs or increasing the timeout."
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
        """Fetch extracted content as a DataFrame."""
        data = self.fetch_content()
        return DataFrame(data)
