import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
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
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            info="The Google search vertical.",
            options=["classic", "news", "images"],
            value="classic",
            advanced=True,
        ),
        MessageTextInput(
            name="country_code",
            display_name="Country Code",
            info="Two-letter country code, e.g. us.",
            advanced=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="Two-letter language code, e.g. en.",
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
        BoolInput(
            name="light_request",
            display_name="Light Request",
            info="Cheaper, lighter response (1 credit instead of 2).",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="page",
            display_name="Page",
            info="Result page number (1-based).",
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

            payload = {
                "query": self.query,
                "search_type": self.search_type,
                "device": self.device,
                "light_request": self.light_request,
                "page": int(self.page) if self.page else 1,
            }
            if self.country_code:
                payload["country_code"] = self.country_code
            if self.language:
                payload["language"] = self.language

            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = []
            results = search_results.get("organic_results", [])
            max_results = self.max_results or len(results)
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
