import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"


class YouDotComSearchComponent(Component):
    display_name = "You.com Search"
    description = (
        "**You.com Search** is a web search API optimized for LLMs and RAG. "
        "Returns structured results with titles, URLs, and snippets."
    )
    icon = "YouDotCom"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="You.com API Key",
            required=True,
            info="Your You.com API key. Get one at https://docs.you.com",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query to execute. Supports operators: site:, filetype:, +, -, AND, OR, NOT, lang:",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of search results to return (1-100).",
            value=10,
            advanced=True,
        ),
        DropdownInput(
            name="country",
            display_name="Country",
            info="Filter results by country.",
            options=[
                "AR",
                "AU",
                "AT",
                "BE",
                "BR",
                "CA",
                "CL",
                "CN",
                "DK",
                "FI",
                "FR",
                "DE",
                "HK",
                "IN",
                "ID",
                "IT",
                "JP",
                "KR",
                "MY",
                "MX",
                "NL",
                "NZ",
                "NO",
                "PH",
                "PL",
                "PT",
                "RU",
                "SA",
                "ZA",
                "ES",
                "SE",
                "CH",
                "TW",
                "TR",
                "GB",
                "US",
            ],
            value=None,
            advanced=True,
        ),
        DropdownInput(
            name="safesearch",
            display_name="Safe Search",
            info="Content moderation filter level.",
            options=["off", "moderate", "strict"],
            value="moderate",
            advanced=True,
        ),
        DropdownInput(
            name="freshness",
            display_name="Freshness",
            info="Filter results by recency.",
            options=["day", "week", "month", "year"],
            value=None,
            advanced=True,
        ),
        DropdownInput(
            name="livecrawl",
            display_name="Live Crawl",
            info="Which sections to live-crawl for full page content.",
            options=["web", "news", "all"],
            value=None,
            advanced=True,
        ),
        DropdownInput(
            name="livecrawl_formats",
            display_name="Live Crawl Format",
            info="Format for live-crawled content. Only relevant when Live Crawl is set.",
            options=["html", "markdown"],
            value=None,
            advanced=True,
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            info="Filter results by language (BCP 47 code).",
            options=[
                "AR",
                "BN",
                "BG",
                "CA",
                "CS",
                "DA",
                "DE",
                "EL",
                "EN",
                "EN-GB",
                "ES",
                "ET",
                "EU",
                "FI",
                "FR",
                "GL",
                "GU",
                "HE",
                "HI",
                "HR",
                "HU",
                "IS",
                "IT",
                "JP",
                "KN",
                "KO",
                "LT",
                "LV",
                "ML",
                "MR",
                "MS",
                "NB",
                "NL",
                "PA",
                "PL",
                "PT-BR",
                "PT-PT",
                "RO",
                "RU",
                "SK",
                "SL",
                "SR",
                "SV",
                "TA",
                "TE",
                "TH",
                "TR",
                "UK",
                "VI",
                "ZH-HANS",
                "ZH-HANT",
            ],
            value=None,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            url = "https://ydc-index.io/v1/search"
            headers = {"X-API-Key": self.api_key, "User-Agent": USER_AGENT}
            params: dict = {"query": self.query, "count": self.max_results}

            if self.country:
                params["country"] = self.country
            if self.safesearch:
                params["safesearch"] = self.safesearch
            if self.freshness:
                params["freshness"] = self.freshness
            if self.livecrawl:
                params["livecrawl"] = self.livecrawl
            if self.livecrawl_formats:
                params["livecrawl_formats"] = self.livecrawl_formats
            if self.language:
                params["language"] = self.language

            with httpx.Client(timeout=90.0) as client:
                response = client.get(url, params=params, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = []
            results = search_results.get("results", {})

            for result in results.get("web", []):
                description = result.get("description", "")
                result_data = {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "description": description,
                    "snippets": result.get("snippets", []),
                }
                if result.get("contents"):
                    result_data["contents"] = result["contents"]

                data_results.append(Data(text=description, data=result_data))

            for result in results.get("news", []):
                description = result.get("description", "")
                result_data = {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "description": description,
                    "page_age": result.get("page_age"),
                }
                if result.get("contents"):
                    result_data["contents"] = result["contents"]

                data_results.append(Data(text=description, data=result_data))

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
