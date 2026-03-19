import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"


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
        try:
            url = "https://ydc-index.io/v1/contents"
            headers = {
                "X-API-Key": self.api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            }

            url_list = [u.strip() for u in self.urls.split(",") if u.strip()]

            payload: dict = {
                "urls": url_list,
                "formats": [self.formats],
            }
            if self.crawl_timeout:
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
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = data_results
            return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return DataFrame(data)
