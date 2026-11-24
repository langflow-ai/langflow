import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"
MAX_RESULTS_MIN = 1
MAX_RESULTS_MAX = 100
HIGHLIGHTS_MAX_RESULTS = 50


class InputValidationError(ValueError):
    """Raised when input validation fails."""


class YouDotComSearchComponent(Component):
    """You.com Search component for web search optimized for LLMs and RAG.

    This component calls the You.com Search API to perform web searches
    and returns structured results as Data objects with titles, URLs,
    descriptions, and snippets. Results are also available as a DataFrame.

    Attributes:
        display_name: Human-readable name for the component.
        description: Description of what the component does.
        icon: Icon identifier for the UI.
        inputs: List of input parameters (api_key, query, max_results, etc.).
        outputs: List of output methods (fetch_content_dataframe).
    """

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
            info="Your You.com API key. Get one at https://you.com/platform/api-keys",
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
            name="extraction_mode",
            display_name="Extraction Mode",
            info="Attach query-relevant highlights or full-page content to each result.",
            options=["highlights", "full_page"],
            value=None,
            advanced=True,
        ),
        DropdownInput(
            name="extraction_formats",
            display_name="Extraction Format",
            info="Format for full-page content. Only valid when Extraction Mode is full_page.",
            options=["markdown", "html"],
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
        """Fetch search results from You.com API.

        Returns:
            list[Data]: A list of Data objects containing search results,
                        each with title, URL, description, snippets, and optionally contents.

        Raises:
            InputValidationError: If max_results is outside the valid range (1-100).
        """
        try:
            if self.max_results is not None and not (MAX_RESULTS_MIN <= self.max_results <= MAX_RESULTS_MAX):
                msg = f"max_results must be between {MAX_RESULTS_MIN} and {MAX_RESULTS_MAX}"
                raise InputValidationError(msg)

            if not self.query or not self.query.strip():
                msg = "Search query cannot be empty. Please provide a valid search query."
                raise InputValidationError(msg)

            url = "https://ydc-index.io/v1/search"
            headers = {"X-API-Key": self.api_key, "User-Agent": USER_AGENT}
            params: dict = {"query": self.query.strip(), "count": self.max_results}

            if self.country:
                params["country"] = self.country
            if self.safesearch:
                params["safesearch"] = self.safesearch
            if self.freshness:
                params["freshness"] = self.freshness
            if self.extraction_formats and self.extraction_mode != "full_page":
                msg = "extraction_formats requires extraction_mode=full_page"
                raise InputValidationError(msg)
            if (
                self.extraction_mode == "highlights"
                and self.max_results is not None
                and self.max_results > HIGHLIGHTS_MAX_RESULTS
            ):
                msg = "max_results must be 50 or fewer when extraction_mode=highlights"
                raise InputValidationError(msg)
            if self.extraction_mode:
                extraction: dict = {"extraction_mode": self.extraction_mode}
                if self.extraction_formats:
                    extraction["full_page"] = {"extraction_formats": [self.extraction_formats]}
                params["extraction"] = extraction
            if self.language:
                params["language"] = self.language

            with httpx.Client(timeout=90.0) as client:
                response = client.get(url, params=params, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = []
            results = search_results.get("results", {})

            for result in [*results.get("web", []), *results.get("news", [])]:
                contents = result.get("contents") or {}
                snippets = result.get("snippets") or contents.get("highlights") or []
                content = (
                    contents.get("markdown")
                    or contents.get("html")
                    or ("\n\n".join(snippets) if contents else result.get("description", ""))
                )
                result_data = {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "description": result.get("description", ""),
                    "snippets": snippets,
                    "content": content,
                }
                if contents:
                    result_data["contents"] = contents
                if result.get("page_age"):
                    result_data["page_age"] = result["page_age"]

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
        """Fetch search results as a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the search results.
        """
        data = self.fetch_content()
        return DataFrame(data)
