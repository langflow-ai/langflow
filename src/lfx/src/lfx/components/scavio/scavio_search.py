import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class ScavioSearchComponent(Component):
    display_name = "Scavio Search API"
    description = (
        "**Scavio** is a real-time search API for AI agents - a unified API over Google, "
        "YouTube, Amazon, Walmart, Reddit, TikTok, and Instagram. A cost-effective Tavily "
        "and SerpAPI alternative that returns clean JSON."
    )
    documentation = "https://scavio.dev/docs/langflow"
    icon = "Scavio"
    name = "ScavioSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Scavio API Key",
            required=True,
            info="Your Scavio API Key. Get one at https://dashboard.scavio.dev.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with Scavio.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country Code",
            info="Geo location country code (ISO 3166-1 alpha-2), e.g. us.",
            advanced=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language",
            info="UI language code (ISO 639-1), e.g. en.",
            advanced=True,
        ),
        DropdownInput(
            name="device",
            display_name="Device",
            info="Device profile to emulate.",
            options=["desktop", "mobile"],
            value="desktop",
            advanced=True,
        ),
        IntInput(
            name="page",
            display_name="Page",
            info="Result page number (1-based), sent as the start offset.",
            value=1,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="The maximum number of search results to return.",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            url = "https://api.scavio.dev/api/v2/google"
            headers = {
                "content-type": "application/json",
                "accept": "application/json",
                "authorization": f"Bearer {self.api_key}",
            }

            page = int(self.page) if self.page else 1
            payload = {
                "query": self.query,
                "device": self.device,
                "start": max(page - 1, 0) * 10,
            }
            if self.gl:
                payload["gl"] = self.gl
            if self.hl:
                payload["hl"] = self.hl

            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = []
            results = search_results.get("organic_results", [])
            max_results = self.max_results if self.max_results is not None else len(results)
            for result in results[:max_results]:
                content = result.get("snippet", "")
                result_data = {
                    "title": result.get("title"),
                    "url": result.get("link"),
                    "content": content,
                    "position": result.get("position"),
                }
                data_results.append(Data(text=content, data=result_data))

        except httpx.TimeoutException:
            error_message = "Request timed out (90s). Please try again or adjust parameters."
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
