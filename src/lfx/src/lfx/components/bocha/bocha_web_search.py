import re

import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, QueryInput, SecretStrInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message

BOCHA_SEARCH_URL = "https://api.bochaai.com/v1/web-search"
BOCHA_FRESHNESS_OPTIONS = ["noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"]
BOCHA_MIN_RESULTS = 1
BOCHA_MAX_RESULTS = 50
BOCHA_EMPTY_RESULTS_MESSAGE = "No search results found."
BOCHA_COUNT_VALIDATION_MESSAGE = f"Max Results must be an integer between {BOCHA_MIN_RESULTS} and {BOCHA_MAX_RESULTS}."


class BochaWebSearchComponent(Component):
    display_name = "Bocha Web Search"
    description = (
        "Search the entire web for any webpage information and webpage links using Bocha, "
        "with strong ability to retrieve real-time information from the web. "
    )
    documentation = "https://open.bochaai.com/"
    icon = "Bocha"
    name = "BochaWebSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Bocha API Key",
            required=True,
            info="Your Bocha Web Search API key.",
        ),
        QueryInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with Bocha.",
            tool_mode=True,
            required=True,
        ),
        DropdownInput(
            name="freshness",
            display_name="Freshness",
            options=BOCHA_FRESHNESS_OPTIONS,
            value="noLimit",
            info="Restrict results to a time range.",
            tool_mode=True,
        ),
        BoolInput(
            name="summary",
            display_name="Include Summary",
            info="Include the summary field returned by Bocha.",
            value=True,
        ),
        IntInput(
            name="count",
            display_name="Max Results",
            info="The maximum number of results to return (1-50).",
            value=10,
        ),
        MessageTextInput(
            name="include",
            display_name="Include Domains",
            info="Comma-separated or pipe-separated domains to include.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude",
            display_name="Exclude Domains",
            info="Comma-separated or pipe-separated domains to exclude.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
    ]

    def _build_error_data(self, error_message: str) -> Data:
        return Data(text=error_message, data={"error": error_message})

    def _split_domains(self, domains: str | None) -> str | None:
        if not domains:
            return None
        normalized_domains = [part.strip() for part in re.split(r"[|,]", domains) if part.strip()]
        return "|".join(normalized_domains) if normalized_domains else None

    def _build_payload(self) -> dict:
        payload: dict = {
            "query": self.query,
            "summary": bool(self.summary),
            "count": self._parse_count(),
        }

        if self.freshness:
            payload["freshness"] = self.freshness

        include_domains = self._split_domains(getattr(self, "include", None))
        exclude_domains = self._split_domains(getattr(self, "exclude", None))
        if include_domains:
            payload["include"] = include_domains
        if exclude_domains:
            payload["exclude"] = exclude_domains

        return payload

    def _parse_count(self) -> int:
        try:
            return int(self.count)
        except (TypeError, ValueError) as exc:
            raise ValueError(BOCHA_COUNT_VALIDATION_MESSAGE) from exc

    def _validate_search_inputs(self) -> str | None:
        if not self.api_key:
            return "Missing Bocha API Key."
        if not self.query or not str(self.query).strip():
            return "Empty search query."
        try:
            count = self._parse_count()
        except ValueError as exc:
            return str(exc)
        if count < BOCHA_MIN_RESULTS or count > BOCHA_MAX_RESULTS:
            return f"Max Results must be between {BOCHA_MIN_RESULTS} and {BOCHA_MAX_RESULTS}."
        if self.freshness and self.freshness not in BOCHA_FRESHNESS_OPTIONS:
            return f"Invalid freshness value: {self.freshness}"
        return None

    def _request_search_results(self) -> dict:
        validation_error = self._validate_search_inputs()
        if validation_error:
            raise ValueError(validation_error)

        cached_results = getattr(self, "_cached_search_results", None)
        if cached_results is not None:
            return cached_results

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload()

        with httpx.Client(timeout=90.0) as client:
            response = client.post(BOCHA_SEARCH_URL, json=payload, headers=headers)

        response.raise_for_status()
        search_results = response.json()
        self._cached_search_results = search_results
        return search_results

    def _build_text_output(self, search_results: object) -> str:
        if not isinstance(search_results, dict):
            return BOCHA_EMPTY_RESULTS_MESSAGE
        response_data = search_results.get("data", search_results)
        if not isinstance(response_data, dict):
            return BOCHA_EMPTY_RESULTS_MESSAGE
        web_pages = response_data.get("webPages", {})
        if not isinstance(web_pages, dict):
            return BOCHA_EMPTY_RESULTS_MESSAGE
        contexts = web_pages.get("value", [])
        if not isinstance(contexts, list):
            return BOCHA_EMPTY_RESULTS_MESSAGE
        if not contexts:
            return BOCHA_EMPTY_RESULTS_MESSAGE

        max_context = min(len(contexts), 10)
        formatted_contexts = []
        for index in range(max_context):
            context = contexts[index]
            if not isinstance(context, dict):
                continue
            formatted_context = (
                f"[[Reference:{index + 1}]]\n"
                f"Webpage Title: {context.get('name', '')}\n"
                f"Webpage URL: {context.get('url', '')}\n"
                f"Webpage Content: {context.get('summary') or context.get('snippet', '')}\n"
                f"Published Time: {context.get('datePublished', '')}\n"
                f"Site Name: {context.get('siteName') or context.get('name', '')}"
            )
            formatted_contexts.append(formatted_context)

        if not formatted_contexts:
            return BOCHA_EMPTY_RESULTS_MESSAGE
        return "\n\n".join(formatted_contexts)

    def fetch_content(self) -> Data:
        try:
            search_results = self._request_search_results()
            result = Data(data=search_results)
            self.status = search_results
        except httpx.TimeoutException:
            error_message = "Request timed out (90s). Please try again or adjust parameters."
            logger.error(error_message)
            return self._build_error_data(error_message)
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return self._build_error_data(error_message)
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return self._build_error_data(error_message)
        except ValueError as exc:
            error_message = str(exc)
            logger.error(error_message)
            return self._build_error_data(error_message)
        else:
            return result

    def run_model(self) -> Data:
        return self.fetch_content()

    def fetch_content_text(self) -> Message:
        try:
            search_results = self._request_search_results()
            result_string = self._build_text_output(search_results)
            self.status = result_string
            return Message(text=result_string)
        except httpx.TimeoutException:
            error_message = "Request timed out (90s). Please try again or adjust parameters."
            logger.error(error_message)
            return Message(text=error_message)
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return Message(text=error_message)
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return Message(text=error_message)
        except ValueError as exc:
            error_message = str(exc)
            logger.error(error_message)
            return Message(text=error_message)
